# Supported platforms

These projects have one maintainer, and they are better for the people who report problems, share findings and send
fixes. This page gives the rules I work to when I choose what to build and test. It is not a guarantee, and not every
project follows every rule yet. I want the projects to work in as many places as is reasonable, and everything below
is best effort.

When a project cannot follow a rule on this page (a dependency needs a newer floor, a CI runner goes away), I say so
in that project: the exception and its reason go in its CHANGELOG and its Known issues section. If something outside
this page breaks for you, open an issue. A reproduction on public data helps.

## Rules

**Python.** I support the CPython versions the Python core team still supports, plus the most recently ended version
for six months after its end of life. On Nov 20 2026 that is 3.11 to 3.15, and 3.10 until Mar 31 2027. CI runs the
oldest and the newest supported version on Linux, and the newest on macOS and Windows. Rust packages with Python
bindings ship one abi3 wheel per platform, built for the oldest supported version.

**Rust.** Each crate declares `rust-version` in `Cargo.toml` and CI checks it with a build on that exact toolchain. The
declared version is what the dependencies need, and I avoid requiring a release less than six months old. CI
otherwise runs on current stable. Older toolchains are not supported.

**Node.** Node is a build tool here (documentation sites and Loom Studio), not something users run. I support the
Node LTS lines that are Active or in Maintenance. On Nov 20 2026 that is 22, 24 and 26. `engines` in each
`package.json` lists them, CI uses the oldest.

**Operating systems.** I test on the GitHub-hosted `ubuntu-latest`, `windows-latest` and `macos-latest` images. Wheels
and binaries are built for:

- Linux x86_64 and aarch64 (glibc, manylinux)
- macOS arm64, and macOS x86_64 for as long as GitHub offers an Intel runner
- Windows x86_64

Linux aarch64 and macOS Intel builds are cross-built or run on a different image than they target and are tested
less. Not built: musl/Alpine, Windows on ARM, 32-bit anything. Where a runner image lacks a toolchain I need, I pin the
previous image for that one job and remove the pin when the image catches up.

## Raising a floor

- I review floors twice a year, in October (after the new Python release and Node LTS) and April.
- A Python floor moves when the version has been end of life for six months. A Rust floor moves when a dependency or
  a language feature needs it. A Node floor moves when the version leaves Maintenance.
- A Python floor raise ships in a minor release of the project, never in a patch release, and is the first item in
  the CHANGELOG under "Changed". A Rust floor raise is listed in the CHANGELOG and changes the README badge.
- Older releases stay available for older toolchains: pip selects the last release that supports your interpreter,
  and cargo does the same when its MSRV-aware resolver is on. I do not backport fixes to those releases except for
  security issues I judge serious.
- For the projects it covers, [STABILITY.md](STABILITY.md) says which kind of release a change needs.

## Where the numbers live

The numbers are in `pyproject.toml`, `Cargo.toml`, `package.json` and the CI matrix, and nowhere else by hand. The
versions named on this page are a snapshot for the date given. READMEs link to this page instead of repeating
versions, apart from badges generated from the manifest. Where a project and this page disagree, the project is right.
