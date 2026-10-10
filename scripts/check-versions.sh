#!/usr/bin/env bash
# check-versions.sh
#
# Reads Ops/versions.toml and verifies that every version recorded there
# matches the manifests in the sibling project checkouts:
#
#   crates_version         vs  Cargo.toml of `crate`
#   <x>_version            vs  Cargo.toml of `<x>_crate` (cli_version, ms_version, ...)
#   pypi_version           vs  pyproject.toml whose [project].name is `pypi`
#                              (static version, or maturin dynamic version
#                              read from the Cargo manifest it builds)
#
# Crate versions resolve `version.workspace = true` against the workspace
# root. Cargo pre-release versions are normalized to PEP 440 for PyPI
# comparisons (0.2.0-alpha -> 0.2.0a0).
#
# Usage:
#   scripts/check-versions.sh [--root DIR] [--remote]
#
#   --root DIR   Directory containing the project checkouts (one directory
#                per repo, named after the repo, e.g. DIR/OpenMassSpec).
#                Default: $SIGILWEAVER_ROOT, else the parent of this Ops repo.
#   --remote     Also compare versions.toml against the latest versions
#                published on crates.io and PyPI (read-only HTTP GETs).
#
# Exit status: 0 all in sync, 1 drift found, 2 missing repo/manifest or
# configuration error. Requires python3 >= 3.11 (tomllib); --remote needs curl.

set -euo pipefail

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS="$OPS_DIR/versions.toml"
ROOT="${SIGILWEAVER_ROOT:-$(dirname "$OPS_DIR")}"
REMOTE=0

usage() { sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) [[ $# -ge 2 ]] || { echo "fatal: --root needs a value" >&2; exit 2; }
            ROOT="$2"; shift 2 ;;
    --root=*) ROOT="${1#--root=}"; shift ;;
    --remote) REMOTE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "fatal: unknown argument: $1 (see --help)" >&2; exit 2 ;;
  esac
done

if [[ ! -f "$VERSIONS" ]]; then
  echo "fatal: $VERSIONS not found" >&2
  exit 2
fi
if [[ ! -d "$ROOT" ]]; then
  echo "fatal: root directory $ROOT not found (set --root or SIGILWEAVER_ROOT)" >&2
  exit 2
fi
ROOT="$(cd "$ROOT" && pwd)"

exec python3 - "$ROOT" "$VERSIONS" "$REMOTE" <<'PYEOF'
import json, os, re, subprocess, sys, tomllib
from pathlib import Path

root = Path(sys.argv[1])
versions_path = Path(sys.argv[2])
remote = sys.argv[3] == "1"

with versions_path.open("rb") as f:
    versions = tomllib.load(f)

SKIP_DIRS = {".git", "target", "node_modules", ".venv", "venv", ".pixi",
             ".untracked", "__pycache__", ".tox"}
UA = "sigilweaver-ops-check-versions (https://github.com/Sigilweaver/Ops)"

stats = {"checked": 0, "drift": 0, "missing": 0}

def report(kind, label, msg):
    if kind == "ok":
        stats["checked"] += 1
        print(f"  ok {label}: {msg}")
    elif kind == "drift":
        stats["checked"] += 1
        stats["drift"] += 1
        print(f"  !! {label}: {msg}")
    else:
        stats["missing"] += 1
        print(f"  ?? {label}: {msg}")

def load_toml(path):
    with path.open("rb") as f:
        return tomllib.load(f)

