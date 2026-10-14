#!/usr/bin/env python3
"""Apply the shared docs build integration to one clean repository checkout.

Run bun install --lockfile-only --ignore-scripts afterwards, then inspect the
diff and run the build. This script never commits, pushes, opens PRs, or deploys.
"""

import argparse
import json
from pathlib import Path
import re
import shutil


def sync(repo: Path, tooling_ref: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", tooling_ref):
        raise ValueError("tooling-ref must be an exact 40-character ops commit")
    docs = repo / "docs"
    manifest = docs / "package.json"
    text = manifest.read_text(encoding="utf-8")
    package = json.loads(text)
    if "@docusaurus/core" not in package.get("dependencies", {}):
        raise ValueError(f"Not a Docusaurus docs project: {repo}")
    config = docs / "docusaurus.config.ts"
    source = config.read_text(encoding="utf-8")
    source = re.sub(r"^\s*plugins: \[['\"]docusaurus-plugin-llms-txt['\"]\],\n", "\n", source, flags=re.MULTILINE)
    if "docusaurus-plugin-llms-txt" in source:
        raise ValueError(f"Review the nonstandard plugin configuration manually: {config}")
    config.write_text(source, encoding="utf-8")
    package["dependencies"].pop("docusaurus-plugin-llms-txt", None)
    for name in ("build", "build:cloudflare"):
        command = package["scripts"][name]
        if "scripts/docs_output.py" not in command:
            package["scripts"][name] = command + " && python3 scripts/docs_output.py build --write-index"
    first_key = re.search(r'\{\s*\n( +)"', text)
    indent = len(first_key.group(1)) if first_key else 2
    manifest.write_text(json.dumps(package, indent=indent) + "\n", encoding="utf-8")
    (docs / "scripts").mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__).with_name("docs_output.py"), docs / "scripts/docs_output.py")

    job = f"""  docs:
    name: Docs (Docusaurus)
    permissions:
      contents: read
    uses: Sigilweaver/ops/.github/workflows/docs.yml@{tooling_ref}
    with:
      tooling-ref: {tooling_ref}
"""
    ci = repo / ".github/workflows/ci.yml"
    ci_source = ci.read_text(encoding="utf-8") if ci.exists() else ""
    pattern = r"^  docs:\n.*?(?=^  [a-zA-Z0-9_-]+:\n|^  #|\Z)"
    match = re.search(pattern, ci_source, flags=re.MULTILINE | re.DOTALL)
    if match and "steps:" in match.group():
        # The existing standalone docs job has no consumers or deployment.
        if re.search(r"needs:.*\bdocs\b|wrangler|deploy", match.group()):
            raise ValueError(f"Review the deployment docs job manually: {ci}")
        ci.write_text(ci_source[:match.start()] + job + ci_source[match.end():], encoding="utf-8")
    elif match and "Sigilweaver/ops/.github/workflows/docs.yml@" in match.group():
        ci.write_text(ci_source[:match.start()] + job + ci_source[match.end():], encoding="utf-8")
    else:
        workflow = repo / ".github/workflows/docs-quality.yml"
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text("""name: Docs quality

on:
  push:
    branches: [main]
    paths: ["docs/**", ".github/workflows/docs-quality.yml"]
  pull_request:
    paths: ["docs/**", ".github/workflows/docs-quality.yml"]

permissions:
  contents: read

concurrency:
  group: docs-quality-${{ github.ref }}
  cancel-in-progress: true

jobs:
""" + job, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--tooling-ref", required=True)
    args = parser.parse_args()
    sync(args.repo, args.tooling_ref)
    print(f"Updated docs integration in {args.repo}; regenerate and validate the lockfile next.")


if __name__ == "__main__":
    main()
