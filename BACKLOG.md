# Sigilweaver suite backlog

Cross-repo view of what's worth doing next across the Sigilweaver
projects. Concrete, per-repo work lives in GitHub issues (linked below);
this file is the suite-level overview that survives across work sessions.
Start here, then open the linked issues for detail.

Maintenance: when an issue is opened, closed, or reprioritized, update the
matching line here. Cross-cutting themes that don't map to a single repo
issue are tracked directly in this file until they do.

---

## 1. Security / robustness hardening (highest)

The readers all parse untrusted binary input with hand-rolled bounds
checks; harden them as a family, not one at a time.

- **Loom dependency exposure (urgent).** 15+ open Dependabot alerts ship in
  Docker images and the desktop binary; the dead `python-jose`/`pyjwt`
  removal is a clean win that clears the one unfixable `ecdsa` alert.
  - [Loom#1](https://github.com/Sigilweaver/Loom/issues/1) - update vulnerable pinned deps
  - [Loom#2](https://github.com/Sigilweaver/Loom/issues/2) - dep-vuln gate + dependabot.yml + pre-release banner
- **Fuzzing + allocation caps across the reader family.** Allocations sized
  from file-controlled `u32`s (memory-DoS) and no fuzz harnesses over the
  decode paths.
  - [OpenARaw#1](https://github.com/Sigilweaver/OpenARaw/issues/1) - cap untrusted allocations
  - [OpenSXRaw#1](https://github.com/Sigilweaver/OpenSXRaw/issues/1) - bound read_scan_block + fix no-op cap
  - [SigilYX#24](https://github.com/Sigilweaver/SigilYX/issues/24) - fuzz harness over the YXDB parse path
  - Extend the same fuzz treatment to opentfraw / opentimstdf / openwraw (no issue yet).
- **Standardize a `cargo audit` / dependency-vuln CI job across the org.**
  Done for openaraw and opensxraw (2026-07-11); Loom still lacks one
  (tracked separately as a Python dep gate, [Loom#2](https://github.com/Sigilweaver/Loom/issues/2)).

## 2. Real CI coverage (cross-cutting)

Every reader's conformance tests currently *skip* on CI because the corpus
is out of tree, so decode paths aren't exercised anywhere automated. This
is the biggest confidence gap in the suite.

- Check in a small curated fixture corpus (or fetch via the existing
  `fetch_corpus.py`) so conformance runs for real on CI. Affects all
  readers. (No single issue yet - suite-wide.)
- [OpenARaw#2](https://github.com/Sigilweaver/OpenARaw/issues/2) / [OpenSXRaw#2](https://github.com/Sigilweaver/OpenSXRaw/issues/2) - byte-slice decoder unit tests (corpus-free coverage)
- [SigilYX#23](https://github.com/Sigilweaver/SigilYX/issues/23) - test the macOS/Windows platforms it ships wheels for

## 3. Reach / packaging

- [OpenMassSpec#2](https://github.com/Sigilweaver/OpenMassSpec/issues/2) - conda-forge feedstock for openmassspec-io + openmassspec (RELEASING.md documents the SOP; never done).
- **Zenodo / DOI reconciliation.** The OpenProteo -> OpenMassSpec rename may
  have left stale record titles; mint DOIs for the newly published openaraw
  / opensxraw. Manual (web UI). (No issue - not code.)

## 4. Feature depth (bigger, later)

- [OpenMassSpec#3](https://github.com/Sigilweaver/OpenMassSpec/issues/3) - streaming ingest (don't buffer a whole run in a Vec; a real .wiff hit ~1.15 GB).
- [OpenSXRaw#3](https://github.com/Sigilweaver/OpenSXRaw/issues/3) - decode m/z calibration + MS2 precursor m/z (the two known-limitations that gate real analysis use).

## 5. Cleanup / loose ends

- [OpenARaw#3](https://github.com/Sigilweaver/OpenARaw/issues/3) - remove dead parsers, document always-empty spectrum fields.
- Standardize a tag/version-match guard across release workflows so a
  mistagged release can't publish. (No issue yet - small, cross-cutting.)

---

## Done recently (for context)

- OpenProteo -> OpenMassSpec / OpenProteoCore -> OpenMassSpecCore rename,
  fully executed (repos, crates, PyPI, docs, DOI-bearing packages).
- OpenMassSpec 1.1.0: umbrella now covers all five vendors (Thermo, Bruker,
  Waters, Agilent, SCIEX) after publishing openaraw (crates.io + PyPI) and
  opensxraw (crates.io) at 0.1.0.
- Org-level community health files (issue/PR templates, SUPPORT.md).
- Security batch (2026-07-11): released OpenARaw 0.1.1 (pyo3 0.29 + MSScan
  panic-guard, published crates.io + PyPI); upgraded OpenTFRaw and
  OpenTimsTDF pyo3+numpy 0.22 -> 0.29, clearing RUSTSEC-2025-0020 /
  RUSTSEC-2026-0177 and closing OpenTFRaw#20 + OpenTimsTDF#1 (audit ignores
  dropped). The two upgrades are on main but UNRELEASED - published
  crates/wheels still carry 0.22 until a TFRaw 1.3.2 / TimsTDF 1.2.4 cut.
- OpenARaw / OpenSXRaw brought up to the OpenTFRaw maturity standard
  (2026-07-11): `cargo audit` + Docusaurus deploy CI jobs, OpenSXRaw Python
  bindings (`opensxraw-py` + PyPI publish), OpenARaw pyo3 0.28->0.29 (clears
  RUSTSEC-2026-0176/0177), docs guide gaps filled, and both wired into the
  Website hub. OpenSXRaw's PyPI publish lands with its next tagged release.
