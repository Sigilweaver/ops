# Format provenance policy

How Sigilweaver vendor-format readers (OpenTFRaw, OpenWRaw, OpenARaw,
OpenTimsTDF, OpenSXRaw, OpenSZRaw) may learn and check what they decode.
Adopted Oct 11, 2026. Each reader's CONTRIBUTING.md points here.

The goal is that every format layout in these readers can be explained
from public bytes or public sources, and that the project says plainly
where any value came from.

## Never

- Vendor code of any kind in the repository or used as a reference:
  SDK headers or sources, decompiled or disassembled binaries, proprietary
  specifications, or confidential documentation.
- Bypassing encryption, licence checks, or any other technical protection
  to read data.
- Format knowledge from anyone working from vendor-internal information.
- Running vendor software in CI or tests, or adding a dependency that
  reads the format through vendor libraries.

## Allowed with disclosure

- A contributor comparing values this project decodes against output from
  vendor software they are licensed to run, as a cross-check.

Conditions:

- The layout itself must be explainable from public data files. A
  comparison may confirm a decoder; it may not be the only basis for one.
- Say so in the pull request: which tool, which files, and what was
  compared. Do not paste vendor-tool output into the repository.
- If a value's only basis is a vendor comparison (for example a derived
  quantity whose formula was matched to vendor output, not taken from a
  public source), its documentation says so.

## Fine

- Public data files (PRIDE, MassIVE, MetaboLights and similar archives),
  including every file inside a public bundle.
- Independent open-source readers and published papers, cited by name and
  version.
- Simple derived quantities and project naming conventions, documented as
  such.

## Records

- Each reader's ATTRIBUTION.md lists its sources, and states when
  contributors have cross-checked values against vendor software.
- Code comments that cite a source name an exact public source this policy
  allows. A claim with no such source is reworded or removed.
- Git history and pull-request text are left as written. Corrections go in
  new commits, ATTRIBUTION.md, or CHANGELOG.md.
