# Sigilweaver suite backlog

Cross-repo view of what's worth doing next across the Sigilweaver
projects. Concrete, per-repo work lives in GitHub issues (linked below);
this file is the suite-level overview that survives across work sessions.
Start here, then open the linked issues for detail.

Maintenance: when an issue is opened, closed, or reprioritized, update the
matching line here. Cross-cutting themes that don't map to a single repo
issue are tracked directly in this file until they do.

---

## 1. Security / robustness hardening

The readers all parse untrusted binary input with hand-rolled bounds
checks; they were hardened as a family, not one at a time. This program is
now **complete** - the only open item is one upstream-blocked audit
advisory (SigilYX#26 below).

- **Fuzzing + allocation caps across the reader family - DONE.** Every
  reader now has both allocation caps on file-controlled length fields
  (memory-DoS) and a fuzz harness over its decode path. All closed:
  ~~OpenARaw#1~~, ~~OpenSXRaw#1~~ (`read_scan_block`), ~~SigilYX#24~~
  (YXDB parse path), ~~OpenWRaw#3~~, ~~OpenKSpace#1~~ (ISMRMRD `ns * nc`),
  ~~OpenQVD#1~~ (`no_of_symbols`, `n_rows`), plus OpenTFRaw#23 (2026-07-19,
  `crates/opentfraw/fuzz`) and OpenTimsTDF#7 (2026-07-14, extended the
  `decode_codec2` harness to the raw block-length read path).
