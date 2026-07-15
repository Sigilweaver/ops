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

- **Fuzzing + allocation caps across the reader family.** Allocations sized
  from file-controlled `u32`s (memory-DoS) and no fuzz harnesses over the
  decode paths.
  - [OpenARaw#1](https://github.com/Sigilweaver/OpenARaw/issues/1) - cap untrusted allocations
  - [OpenSXRaw#1](https://github.com/Sigilweaver/OpenSXRaw/issues/1) - bound read_scan_block + fix no-op cap
  - [SigilYX#24](https://github.com/Sigilweaver/SigilYX/issues/24) - fuzz harness over the YXDB parse path
  - [OpenWRaw#3](https://github.com/Sigilweaver/OpenWRaw/issues/3) - cap untrusted allocations + fuzz harness (~71 unwraps, 16 unbounded allocs)
  - [OpenKSpace#1](https://github.com/Sigilweaver/OpenKSpace/issues/1) - cap ISMRMRD header-sized allocations (`ns * nc`)
  - [OpenQVD#1](https://github.com/Sigilweaver/OpenQVD/issues/1) - cap QVD length-field allocations (`no_of_symbols`, `n_rows`)
  - Extend the same fuzz treatment to opentfraw / opentimstdf (no issue yet).
- **`cargo audit` CI job standardized across every Rust repo (done 2026-07-11).**
  The rollout surfaced a real suite-wide vuln surface. Cleared by lockfile
  bump: genolance, openkspace (crossbeam-epoch/quinn-proto/rustls-webpki).
  Clean already: opensqlanywhere, openmassspeccore. The rest ignore genuine
  upgrade-needed advisories (kept green) with per-repo tracking issues:
  - **pyo3 -> 0.29** (same migration as OpenTFRaw#20 / OpenTimsTDF#1):
    [DICOM-Atlas#3](https://github.com/Sigilweaver/DICOM-Atlas/issues/3),
    [OpenQBW#2](https://github.com/Sigilweaver/OpenQBW/issues/2),
    [OpenQVD#4](https://github.com/Sigilweaver/OpenQVD/issues/4),
    [SpecLance#3](https://github.com/Sigilweaver/SpecLance/issues/3),
    [OpenMassSpec#4](https://github.com/Sigilweaver/OpenMassSpec/issues/4),
    [SigilYX#26](https://github.com/Sigilweaver/SigilYX/issues/26)
  - **quick-xml -> 0.41** (breaking API bump): [OpenKSpace#2](https://github.com/Sigilweaver/OpenKSpace/issues/2), plus the four pyo3+quick-xml issues above (OpenQVD/SpecLance/OpenMassSpec/SigilYX).
  - Loom is a separate Python dep gate, [Loom#2](https://github.com/Sigilweaver/Loom/issues/2).

## 2. Real CI coverage (cross-cutting)

Every reader's conformance tests currently *skip* on CI because the corpus
is out of tree, so decode paths aren't exercised anywhere automated. This
is the biggest confidence gap in the suite.

- Check in a small curated fixture corpus (or fetch via the existing
  `fetch_corpus.py`) so conformance runs for real on CI. Affects all
  readers. (No single issue yet - suite-wide.)
- [OpenARaw#2](https://github.com/Sigilweaver/OpenARaw/issues/2) / [OpenSXRaw#2](https://github.com/Sigilweaver/OpenSXRaw/issues/2) - byte-slice decoder unit tests (corpus-free coverage)
- [GenoLance#1](https://github.com/Sigilweaver/GenoLance/issues/1) - **no unit tests at all**; CI runs `cargo test` over an empty set
- **Windows/macOS test-matrix gap** (ships wheels, tests only Linux): [SigilYX#23](https://github.com/Sigilweaver/SigilYX/issues/23), [OpenWRaw#2](https://github.com/Sigilweaver/OpenWRaw/issues/2), [OpenTimsTDF#2](https://github.com/Sigilweaver/OpenTimsTDF/issues/2), [OpenQVD#2](https://github.com/Sigilweaver/OpenQVD/issues/2), [DICOM-Atlas#1](https://github.com/Sigilweaver/DICOM-Atlas/issues/1), [SpecLance#1](https://github.com/Sigilweaver/SpecLance/issues/1)

## 3. Reach / packaging

- [OpenMassSpec#2](https://github.com/Sigilweaver/OpenMassSpec/issues/2) - conda-forge feedstock for openmassspec-io + openmassspec (RELEASING.md documents the SOP). `openmassspec-io` staged-recipes PR open: [conda-forge/staged-recipes#34167](https://github.com/conda-forge/staged-recipes/pull/34167) (replaces the stale pre-rename #34069, closed). `openmassspec` facade recipe still to follow once `openmassspec-io` merges (its `run:` dep needs the feedstock to exist for the solver).
- **Zenodo / DOI reconciliation.** The OpenProteo -> OpenMassSpec rename may
  have left stale record titles; mint DOIs for the newly published openaraw
  / opensxraw. Manual (web UI). (No issue - not code.)

## 4. Feature depth (bigger, later)

- [OpenMassSpec#3](https://github.com/Sigilweaver/OpenMassSpec/issues/3) - streaming ingest (don't buffer a whole run in a Vec; a real .wiff hit ~1.15 GB).

## 5. Docs parity

- **Python API reference page missing** on py-binding repos that have docs
  sites (same gap as [OpenTimsTDF#3](https://github.com/Sigilweaver/OpenTimsTDF/issues/3)):
  [SpecLance#2](https://github.com/Sigilweaver/SpecLance/issues/2),
  [SigilYX#25](https://github.com/Sigilweaver/SigilYX/issues/25),
  [OpenQBW#1](https://github.com/Sigilweaver/OpenQBW/issues/1),
  [DICOM-Atlas#2](https://github.com/Sigilweaver/DICOM-Atlas/issues/2).
- [OpenQVD#3](https://github.com/Sigilweaver/OpenQVD/issues/3) - no docs site at all, unlike the sibling readers.

## 6. Cleanup / loose ends

- Standardize a tag/version-match guard across release workflows so a
  mistagged release can't publish. (No issue yet - small, cross-cutting.)

## 7. Vendor-reader parity / shared-schema completeness

Cross-vendor audit (2026-07-15) found gaps between what each vendor reader
decodes and what actually survives the shared schema/mzML writer into
output - some affect every vendor equally (shared-layer bugs), some are
single-vendor. See [OpenMassSpec#6](https://github.com/Sigilweaver/OpenMassSpec/issues/6)
for the proposed parity-matrix doc that should track this table going
forward instead of this section once it exists.

- **Chromatograms are unwired end-to-end.** `ChromatogramRecord`/
  `iter_chromatograms` exist in the shared schema, and the mzML writer now
  emits `<chromatogramList>` when a source yields anything (closed
  [OpenMassSpecCore#1](https://github.com/Sigilweaver/OpenMassSpecCore/issues/1),
  2026-07-15) - but no vendor implements `iter_chromatograms` yet, so
  TIC/BPC/SRM output is still empty in practice until a vendor does.
  - ~~[OpenWRaw#9](https://github.com/Sigilweaver/OpenWRaw/issues/9) - wire the existing (already-decoded, unused) `chroms.rs` into the trait~~ closed 2026-07-15 (574fe09); pressure/flow-rate/temperature channels only (units with no matching PSI-MS term are skipped). On main, UNRELEASED.
- ~~[OpenMassSpecCore#2](https://github.com/Sigilweaver/OpenMassSpecCore/issues/2) - `RunMetadata.start_timestamp` decoded by all five vendors, never written by the shared mzML writer~~ closed 2026-07-15; reaches output automatically once vendors bump to the next core release (no vendor code changes needed).
- ~~[OpenMassSpecCore#3](https://github.com/Sigilweaver/OpenMassSpecCore/issues/3) - no schema field for FAIMS compensation voltage~~ schema half closed 2026-07-15 (`SpectrumRecord.faims_cv` + writer support added). Vendor half done: [OpenTFRaw#27](https://github.com/Sigilweaver/OpenTFRaw/issues/27) closed 2026-07-15 (32d1d0a, released in OpenTFRaw 1.3.4).
- [OpenWRaw#8](https://github.com/Sigilweaver/OpenWRaw/issues/8) - precursor info hardcoded `None` for every spectrum, including targeted MS/MS functions (biggest single-vendor gap found). Investigated 2026-07-15: the corpus has no genuine targeted-MS/MS sample (all multi-function bundles are HDMSe with `Precursor Selection: Everything`, so `None` is actually correct for every file we have) - blocked on [OpenWRaw#13](https://github.com/Sigilweaver/OpenWRaw/issues/13) (acquire a real DDA/SRM sample). A smaller adjacent win is available regardless: `_FUNCnnn.STS` has fully-decoded per-scan collision energy that no code parses yet.
- [OpenTimsTDF#13](https://github.com/Sigilweaver/OpenTimsTDF/issues/13) - PRM-PASEF frames decoded but skipped in the mzML projection
- No vendor computes CCS despite two having raw ion-mobility data:
  [OpenTimsTDF#14](https://github.com/Sigilweaver/OpenTimsTDF/issues/14) (1/K0),
  [OpenWRaw#10](https://github.com/Sigilweaver/OpenWRaw/issues/10) (TWIMS drift time)

---

## Done recently (for context)

- OpenTFRaw#27 (2026-07-15, 32d1d0a): wired the existing `ScanParams::faims_cv()`
  accessor into `to_msc_record` now that openmassspec-core 1.2.0 (with the
  schema field) is published; released in OpenTFRaw 1.3.4.
- OpenWRaw#9 (2026-07-15, 574fe09): `WatersSource::iter_chromatograms` now
  decodes `_CHROMS.INF`/`_CHROnnnn.DAT` into `ChromatogramRecord`, mapping
  units to a PSI-MS chromatogram-type term (pressure/flow-rate/temperature,
  verified against psi-ms.obo) and skipping channels with no CV match
  (composition %, heater power %) rather than mislabeling them. On main,
  UNRELEASED. Won't produce real mzML output until OpenWRaw cuts a release
  against openmassspec-core 1.2.0+ (writer support landed in
  OpenMassSpecCore#1).
- OpenWRaw#8 investigated (2026-07-15), not fixed: the corpus has no
  genuine targeted-MS/MS sample, so the issue's "Set Mass" premise doesn't
  apply to any file we have - opened
  [OpenWRaw#13](https://github.com/Sigilweaver/OpenWRaw/issues/13) to
  track acquiring one.
- OpenMassSpecCore shared-writer fixes (2026-07-15): closed
  [OpenMassSpecCore#1](https://github.com/Sigilweaver/OpenMassSpecCore/issues/1)/[#2](https://github.com/Sigilweaver/OpenMassSpecCore/issues/2)/[#3](https://github.com/Sigilweaver/OpenMassSpecCore/issues/3)
  from the parity audit below - `write_mzml`/`write_indexed_mzml` now
  emit `<chromatogramList>` (indexed variant gets a second
  `<index name="chromatogram">` block), `<run startTimeStamp>`, and a
  scan-level FAIMS compensation-voltage cvParam (new
  `SpectrumRecord.faims_cv` field). Verified against the vendored PSI-MS
  XSDs via the extended `emit_sample_mzml` example. On main but
  UNRELEASED as of core 1.1.1; opened
  [OpenTFRaw#27](https://github.com/Sigilweaver/OpenTFRaw/issues/27) to
  wire the FAIMS field into OpenTFRaw's conversion once a new core
  version ships.
- Cross-vendor MS-stack parity audit (2026-07-15): confirmed OpenSXRaw#3
  (calibration + MS2 precursor m/z) and OpenARaw#3 (dead parsers /
  always-empty fields) were already closed - both removed from the
  sections above. Surfaced 9 new issues, filed under section 7 above.
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
- Loom dependency exposure closed out (2026-07-12): dead `python-jose`/
  `pyjwt` removed, dep-vuln CI gate + dependabot.yml + pre-release banner
  added (Loom#1, Loom#2). Loom#3 (remaining dev-tooling debt) stays open.
- OpenARaw / OpenSXRaw brought up to the OpenTFRaw maturity standard
  (2026-07-11): `cargo audit` + Docusaurus deploy CI jobs, OpenSXRaw Python
  bindings (`opensxraw-py` + PyPI publish), OpenARaw pyo3 0.28->0.29 (clears
  RUSTSEC-2026-0176/0177), docs guide gaps filled, and both wired into the
  Website hub. OpenSXRaw's PyPI publish lands with its next tagged release.
