# CI/CD standards

How every Sigilweaver repo's CI should be shaped. Written up 2026-07-19
after a pyo3/quick-xml audit-advisory sweep added Windows/macOS test
coverage to several repos and immediately caught real, previously-latent
bugs on those platforms - which is exactly the point of this doc: these
rules exist because *not* following them lets bugs ship silently on
platforms nobody tests.

## The rule

**Test on every OS you ship a wheel/binary for. No more, no less.**

The `ci.yml` test matrix must mirror the `release.yml`/`publish.yml`
wheel-build matrix exactly. Testing a platform you don't ship wastes CI
minutes; shipping a platform you don't test is how bugs reach users
first. If a release workflow builds `ubuntu-latest` + `macos-14` +
`windows-latest` wheels, the CI test matrix must run on all three, both
for the Rust test suite and any Python-level (`pytest`/smoke-test)
coverage - a real bug in this sweep was in a Python test script, not
Rust.

**Lint/fmt: once, on Linux, not per-OS.** `cargo fmt --check` and
`cargo clippy` are OS-independent (barring rare `cfg(windows)`/
`cfg(unix)` code paths), so running them on all three platforms just
triples CI time for zero additional signal. Gate them behind
`if: matrix.os == 'ubuntu-latest'` in the shared job, or split into
their own always-ubuntu job.

## Reference shape

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-14, windows-latest]  # match release.yml exactly
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        shell: bash  # Windows defaults to pwsh; POSIX-shell steps need this
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with: { components: rustfmt, clippy }
      - uses: Swatinem/rust-cache@v2

      - name: fmt
        if: matrix.os == 'ubuntu-latest'
        run: cargo fmt --all -- --check
      - name: clippy
        if: matrix.os == 'ubuntu-latest'
        run: cargo clippy --workspace --all-targets -- -D warnings

      - name: test
        run: cargo test --workspace --all-targets

      # If the repo has Python bindings, build + test them on every OS
      # in this same matrix too - see the gotchas below before assuming
      # this "just works" on macOS/Windows.
```

Use `macos-14` (Apple Silicon), not the deprecated Intel `macos-13`/
`macos-latest` alias, unless a repo has a specific reason to keep
testing Intel too - match whatever `release.yml` actually builds.

## Known gotchas to bake in proactively

Don't wait to discover these when someone finally flips on Windows/macOS
CI for a repo that's never had it - add them up front for any repo with
Python bindings.

### pyo3 extension-module crates fail to link on macOS

Any crate with pyo3's `extension-module` feature hard-enabled needs
special linker flags on macOS that `maturin` normally supplies at
wheel-build time but a plain `cargo build`/`cargo test` does not. Without
it you get linker errors like `undefined symbols ... _PyExc_AttributeError`.
This is documented in [pyo3's FAQ](https://pyo3.rs/main/faq.html).

We saw pyo3's own automatic detection handle this fine for crates using
an `abi3-pyXX` feature (OpenQBW, OpenQVD, SpecLance all passed clean on
first try), but *not* for a crate building against the full/non-limited
Python API (DICOM-Atlas's `dicom-map-py`, which also uses
`generate-import-lib`) - same pyo3 0.29.0 in both cases, so the
auto-detection is apparently feature-combination-sensitive. Don't rely
on it. Add this to any pyo3 crate's repo root:

```toml
# .cargo/config.toml
[target.x86_64-apple-darwin]
rustflags = ["-C", "link-arg=-undefined", "-C", "link-arg=dynamic_lookup"]
[target.aarch64-apple-darwin]
rustflags = ["-C", "link-arg=-undefined", "-C", "link-arg=dynamic_lookup"]
```

### Windows' default text encoding is not UTF-8

Python's `subprocess.run(text=True)` and `Path.read_text()` decode using
the platform default encoding, which on Windows is the `cp1252` locale
codec, not UTF-8. Any subprocess stdout or data file containing a
non-ASCII byte raises `UnicodeDecodeError` - hit this in a Rust-CLI
round-trip test reading DICOM tag names on Windows. Always pass
`encoding="utf-8"` explicitly in both cases; never rely on the platform
default.

### Windows binaries need `.exe`

Test scripts that shell out to a workspace-built binary
(`target/release/some-tool`) need to account for the `.exe` suffix on
Windows, or they'll report the binary as missing even though it built
fine.

### Windows shell defaults to pwsh

`windows-latest` runners default to PowerShell, not bash. Any step
written with POSIX syntax (heredocs, `.`-sourcing a venv activate
script, glob expansion) needs `shell: bash` set explicitly - either
per-step or via a job-level `defaults.run.shell: bash` (Git for Windows
ships a real bash, so this works uniformly across all three OSes).

### Platform-specific tooling in a step (gcc/mingw/etc)

If a step assumes a Linux-only toolchain (e.g. a raw `gcc`-based C FFI
smoke test using `.so`/`LD_LIBRARY_PATH`), it's fine to gate it
`if: runner.os == 'Linux'` rather than force a full three-OS port in
the same change - just say so in a comment, and track the portability
work separately if it's worth doing.

## Current compliance (surveyed 2026-07-19)

| Repo | Tests on | Ships for | Status |
|---|---|---|---|
| OpenTFRaw, OpenTimsTDF, OpenQVD, OpenQBW, SpecLance, DICOM-Atlas | ubuntu + macos + windows | same | matches |
| OpenARaw, OpenSXRaw, OpenSZRaw | ubuntu + macos | ubuntu + macos + windows | gap - no Windows test job |
| OpenMassSpec | ubuntu + macos | ubuntu + macos + windows | gap - no Windows test job (Rust *and* Python) |
| SigilYX | ubuntu only | ubuntu + macos + windows | gap - tracked as [SigilYX#23](https://github.com/Sigilweaver/SigilYX/issues/23) |
| OpenYXDB | ubuntu only (pixi/C++ toolchain, not cargo) | linux + macos + windows | gap - different toolchain, the pyo3-specific fixes above don't apply |
| OpenKSpace, GenoLance | ubuntu (+macos for OpenKSpace) | crates.io only, no wheels | no gap - nothing platform-specific ships |

Gap issues are tracked per-repo and linked from
[`BACKLOG.md`](BACKLOG.md#2-real-ci-coverage-cross-cutting); this doc is
the standard they're measured against, update it if the standard
changes rather than re-litigating it per-issue.