- **`cargo audit` CI job standardized across every Rust repo (done 2026-07-11).**
  The rollout surfaced a real suite-wide vuln surface. Cleared by lockfile
  bump: genolance, openkspace (crossbeam-epoch/quinn-proto/rustls-webpki).
  Clean already: opensqlanywhere, openmassspeccore. The rest ignore genuine
  upgrade-needed advisories (kept green) with per-repo tracking issues:
  - **pyo3 -> 0.29** (same migration as OpenTFRaw#20 / OpenTimsTDF#1): closed
    2026-07-19 for DICOM-Atlas#3, OpenQBW#2, OpenQVD#4, SpecLance#3 (all four
    on main, unreleased), and for [OpenMassSpec#4](https://github.com/Sigilweaver/OpenMassSpec/issues/4)
    (pyo3 side landed in an earlier commit; see below for the quick-xml half).
    [SigilYX#26](https://github.com/Sigilweaver/SigilYX/issues/26) stays
    open too, blocked upstream: `pyo3-polars` latest published (0.27.0)
    caps at `pyo3 = "0.28"`, no 0.29-compatible release exists yet.
  - **quick-xml -> 0.41** (breaking API bump): closed 2026-07-19 for
    [OpenKSpace#2](https://github.com/Sigilweaver/OpenKSpace/issues/2),
    OpenQVD#4, SpecLance#3, and now also OpenMassSpec#4 - `mzdata` cut
    0.65.4 on 2026-07-14 with the quick-xml 0.41 bump (mobiusklein/mzdata#53),
    OpenMassSpec#11 picked it up 2026-07-19, `cargo audit` is clean.
    One holdout remains, blocked upstream, not fixable from our side:
    - SigilYX#26 - our own direct pin already resolves to 0.41, but
      Cargo.lock also carries a second, older quick-xml pulled in via
      `polars-io`'s optional (and inactive) `cloud` feature, which caps
      `object_store` below the version that would clear it. Blocked on
      polars-io bumping its `object_store` constraint.
  - ~~Loom is a separate Python dep gate, [Loom#2](https://github.com/Sigilweaver/Loom/issues/2)~~ closed 2026-07-12 (dep-vuln gate + dependabot.yml + pre-release banner landed).

## 2. Vendor-extras adaptation wave (done 2026-08-12)

The core-1.4.0 wave and the follow-on **vendor-extras wave are both done**
(see "Done recently"). OpenMassSpecCore#18 (the "Option C" decision from
[#17](https://github.com/Sigilweaver/OpenMassSpecCore/issues/17)) added
`SpectrumRecord::extra` / `RunMetadata::extra` (namespaced reader-specific
string metadata) and `SpectrumRecord::acquisition_event_id` (typed numeric
grouping id), projected as mzML `userParam`s. Core 1.5.0 was cut, all six
readers adapted (fields defaulted - none populated yet) and released, and
the umbrella (openmassspec-io / openmassspec 1.5.4) re-pinned to the whole
new stack.

Remaining follow-ups (not started):

- **Populate** `extra` / `acquisition_event_id` from real decoded vendor
  data. The 1.5.0 wave only defaulted them (empty / `None`) for
  compile-compatibility; the actual population from already-decoded fields
  is where several section-8 decoded-but-unused fields would finally get a
  home. No issues filed yet.
- Acquisition *mode* remains deferred, still tracked by the open umbrella
  proposal [#17](https://github.com/Sigilweaver/OpenMassSpecCore/issues/17).

## 3. Real CI coverage (cross-cutting) - DONE

The corpus-skip gap - previously the biggest confidence gap in the suite -
is closed. Conformance tests now run for real in CI instead of skipping,
and the corpus-free decoder unit tests landed alongside.

- ~~[OpenMassSpec#5](https://github.com/Sigilweaver/OpenMassSpec/issues/5)~~
  closed - `fetch_corpus.py` wired into CI so conformance tests run for
  real across all readers, rather than skipping silently on a plain
  checkout.
- ~~[OpenARaw#2](https://github.com/Sigilweaver/OpenARaw/issues/2) / [OpenSXRaw#2](https://github.com/Sigilweaver/OpenSXRaw/issues/2)~~ closed - byte-slice decoder unit tests (corpus-free coverage).
- ~~[GenoLance#1](https://github.com/Sigilweaver/GenoLance/issues/1)~~ closed - unit tests added; CI no longer runs `cargo test` over an empty set.
- **Test-matrix-mirrors-what-you-ship gap**, now documented as the org
  standard in [`CI_STANDARDS.md`](CI_STANDARDS.md) (test every OS you
  ship a wheel/binary for; lint once on Linux). Closed 2026-07-19:
  OpenQVD#2, DICOM-Atlas#1, SpecLance#1 (OpenWRaw#2 and OpenTimsTDF#2
  were already closed previously). OpenQVD and SpecLance went green on
  the first push. DICOM-Atlas needed two follow-up fixes after the
  matrix addition actually ran: `dicom-map-py`'s hard-enabled pyo3
  `extension-module` feature doesn't link on macOS without
  `.cargo/config.toml`'s `dynamic_lookup` rustflags (maturin normally
  papers over this, plain `cargo build` doesn't - pyo3 FAQ), and
  `tests/roundtrip_fuzz.py` needed the `.exe` suffix plus explicit
  `encoding="utf-8"` for Windows' cp1252 default. All green as of
  8f4605b/fef5975. The follow-up compliance survey (also 2026-07-19)
  found the same gap elsewhere, now tracked:
  [SigilYX#23](https://github.com/Sigilweaver/SigilYX/issues/23) (no
  Windows/macOS test at all), [OpenARaw#10](https://github.com/Sigilweaver/OpenARaw/issues/10),
  [OpenSXRaw#14](https://github.com/Sigilweaver/OpenSXRaw/issues/14),
  [OpenSZRaw#12](https://github.com/Sigilweaver/OpenSZRaw/issues/12)
  (no Windows test despite shipping a Windows wheel - all three closed
  2026-07-19, `ci.yml` now runs the full ubuntu/macos/windows matrix),
  [OpenMassSpec#9](https://github.com/Sigilweaver/OpenMassSpec/issues/9)
  (same, plus fmt/clippy redundantly run on two OSes instead of once),
  [OpenYXDB#3](https://github.com/Sigilweaver/OpenYXDB/issues/3) (ubuntu-only
  despite a pixi/C++ toolchain shipping linux+macos+windows - different
  stack, same standard).

## 4. Reach / packaging

- [OpenMassSpec#2](https://github.com/Sigilweaver/OpenMassSpec/issues/2) - conda-forge feedstock for openmassspec-io + openmassspec (RELEASING.md documents the SOP). `openmassspec-io` staged-recipes PR open: [conda-forge/staged-recipes#34167](https://github.com/conda-forge/staged-recipes/pull/34167) (replaces the stale pre-rename #34069, closed). `openmassspec` facade recipe still to follow once `openmassspec-io` merges (its `run:` dep needs the feedstock to exist for the solver).
- **Zenodo / DOI reconciliation.** The OpenProteo -> OpenMassSpec rename may
  have left stale record titles; mint DOIs for the newly published openaraw
  / opensxraw. Manual (web UI). (No issue - not code.)

## 5. Feature depth (bigger, later)

- [OpenMassSpec#3](https://github.com/Sigilweaver/OpenMassSpec/issues/3) - streaming ingest (don't buffer a whole run in a Vec; a real .wiff hit ~1.15 GB).

## 6. Docs parity

- **Python API reference page missing** on py-binding repos that have docs
  sites (same gap as [OpenTimsTDF#3](https://github.com/Sigilweaver/OpenTimsTDF/issues/3)):
  [SpecLance#2](https://github.com/Sigilweaver/SpecLance/issues/2),
  [SigilYX#25](https://github.com/Sigilweaver/SigilYX/issues/25),
  [OpenQBW#1](https://github.com/Sigilweaver/OpenQBW/issues/1),
  [DICOM-Atlas#2](https://github.com/Sigilweaver/DICOM-Atlas/issues/2).
- [OpenQVD#3](https://github.com/Sigilweaver/OpenQVD/issues/3) - no docs site at all, unlike the sibling readers.

## 7. Cleanup / loose ends

- Standardize a tag/version-match guard across release workflows so a
  mistagged release can't publish. (No issue yet - small, cross-cutting.)

## 8. Vendor-reader parity / shared-schema completeness

Cross-vendor audit (2026-07-15) found gaps between what each vendor reader
decodes and what actually survives the shared schema/mzML writer into
output - some affect every vendor equally (shared-layer bugs), some are
single-vendor. See [OpenMassSpec#6](https://github.com/Sigilweaver/OpenMassSpec/issues/6)
for the proposed parity-matrix doc that should track this table going
forward instead of this section once it exists.

- **Chromatograms are now wired across all six vendors.** `ChromatogramRecord`/
  `iter_chromatograms` exist in the shared schema, the mzML writer emits
  `<chromatogramList>` when a source yields anything (closed
  [OpenMassSpecCore#1](https://github.com/Sigilweaver/OpenMassSpecCore/issues/1),
  2026-07-15), and every vendor reader now implements `iter_chromatograms`:
  OpenTFRaw, OpenWRaw, OpenSZRaw (as of the 2026-07-24 sweep), plus
  OpenSXRaw ([#21](https://github.com/Sigilweaver/OpenSXRaw/issues/21),
  closed 2026-07-26), OpenARaw ([#17](https://github.com/Sigilweaver/OpenARaw/issues/17),
  closed 2026-07-26), and OpenTimsTDF ([#25](https://github.com/Sigilweaver/OpenTimsTDF/issues/25),
  closed 2026-07-28). What remains is per-vendor depth (BPC/SRM/PRM
  refinements) tracked in the follow-up bullets below, not the basic
  end-to-end wiring, which is done:
  - ~~[OpenWRaw#9](https://github.com/Sigilweaver/OpenWRaw/issues/9) - wire the existing (already-decoded, unused) `chroms.rs` into the trait~~ closed 2026-07-15 (574fe09); pressure/flow-rate/temperature channels only (units with no matching PSI-MS term are skipped). On main, UNRELEASED.
  - ~~[OpenTFRaw#39](https://github.com/Sigilweaver/OpenTFRaw/issues/39) - TIC/BPC/SRM all already fully decoded (`ScanIndexEntry`, unused `tic_chromatogram()`/`bpc_chromatogram()` helpers, SRM transition grouping) - pure wire-up, smallest of the five~~ closed; confirmed wired (`build_chromatograms`, `crates/opentfraw/src/mzml.rs:709`) during the 2026-07-24 sweep.
  - ~~[OpenTimsTDF#25](https://github.com/Sigilweaver/OpenTimsTDF/issues/25)~~ closed 2026-07-28 - TIC/BPC wired via #26, SRM/PRM traces implemented for mzML export.
  - ~~[OpenSXRaw#21](https://github.com/Sigilweaver/OpenSXRaw/issues/21)~~ closed 2026-07-26 - existing Idx TIC data wired into `iter_chromatograms`; BPC/SRM new-decode work was spun out separately.
  - ~~[OpenARaw#17](https://github.com/Sigilweaver/OpenARaw/issues/17)~~ closed 2026-07-26 - `iter_chromatograms` implemented so TIC/BPC/SRM reach mzML output.
  - OpenSZRaw - no new issue; already-open [OpenSZRaw#2](https://github.com/Sigilweaver/OpenSZRaw/issues/2) (PDA/LSS chromatogram payload decode) already scopes the `iter_chromatograms` wiring as part of its done-criteria. `PDA 3D Raw Data`'s per-value payload grammar is still unsolved after 14+ combined investigation sessions (2026-07-19/20, two contributors) - see `docs/format/04-lcd-chromatogram-pda.md`'s factsheet for the full ruled-out list. Both follow-ups spun out 2026-07-20 are now resolved: [OpenSZRaw#21](https://github.com/Sigilweaver/OpenSZRaw/issues/21) closed - `LC Raw Data/Chromatogram Ch6` decoded (page framing + literal/wide-token tokenization, PR #22, external contributor); `Ch5` left unemitted (single repeated value in every available file, numeric grammar untestable from the corpus). [OpenSZRaw#20](https://github.com/Sigilweaver/OpenSZRaw/issues/20) closed 2026-07-21 - corpus widened 151->2976 files/9->16 accessions and found a genuinely non-empty `LSS Raw Data/Chromatogram Ch1` (MTBLS7425, 16S/23S rRNA study), the first real sample of the literally-named stream; not decoded yet. 2026-07-24 sweep re-ran Ch6's decode against Ch1: the outer page framing generalizes byte-exactly (zero leftover across all 7 MTBLS7425 files), but Ch6's tokenization threshold does not - an exhaustive parameter sweep found no matching threshold/wide_width combination, a genuine negative result (see issue comment for leads). A new anomaly spun out from that pass: [OpenSZRaw#23](https://github.com/Sigilweaver/OpenSZRaw/issues/23) (2149 `MTBLS688` files lack the `LSS Raw Data` storage entirely, unlike every other IT-TOF file, cause not investigated).
- ~~[OpenMassSpecCore#2](https://github.com/Sigilweaver/OpenMassSpecCore/issues/2) - `RunMetadata.start_timestamp` decoded by all five vendors, never written by the shared mzML writer~~ closed 2026-07-15; reaches output automatically once vendors bump to the next core release (no vendor code changes needed).
- ~~[OpenMassSpecCore#3](https://github.com/Sigilweaver/OpenMassSpecCore/issues/3) - no schema field for FAIMS compensation voltage~~ schema half closed 2026-07-15 (`SpectrumRecord.faims_cv` + writer support added). Vendor half done: [OpenTFRaw#27](https://github.com/Sigilweaver/OpenTFRaw/issues/27) closed 2026-07-15 (32d1d0a, released in OpenTFRaw 1.3.4).
- ~~[OpenWRaw#8](https://github.com/Sigilweaver/OpenWRaw/issues/8) - precursor info hardcoded `None` for every spectrum, including targeted MS/MS functions~~ closed; the adjacent collision-energy win and the `_extern.inf` `Set Mass` field are both now wired (`precursor_info_for`, `mzml.rs:256-279`), verified against real targeted-MS/MS corpus (PXD035818). ~~[OpenWRaw#13](https://github.com/Sigilweaver/OpenWRaw/issues/13)~~ (acquire a real DDA/SRM sample) closed alongside it. 2026-07-24 sweep found one adjacent gap the fix didn't cover: [OpenWRaw#22](https://github.com/Sigilweaver/OpenWRaw/issues/22) - the ETD Fragmentation Mode channel is still never wired to `PrecursorInfo.activation`.
- [OpenTimsTDF#13](https://github.com/Sigilweaver/OpenTimsTDF/issues/13) - PRM-PASEF frames decoded but skipped in the mzML projection. Effort tightened to "small" by the 2026-07-24 sweep - structurally a close copy-paste of the existing PASEF-DDA build path (see issue comment).
- No vendor computes CCS despite two having raw ion-mobility data:
  [OpenTimsTDF#14](https://github.com/Sigilweaver/OpenTimsTDF/issues/14) (1/K0),
  [OpenWRaw#10](https://github.com/Sigilweaver/OpenWRaw/issues/10) (TWIMS drift time). ~~The shared-schema blocker~~ - [OpenMassSpecCore#5](https://github.com/Sigilweaver/OpenMassSpecCore/issues/5) (no `ccs` field anywhere in the schema/writer) - closed in core 1.3.0. All six vendor readers have since adapted to 1.3.0's new `PrecursorInfo::ccs`/`RunMetadata::analyzers`/`instrument_serial_number` fields and republished (2026-07-25: openaraw 0.1.5, opensxraw 0.2.3, openszraw 0.1.2, opentfraw 1.3.6, opentimstdf 1.3.1, openwraw 1.2.7 - all default `ccs: None`, since neither vendor does the math yet). The schema no longer blocks anything; OpenTimsTDF#14 and OpenWRaw#10 are now purely vendor-side math work and are the actual next step. Bruker's 1/K0 -> CCS conversion (Mason-Schamp) is well-defined and public; Waters' TWIMS calibration is vendor-proprietary and messier, so OpenTimsTDF#14 is the better first target.

**2026-07-24 cross-repo sweep** (issue-finding pass, read-only introspection
only per the clean-room rule - no comparison against vendor SDKs/software).
Closed as resolved-but-stale-open: [OpenSZRaw#24](https://github.com/Sigilweaver/OpenSZRaw/issues/24)
(single-quad `.lcd` variant - the docs already described it as fully
decoded). New issues filed, beyond the ones folded into the bullets above:
[OpenTFRaw#41](https://github.com/Sigilweaver/OpenTFRaw/issues/41) (DIA/wideband
flags decoded-unused), [OpenTFRaw#42](https://github.com/Sigilweaver/OpenTFRaw/issues/42)
(label_headings/user_labels pairing), [OpenTFRaw#43](https://github.com/Sigilweaver/OpenTFRaw/issues/43)
(audit_end unused), [OpenTFRaw#44](https://github.com/Sigilweaver/OpenTFRaw/issues/44)
(DIA isolation-window m/z unrecoverable for Exploris/Fusion Lumos - corpus
already on hand, needs new RE), [OpenARaw#19](https://github.com/Sigilweaver/OpenARaw/issues/19)
(MSScan.bin offsets 36/44 TIC/intensity fields unparsed for stride=284),
[OpenSXRaw#23](https://github.com/Sigilweaver/OpenSXRaw/issues/23) (precursor
collision_energy/activation never investigated), [OpenWRaw#23](https://github.com/Sigilweaver/OpenWRaw/issues/23)
(lock-mass correction channels decoded but never applied - accuracy
implication unexamined), [OpenWRaw#24](https://github.com/Sigilweaver/OpenWRaw/issues/24)
(three minor decoded-but-dead fields, bundled), [OpenTimsTDF#27](https://github.com/Sigilweaver/OpenTimsTDF/issues/27)
(Frames.Polarity bypassed by a calibration-ID heuristic, cosmetic),
[OpenTimsTDF#28](https://github.com/Sigilweaver/OpenTimsTDF/issues/28)
(Frame.scan_mode decoded but redundant with msms_type dispatch),
[OpenSZRaw#26](https://github.com/Sigilweaver/OpenSZRaw/issues/26)
(cycle_index unused for QTOF precursor linking), [OpenSZRaw#27](https://github.com/Sigilweaver/OpenSZRaw/issues/27)
(MRM event_id decoded then discarded), ~~[OpenMassSpecCore#6](https://github.com/Sigilweaver/OpenMassSpecCore/issues/6)~~
(SpectrumRecord.analyzer never emitted, no per-spectrum
instrumentConfigurationRef - loses analyzer identity on hybrid
instruments) and ~~[OpenMassSpecCore#7](https://github.com/Sigilweaver/OpenMassSpecCore/issues/7)~~
(no instrument serial-number field) both closed in core 1.3.0 (schema
fields added; no vendor populates either one yet - all six default to
empty/`None`, same situation as `ccs` above). Also corrected several stale entries
above (OpenTFRaw#39, OpenWRaw#8/#13 were already closed but still shown
open) and confirmed OpenMassSpec's version pins and per-vendor API
surface have no drift.

## 9. Suite expansion - new vendor candidates

Considered by instrument market share, not just tooling gaps. **Hard
requirement for any candidate below: a corpus of real files must be
publicly sourceable** (public repository, not just a vendor demo file) -
no candidate should convert to active scoping without that confirmed
first. The six vendors already in OpenMassSpec (Thermo, Agilent, Waters,
SCIEX, Bruker, Shimadzu) cover roughly the top tier already.

- **JEOL** - next-largest MS vendor by share not yet covered. Full range
  (GC-MS, LC-MS, MALDI-TOF), strong installed base in Asia and academia.
  No ProteoWizard/msconvert support either, so also a genuine open-tooling
  gap, not just a market-share pick. **Corpus unconfirmed** (2026-07-21
  search pass found no public repository known to host native JEOL raw
  binaries - MassBank/MetaboLights/GNPS-MassIVE weren't checked
  file-by-file for JEOL extensions). Needs that checked before any real
  scoping.
- **LECO** - real share but concentrated in a narrower niche (GCxGC-TOF,
  environmental/forensics) rather than broad MS market share. Also no
  pwiz support. **Corpus checked and weaker than it first looked**:
  RIKEN's MassBase hosts 8,331 LECO Pegasus III GC-TOF-MS runs, but they're
  distributed pre-converted to a unified text format, not native LECO
  binary - not usable as a reverse-engineering corpus as-is. Would need a
  different source (direct facility outreach, or a repository that
  deposits raw LECO files unconverted) before this is viable at all.
- **PerkinElmer** - ruled out for now: MS line is smaller and partly
  OEM'd from other vendors' tech, so less of a genuinely distinct format
  to reverse-engineer.
- **Flow cytometry - downgraded from "no action" to a maybe (2026-07-21).**
  FCS itself is still an open ISAC standard, so this isn't
  reverse-engineering in the usual sense - the opportunity, if any, is a
  clean/simple/permissively-licensed Rust FCS reader as an alternative to
  existing implementations, not format discovery. Corpus is trivially
  available (FlowRepository.org is a dedicated public FCS repository).
  Prompted by auditing `jrmoynihan/flow` (Rust, AI-agent-built): found it
  currently has a **broken workspace on `main`** (`Cargo.toml` references
  a `flow-pacmap` member that was never committed - `cargo check
  --workspace` fails from a clean clone as of the 2026-07-19 release
  commit), CI fully disabled (`.github/workflows/rust.yml` entirely
  commented out, so 488 tests never run automatically), and heavy
  unwrap/expect/panic density in library code (597 across ~66.7k lines of
  non-test Rust). Not urgent, not scoped - just no longer ruled out on
  format-openness grounds alone, since "an open spec has one sloppy
  implementation" is a different situation than "no implementation
  exists."
- **Microscopy - new domain, not yet scoped, flagged because corpus
  sourcing looks strong.** Proprietary vendor image formats: Zeiss
  (`.czi`), Leica (`.lif`), Nikon (`.nd2`), and others. Unlike JEOL/LECO,
  a public corpus is confirmed to exist: the Image Data Resource
  (idr.openmicroscopy.org, OME) and the EMBL-EBI BioImage Archive both
  host original raw files in native vendor formats, not just converted
  derivatives. Existing incumbent is Bio-Formats (OME, Java, GPL) which
  already covers 150+ formats - same relationship OpenMassSpec has to
  ProteoWizard, so the differentiator would again be a permissively
  licensed, dependency-light Rust implementation rather than filling an
  absolute gap. Worth a proper scoping pass (same treatment as
  OpenARaw/OpenSXRaw got) before committing to a first format.

---

## Done recently (for context)

- **Vendor-extras wave + full stack release train (2026-08-12).** Cut and
  published the whole stack: openmassspec-core 1.5.0 (crates.io), the six
  readers - openaraw 0.1.7, opensxraw 0.2.5, openszraw 0.1.4, opentfraw
  1.4.0, opentimstdf 1.3.3, openwraw 1.2.9 (crates.io + PyPI) - and the
  umbrella openmassspec-io / openmassspec 1.5.4, re-pinned to the new core
  + readers. Also merged the six `chore/decoded-unused-fields` reader PRs
  and closed the five fully-resolved issues (SZRaw#26, TimsTDF#27,
  TFRaw#41/#42/#43) beforehand.
  - **Gotcha worth remembering:** core adds record fields as a *minor*
    bump, but the fields are required (no `Default`), so it is
    source-breaking to any reader that constructs `SpectrumRecord`/
    `RunMetadata`. Readers pin core with a caret (`"1.4.0"` = `^1.4`), so
    the moment core 1.5.0 hit crates.io their CI went red (missing-field
    E0063) even though only a version string had changed. The fix is the
    standard adaptation - bump the reader's core pin to the new version and
    default the new fields at every construction site - and it must land
    before the readers can build/release. `openmassspec-io` and
    `-io-cli` construct the core records too, so they need the same
    treatment. Watch for the local-vs-core name collision (`mzml::SpectrumRecord`
    vs `msc::SpectrumRecord`) and field shorthand (`index,`) when editing.
- **Core-1.4.0 adaptation wave (closed 2026-07-29).** Same shape as the
  1.3.0 wave below: OpenMassSpecCore#16 cut the 1.4.0 release (acquisition-
  software provenance, SHA-1 test coverage, zlib compression default,
  peak-picking processing step - two source-breaking), then all seven
  downstream `acquisition_software_name/version` construction-site fixes
  landed and closed (OpenARaw#26, OpenSXRaw#31, OpenSZRaw#30, OpenTFRaw#47,
  OpenTimsTDF#31, OpenWRaw#25, and OpenMassSpec#22 test-fixture-only), six
  vendor readers re-bumped. The two MSRV-gap issues filed in the same pass
  (OpenTimsTDF#32, OpenQBW#12 - `rusqlite`/`libsqlite3-sys` needs Rust 1.95
  via the `cfg_select!` macro) are both closed too; OpenMassSpec's own MSRV
  job was moved 1.88 -> 1.95 (691a6ca), not raised to an org-wide
  `policy.msrv` change since no other repo is forced off 1.88 yet.
- **CI corpus-skip gap closed (section 3).** OpenMassSpec#5 wired
  `fetch_corpus.py` into CI so conformance tests run for real; the
  corpus-free decoder unit tests (OpenARaw#2, OpenSXRaw#2) and GenoLance#1
  (empty test set) all closed alongside.
- **Chromatograms wired across all six vendors (section 8).** The last
  three - OpenSXRaw#21, OpenARaw#17 (both 2026-07-26), OpenTimsTDF#25
  (2026-07-28) - closed, joining OpenTFRaw/OpenWRaw/OpenSZRaw.
- **`chore/decoded-unused-fields` sweep - merged 2026-08-12.** Six
  self-authored PRs landed to `main` (all UNRELEASED), working the section-8
  decoded-but-unused fields: OpenARaw#29 (stride-284 base-peak intensity -
  code), OpenSZRaw#33 (QTOF cycle_index precursor linking, resolves #26 -
  code), OpenTFRaw#50 (DIA/wideband flags + label headings + audit_end,
  resolves #41/#42/#43 - code), OpenTimsTDF#38 (Frames.Polarity ground
  truth, resolves #27 - code), OpenSXRaw#37 (#23 collision-energy/activation
  - documents why it can't be safely wired yet, issue stays open),
  OpenWRaw#29 (#22/#23/#24 - documents blockers, issues stay open). The
  fully resolved-by-code issues were closed 2026-08-12: OpenSZRaw#26,
  OpenTimsTDF#27, OpenTFRaw#41/#42/#43. Left open on purpose: OpenARaw#19
  (only offset 44/base-peak intensity wired; offset 36/TIC couldn't be
  safely assigned and stays unresolved), OpenTimsTDF#28 (documented-for-
  decision, not wired), OpenSXRaw#23 and OpenWRaw#22/#23/#24 (documented
  blockers). Still open: OpenTFRaw#51 (external, Nabejo - DIA
  isolation-window m/z regression test, #44).
- **Core-1.3.0 adaptation wave + parity.md correction (2026-07-25).**
  Cross-repo integration audit (treating the suite as one product, not
  N independent repos) found three findings: (1) `openmassspec-core`
  1.3.0 - closing OpenMassSpecCore#5/#6/#7 (`ccs`, `analyzers`,
  `instrument_serial_number` schema fields) - was published but no
  downstream repo had picked it up, so the fields those issues were
  supposed to unblock were still unreachable; (2) `docs/parity.md`'s
  chromatogram and FAIMS rows were stale, contradicting its own "last
  verified" banner; (3) OpenMassSpec#5's body omitted OpenSZRaw from
  the corpus-skip list. Fixed all three: adapted all six vendor readers'
  `RunMetadata`/`PrecursorInfo` construction to the new fields (all
  default to empty/`None` - none of the three are decoded by any vendor
  yet) and republished (openaraw 0.1.5, opensxraw 0.2.3, openszraw
  0.1.2, opentfraw 1.3.6, opentimstdf 1.3.1, openwraw 1.2.7); found and
  fixed a second, related bug in the same pass - every repo's declared
  `openmassspec-core` manifest minimum was stale (still `"1.0.0"`/
  `"1.2.0"`), same class of bug already fixed once in OpenTimsTDF
  (e8afe90); corrected parity.md's chromatogram row (Thermo/Waters now
  "yes", Shimadzu "partial" - LC detector channels only, IT-TOF `.lcd`
  only) and FAIMS row (Thermo "yes", closed #27); updated OpenMassSpec#5.
  `openmassspec-io` bumped to build against all six new versions,
  `STACK.md` regenerated, `versions.toml` updated. Net effect: the
  schema blocker on OpenTimsTDF#14/OpenWRaw#10 (CCS math, section 8
  above) is now fully cleared - both are pure vendor-side math work.
- OpenMassSpec#4 closed (2026-07-19, OpenMassSpec#11): `mzdata` cut
  0.65.4 with its quick-xml 0.41 bump (mobiusklein/mzdata#53, merged
  2026-07-14); bumping the dependency was the whole fix, no source
  changes needed. `cargo audit` now clean suite-wide - no repo still
  carries an ignored quick-xml/pyo3 advisory.
- OpenARaw#10 / OpenSXRaw#14 / OpenSZRaw#12 closed (2026-07-19): all
  three now test on the full ubuntu/macos/windows matrix, closing the
  last Windows-CI gap in [`CI_STANDARDS.md`](CI_STANDARDS.md)'s
  compliance table - every repo that ships a Windows wheel now tests on
  Windows.
- Fuzz treatment reached the last two vendor readers: OpenTFRaw#23
  (2026-07-19) added unit tests plus a `cargo-fuzz` harness
  (`crates/opentfraw/fuzz`); OpenTimsTDF#7 (2026-07-14) capped the raw
  block-length read path and extended the existing `decode_codec2`
  harness to cover it. Every reader in the family now has both
  allocation caps and a fuzz target.
- Security batch (2026-07-19): pyo3/quick-xml audit cleanup across six
  repos. Closed: OpenKSpace#2 (quick-xml), OpenQBW#2 (pyo3), DICOM-Atlas#3
  + #1 (pyo3, Windows/macOS CI), OpenQVD#4 + #2 (quick-xml+pyo3, Windows/
  macOS CI - required an arrow 58->59 bump alongside pyo3-arrow), SpecLance#3
  + #1 (quick-xml+pyo3, Windows/macOS CI). Investigated and left open,
  blocked upstream: SigilYX#26 (pyo3-polars caps pyo3 at 0.28; polars-io's
  inactive `cloud` feature pins an old quick-xml transitively). OpenMassSpec#4
  was left open at the time (mzdata's quick-xml fix was merged upstream but
  unreleased) - since closed, see above. Also closed OpenTFRaw#22
  (docs/guide/reader.md field-table drift, regenerated from the struct).
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
  sections above. Surfaced 9 new issues, filed under section 8 above.
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
