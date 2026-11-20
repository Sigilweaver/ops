# Format provenance policy

This page covers every Sigilweaver project that reads a proprietary file
format: the mass-spec readers (OpenTFRaw, OpenWRaw, OpenTimsTDF, OpenARaw,
OpenSXRaw, OpenSZRaw), OpenSQLAnywhere, OpenQBW, OpenYXDB, and any reader
added later. Each project's CONTRIBUTING.md points here.

Every format layout in these projects should be explainable from public
bytes or public sources, and each project should say plainly where a value came from.

## What I accept

- Public files and public documentation, including every file inside a
  public bundle (PRIDE, MassIVE, MetaboLights and similar archives).
- Byte-level analysis of files you own or that are public.
- Other open-source readers, cited by name, version and license. I take
  facts from them, not their code, unless the license allows it and the
  copy is credited.
- Comparison against output the vendor has already published.
- A black-box comparison against vendor software you are licensed to run,
  as a cross-check only. It can confirm a decoder. It is never the only
  basis for a value, and the layout must be explainable from public data.
  Vendor software is never a dependency and never runs in CI or tests.

## What I decline, regardless of who did the work

- Anything that came from decompiling, disassembling, debugging or tracing
  vendor software or libraries. This includes watching it run through a
  database engine, an ODBC driver or a hook.
  Comparing the output it produces is a cross-check (see above);
  observing its internals is declined.
- Vendor source code, SDK headers, and leaked or confidential documents.
- Anything that bypasses encryption, licence checks or other protection.
- Knowledge from people working from vendor-internal information.

## What every PR or issue that adds format knowledge includes

1. A one or two line method statement: what you looked at and how you
   reached the finding.
2. Your answer to: "Was any vendor software, library or binary involved
   beyond the program that created the file?" If yes, say what it was used
   for.

For a cross-check, also name the tool, the files and what was compared. Do
not paste vendor-tool output into the repository.

## What happens to material I decline

I close it with a link to this page and do not use it. If the underlying
fact matters, I re-derive it from public files and cite those. I do not ask
anyone to do anything on the decline list, and I do not ask for raw files:
public data is used for reproductions.

## Records

- Each project records its sources (in ATTRIBUTION.md where it has one) and
  notes any value cross-checked against vendor software. If a value's only basis is such a
  comparison, its documentation says so next to the value.
- Code comments that cite a source name a public source this page accepts.
  A claim with no such source is reworded or removed.
- Corrections go in new commits, ATTRIBUTION.md or CHANGELOG.md.

## Why

Each reader has to stay defensible for everyone who depends on it. I cannot
verify or defend work derived from vendor code, so I do not take it,
however good it is. Readers live in separate repositories, so a problem
with one does not touch the others.

## Reply text

> Thank you for the work and for sharing it. I can't merge this: it relies
> on material I don't accept under the project's
> [provenance policy](https://github.com/Sigilweaver/ops/blob/main/PROVENANCE.md),
> and I can't verify where it came from, so I won't use it. If the fact
> matters I will re-derive it from public files and credit those. A short
> method statement and the vendor-software answer described on that page
> help on any future PR or issue.
