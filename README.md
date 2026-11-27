# Sigilweaver ops

Cross-repo operational glue for the [Sigilweaver](https://github.com/Sigilweaver)
project suite. This repository is intentionally small: it tracks only the
files that coordinate releases and version state across every per-project
repo, not the projects themselves.

## What lives here

| Path | Purpose |
| --- | --- |
| [`versions.toml`](versions.toml) | Single source of truth for the currently published version of every Sigilweaver crate, Python package, and supporting repository. Updated as part of each release. |
| [`CI_STANDARDS.md`](CI_STANDARDS.md) | What every repo's CI should look like (test-matrix-mirrors-what-you-ship, lint once on Linux) and the platform-specific gotchas to bake in proactively. Gap issues in individual repos link back here. |
| [`DOCS_MAINTENANCE.md`](DOCS_MAINTENANCE.md) | Shared docs generation and output checks, pinned CI integration, and the mechanical rollout command. |
| [`PROVENANCE.md`](PROVENANCE.md) | Where the vendor-format readers may get format knowledge, what may be cross-checked against vendor software, and how sources are recorded. |
| [`STABILITY.md`](STABILITY.md) | What counts as a breaking change for the mass-spec crates and Python packages, and the rules that keep breaking releases rare. |
| [`SUPPORT.md`](SUPPORT.md) | Which Python, Rust and Node versions and which operating systems the Sigilweaver projects build and test for, and how those floors are raised. |
| [`scripts/check-versions.sh`](scripts/check-versions.sh) | Verifies each per-project repo's `Cargo.toml` / `pyproject.toml` matches the value recorded in `versions.toml`. |

## What does not live here

The actual project repositories (OpenMassSpec, OpenQBW, DICOM-Atlas, etc.) are
their own GitHub repositories under the Sigilweaver organisation. This repo
does not vendor or submodule them. Local developer workspaces typically
clone the project repos as sibling directories next to this one; the
`.gitignore` here is allow-listed so those sibling clones never appear as
untracked changes.

The org profile and shared Actions workflows live in
[`Sigilweaver/.github`](https://github.com/Sigilweaver/.github), separate
from this ops repo.

## Updating versions.toml

When a project releases a new version:

1. Edit the relevant `[<group>.<project>]` table in `versions.toml`.
2. Run `scripts/check-versions.sh` to confirm the new value matches the
   project's manifest. It expects the project clones to sit next to this
   repo (one directory per repo); point it elsewhere with `--root DIR` or
   `SIGILWEAVER_ROOT=DIR`. Add `--remote` to also compare against the
   versions published on crates.io and PyPI. Exit status: 0 in sync,
   1 drift, 2 something could not be checked (missing repo, unreadable
   manifest, or no versions found). Mark anything not yet on a registry
   `status = "unpublished"` (whole entry) or `<prefix>_status = "unpublished"`
   (one crate, e.g. `cli_status`); `--remote` skips those.
3. Commit and push.

## License

Apache-2.0.
