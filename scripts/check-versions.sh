#!/usr/bin/env bash
# check-versions.sh
#
# Walks the workspace, reads /workspaces/Projects/versions.toml, and
# verifies that each declared Cargo.toml/pyproject.toml matches.
#
# Usage:
#   ./scripts/check-versions.sh           # report drift
#   ./scripts/check-versions.sh --fix     # rewrite Cargo.toml/pyproject.toml
#                                         # to match versions.toml (no commit)
#
# Requires: python3 (uses tomllib, stdlib since 3.11).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS="$ROOT/versions.toml"

if [[ ! -f "$VERSIONS" ]]; then
  echo "fatal: $VERSIONS not found" >&2
  exit 2
fi

FIX=0
if [[ "${1:-}" == "--fix" ]]; then
  FIX=1
fi

python3 - "$ROOT" "$VERSIONS" "$FIX" <<'PYEOF'
import sys, re, tomllib
from pathlib import Path

root = Path(sys.argv[1])
versions_path = Path(sys.argv[2])
fix = bool(int(sys.argv[3]))

with versions_path.open("rb") as f:
    versions = tomllib.load(f)

drift = 0
checked = 0

def find_cargo_toml(repo_name: str) -> Path | None:
    # repo_name like "Sigilweaver/OpenProteo" -> look for OpenProteo/Cargo.toml
    name = repo_name.split("/")[-1]
    candidate = root / name / "Cargo.toml"
    return candidate if candidate.exists() else None

def extract_version(text: str) -> str | None:
    # Try workspace.package version first. Use look-behind to avoid
    # matching `rust-version`.
    m = re.search(r'\[workspace\.package\][^\[]*?(?<![-\w])version\s*=\s*"([^"]+)"', text, re.DOTALL)
    if m:
        return m.group(1)
    # Fall back to first top-level version (e.g. in a per-crate Cargo.toml).
    m = re.search(r'(?m)^(?<![-\w])version\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None

def check_crate(label: str, repo: str, want_version: str, crate: str | None = None) -> None:
    global drift, checked
    cargo = find_cargo_toml(repo)
    if cargo is None:
        print(f"  ?  {label}: no Cargo.toml found for {repo}")
        return
    have = extract_version(cargo.read_text())
    # Fall back to crates/<crate>/Cargo.toml if no top-level version.
    if have is None and crate is not None:
        sub = cargo.parent / "crates" / crate / "Cargo.toml"
        if sub.exists():
            cargo = sub
            have = extract_version(cargo.read_text())
    if have is None:
        print(f"  ?  {label}: no version found in {cargo}")
        return
    checked += 1
    if have == want_version:
        print(f"  ok {label}: {have}")
    else:
        drift += 1
        print(f"  !! {label}: have {have}, want {want_version}  ({cargo})")

for section in ("proteomics", "formats", "scientific"):
    if section not in versions:
        continue
    print(f"== {section} ==")
    for name, info in versions[section].items():
        repo = info.get("repo")
        if "crates_version" in info and repo:
            check_crate(f"{name} (crate)", repo, info["crates_version"], info.get("crate"))

print()
print(f"checked: {checked}, drift: {drift}")
sys.exit(1 if drift else 0)
PYEOF
