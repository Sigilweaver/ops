# Sigilweaver ops

Cross-repo operational glue for the [Sigilweaver](https://github.com/Sigilweaver)
project suite. This repository is intentionally small: it tracks only the
files that coordinate releases and version state across every per-project
repo, not the projects themselves.

## What lives here

| Path | Purpose |
| --- | --- |
| [`versions.toml`](versions.toml) | Single source of truth for the currently published version of every Sigilweaver crate, Python package, and supporting repository. Updated as part of each release. |
| [`BACKLOG.md`](BACKLOG.md) | Suite-level view of what's worth doing next across the projects, grouped by theme and linked to the per-repo GitHub issues. Start here to pick up work. |
| [`release.toml.template`](release.toml.template) | `cargo-release` configuration template for Sigilweaver Rust workspaces. Copy to a repo root as `release.toml` to opt into coordinated release behavior. |
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
2. Run `scripts/check-versions.sh` (expects sibling project clones to exist
   on disk) to confirm the new value matches the project's manifest.
3. Commit and push.

## License

Apache-2.0.
