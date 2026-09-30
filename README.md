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
| [`CI_STANDARDS.md`](CI_STANDARDS.md) | What every repo's CI should look like (test-matrix-mirrors-what-you-ship, lint once on Linux) and the platform-specific gotchas to bake in proactively. Gap issues in individual repos link back here. |
| [`release.toml.template`](release.toml.template) | `cargo-release` configuration template for Sigilweaver Rust workspaces. Copy to a repo root as `release.toml` to opt into coordinated release behavior. |
| [`scripts/check-versions.sh`](scripts/check-versions.sh) | Verifies each per-project repo's `Cargo.toml` / `pyproject.toml` matches the value recorded in `versions.toml`. |
| [`scripts/org_work.py`](scripts/org_work.py) | Pulls the whole org's issues, PRs, checks, reviews and recent branch work into a searchable local queue. Keeps ownership and next-action notes across refreshes. |

## Org work queue

Requires Python 3.10+ and an authenticated GitHub CLI account with access to
the organization. Run from this repository:

```sh
python3 scripts/org_work.py sync
```

Open `.work/queue.html` for a searchable view, or read `.work/queue.md`.
The sync covers every accessible org repository, including private,
archived and uncloned repositories. Repository, issue, PR and branch
connections are paginated. Recent non-bot branches without an open PR are
compared with their default branch, so cloud-session work is visible too.
The default branch window is 14 days; change it with `--branch-days`.
Locally tracked branches stay included while their work state is not done,
even if their last commit falls outside that window.

Reports distinguish human PRs, contributor reports, security work and
dependency maintenance. Suggested priorities come from titles, labels and
author identity; they are a starting point for triage. Reports flag merge
conflicts, missing checks, partial check evidence and passing checks older
than seven days, or checks without usable completion dates. Reports
evaluate freshness when rendered, not only when synced. Passing checks
never imply approval to merge. Inspect
the patch and obtain fresh audits before acting on old green results.

Keep the next action and investigator with the work item:

```sh
python3 scripts/org_work.py track 'Sigilweaver/OpenTFRaw#57' \
  --status investigating --owner source-cid --priority 2 \
  --note 'Investigate per-event method linkage and add a raw-file regression.'
python3 scripts/org_work.py track 'Sigilweaver/OpenQBW#20' \
  --status review --note 'Check duplicate ordinals and obtain CI evidence.'
python3 scripts/org_work.py report
```

These commands update local state only. Sync never posts, assigns, closes,
reviews or merges GitHub work and never changes local checkouts. Refresh
preserves local notes and flags PR or branch heads that changed since the
local review. Snapshot differences list new, updated and no-longer-open
items. Failed repository reads are reported and do not imply closure.
Previously seen repositories that disappear from the org listing retain their
cached work with a visible warning. Reports distinguish known repositories from
the current accessible listing, so losing access cannot silently hide work.

`.work/` is ignored by Git, and generated files have owner-only permissions.
It can contain private issue bodies and discussions. Keep it local. A
separate `--data-dir` can be used for another org; pass global options
before the subcommand. The HTML report is self-contained and makes no
network requests. Discussion context is the last 10 comments and reviews;
check contexts beyond the first 100 are explicitly marked incomplete.

Run the meaningful offline regression checks:

```sh
python3 -m unittest discover -s scripts -p 'test_org_work.py'
```

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
