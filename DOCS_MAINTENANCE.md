# Docs maintenance

The Docusaurus projects share one generator and validator, maintained in
`scripts/docs_output.py`. Local builds use an identical generated copy in
`docs/scripts/docs_output.py`; the reusable CI workflow verifies that copy
against the exact ops commit pinned by the calling repository.

This keeps local builds and deployment builds useful without fetching tools
from the network during a build. Docusaurus remains responsible for content,
navigation, HTML, and the sitemap. The shared script derives the site name
and public routes from that built output, generates `llms.txt`, and verifies:

- Every sitemap page exists and has a matching canonical URL and a title.
- Every rendered link within the site's base path resolves to a built page
  or asset, and every HTML fragment exists.
- The generated index has the correct title and links exactly once to every
  sitemap page, with no empty targets.

Other project sites, external services, and technical accuracy of the prose
remain outside this automated check. The script requires Python 3.10 or later.

## Update a project

Use a clean isolated checkout, and select the exact tested ops commit:

```sh
python3 /path/to/ops/scripts/sync_docs.py /path/to/project --tooling-ref <ops-commit>
cd /path/to/project/docs
bun install --lockfile-only --ignore-scripts
bun install --frozen-lockfile
bun run typecheck
bun run build:cloudflare
```

Inspect the diff before committing. The sync script updates the plugin
integration, local build commands, generated tooling copy, and CI reference;
it never publishes anything. Existing deployment workflows remain separate.
If a site's configuration is unusual, the script stops for inspection.

`bun run build` and `bun run build:cloudflare` generate and validate the index.
To validate a previously built artifact without changing it:

```sh
python3 docs/scripts/docs_output.py docs/build
```

## Shared CI

The job uses `.github/workflows/docs.yml`, with both its `uses` reference and
`tooling-ref` input pinned to the same exact commit. It installs the frozen
Bun lockfile, runs the site's existing typecheck command, builds, verifies the
generated tooling copy, checks the output, and uploads the build artifact.
The default Bun version is 1.3.6; a caller can override it deliberately.

Updating the generator is a normal ops PR. Once its tests pass, run the sync
script against each project with the new commit, validate each site's output,
and review the resulting project changes. Dependencies can be updated with
the same build checks, but source explanations and examples still require
project-specific review. Do not suppress output failures to make a rollout
green; fix the document or route that the check identifies.

Run the generator's regression suite from ops:

```sh
python3 -m unittest discover -s scripts -p test_docs_output.py -v
```