def manifests(repo_dir, filename):
    """Tracked manifests (git ls-files) or a filtered walk if not a git repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_dir), "ls-files", "--", filename, f"*/{filename}"],
            capture_output=True, text=True, check=True).stdout.split()
        if out:
            return sorted(repo_dir / p for p in out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    found = []
    for dirpath, dirnames, filenames in os.walk(repo_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if filename in filenames:
            found.append(Path(dirpath) / filename)
    return sorted(found)

def workspace_root_version(cargo_path, repo_dir):
    d = cargo_path.parent
    while True:
        cand = d / "Cargo.toml"
        if cand.exists():
            data = load_toml(cand)
            if "workspace" in data:
                return data["workspace"].get("package", {}).get("version")
        if d == repo_dir or d == d.parent:
            return None
        d = d.parent

def cargo_package_version(cargo_path, repo_dir):
    pkg = load_toml(cargo_path).get("package", {})
    v = pkg.get("version")
    if isinstance(v, dict) and v.get("workspace"):
        return workspace_root_version(cargo_path, repo_dir)
    return v

def find_crate(repo_dir, crate):
    for m in manifests(repo_dir, "Cargo.toml"):
        try:
            pkg = load_toml(m).get("package", {})
        except tomllib.TOMLDecodeError:
            continue
        if pkg.get("name") == crate:
            return m, cargo_package_version(m, repo_dir)
    return None, None

def norm_name(n):
    return re.sub(r"[-_.]+", "-", n).lower()

def pep440(v):
    """Normalize a Cargo/semver version the way maturin does (subset)."""
    if v is None:
        return None
    m = re.fullmatch(r"(\d+(?:\.\d+)*)(?:-(alpha|beta|rc|a|b)\.?(\d+)?)?", v)
    if not m:
        return v
    base, pre, num = m.groups()
    if not pre:
        return base
    tag = {"alpha": "a", "a": "a", "beta": "b", "b": "b", "rc": "rc"}[pre]
    return f"{base}{tag}{num or 0}"

def find_pypi(repo_dir, name):
    for m in manifests(repo_dir, "pyproject.toml"):
        try:
            data = load_toml(m)
        except tomllib.TOMLDecodeError:
            continue
        proj = data.get("project", {})
        if norm_name(proj.get("name", "")) != norm_name(name):
            continue
        if "version" in proj:
            return m, proj["version"], None
        if "version" in proj.get("dynamic", []):
            mp = data.get("tool", {}).get("maturin", {}).get("manifest-path", "Cargo.toml")
            cargo = (m.parent / mp).resolve()
            if not cargo.exists():
                return m, None, f"maturin manifest {cargo} missing"
            return m, pep440(cargo_package_version(cargo, repo_dir)), None
        return m, None, "no static or dynamic version"
    return None, None, None

def rel(p):
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)

def check_crate(label, repo_dir, crate, want):
    if not crate:
        report("missing", label, "version recorded but no crate name")
        return
    path, have = find_crate(repo_dir, crate)
    if path is None:
        report("missing", label, f"crate {crate} not found in {rel(repo_dir)}")
    elif have is None:
        report("missing", label, f"no version in {rel(path)}")
    elif have == want:
        report("ok", label, have)
    else:
        report("drift", label, f"manifest {have}, versions.toml {want}  ({rel(path)})")

def check_pypi(label, repo_dir, name, want):
    if not name:
        report("missing", label, "pypi_version recorded but no pypi name")
        return
    path, have, err = find_pypi(repo_dir, name)
    if path is None:
        report("missing", label, f"no pyproject.toml with name {name} in {rel(repo_dir)}")
    elif have is None:
        report("missing", label, f"{err} ({rel(path)})")
    elif pep440(have) == pep440(want):
        report("ok", label, have)
    else:
        report("drift", label, f"manifest {have}, versions.toml {want}  ({rel(path)})")

def http_json(url):
    try:
        out = subprocess.run(["curl", "-sL", "--max-time", "20", "-A", UA,
                              "-w", "\n%{http_code}", url],
                             capture_output=True, text=True)
    except FileNotFoundError:
        return None, "curl not found"
    if out.returncode != 0:
        return None, f"GET failed (curl exit {out.returncode})"
    body, _, code = out.stdout.rpartition("\n")
    if code == "404":
        return None, "404"
    if code != "200":
        return None, f"GET failed (HTTP {code})"
    try:
        return json.loads(body), None
    except json.JSONDecodeError:
        return None, "bad JSON"

def check_remote_crate(label, crate, want):
    data, err = http_json(f"https://crates.io/api/v1/crates/{crate}")
    if err == "404":
        report("drift", label, f"not published on crates.io, versions.toml {want}")
        return
    if err:
        report("missing", label, f"crates.io {crate}: {err}")
        return
    c = data.get("crate", {})
    have = c.get("max_stable_version") or c.get("max_version")
    if "-" in want:
        have = c.get("max_version") or have
    if have == want:
        report("ok", label, f"crates.io {have}")
    else:
        report("drift", label, f"crates.io {have}, versions.toml {want}")

def check_remote_pypi(label, name, want):
    data, err = http_json(f"https://pypi.org/pypi/{name}/json")
    if err == "404":
        report("drift", label, f"not published on PyPI, versions.toml {want}")
        return
    if err:
        report("missing", label, f"PyPI {name}: {err}")
        return
    have = data.get("info", {}).get("version")
    if pep440(have) == pep440(want):
        report("ok", label, f"PyPI {have}")
    else:
        report("drift", label, f"PyPI {have}, versions.toml {want}")

def branch(repo_dir):
    try:
        b = subprocess.run(["git", "-C", str(repo_dir), "branch", "--show-current"],
                           capture_output=True, text=True).stdout.strip()
        return b or "detached"
    except FileNotFoundError:
        return "?"

print(f"root: {root}")
for section in ("mass_spectrometry", "formats", "scientific"):
    if section not in versions:
        continue
    print(f"\n== {section} ==")
    for name, info in versions[section].items():
        if not isinstance(info, dict):
            continue
        fields = [k for k in info if k.endswith("_version")]
        if not fields:
            continue
        repo = info.get("repo")
        if not repo:
            report("missing", name, "no repo recorded")
            continue
        repo_dir = root / repo.split("/")[-1]
        if not repo_dir.is_dir():
            report("missing", name, f"repo checkout {rel(repo_dir)} not found")
            continue
        print(f" {name} [{repo_dir.name} @ {branch(repo_dir)}]")
        unpublished = info.get("status") == "unpublished"
        for key in fields:
            want = info[key]
            if key == "crates_version":
                crate = info.get("crate")
                check_crate(f"{name} crate {crate}", repo_dir, crate, want)
                if remote and crate and not unpublished:
                    check_remote_crate(f"{name} crate {crate}", crate, want)
            elif key == "pypi_version":
                pkg = info.get("pypi")
                check_pypi(f"{name} pypi {pkg}", repo_dir, pkg, want)
                if remote and pkg and not unpublished:
                    check_remote_pypi(f"{name} pypi {pkg}", pkg, want)
            else:
                prefix = key[: -len("_version")]
                crate = info.get(f"{prefix}_crate")
                check_crate(f"{name} {prefix} crate {crate}", repo_dir, crate, want)
                if remote and crate and not unpublished:
                    check_remote_crate(f"{name} {prefix} crate {crate}", crate, want)

print()
print(f"checked: {stats['checked']}, drift: {stats['drift']}, missing: {stats['missing']}")
if stats["missing"]:
    sys.exit(2)
sys.exit(1 if stats["drift"] else 0)
PYEOF
