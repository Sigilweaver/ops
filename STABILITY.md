# API stability policy

How Sigilweaver mass-spectrometry crates and Python packages version their
public APIs. Covers openmassspec-core, openmassspec-arrow, the vendor
readers (OpenTFRaw, OpenWRaw, OpenARaw, OpenTimsTDF, OpenSXRaw,
OpenSZRaw), the OpenMassSpec umbrella, and SpecLance.

The goal is that users can take every minor and patch release without
code changes, and that breaking releases are rare and announced.

## What is breaking

A change needs a new major version (or a new minor version for a 0.x
crate) when it:

- removes or renames a public item, field, method, function argument, or
  Python attribute;
- changes a public signature or return type, including turning a value
  into an `Option` or `Result`;
- adds a field to a public struct, or a variant to a public enum, that is
  not `#[non_exhaustive]`;
- raises the minimum Python version.

## What is not breaking

These ship in minor or patch releases:

- New fields on `#[non_exhaustive]` structs, new variants on
  `#[non_exhaustive]` enums, new functions, methods, and Python attributes.
- New CV terms and new mzML or Arrow output fields.
- Bug fixes that change decoded values, including m/z, intensity, MS
  level, polarity, and precursor values. These are listed in the
  CHANGELOG under Fixed, with the affected files or instruments.
- Errors reported where a value was previously wrong or silently missing.
- Raising the Rust MSRV. It is listed in the CHANGELOG and the README
  badge.
- Dependency updates that do not appear in the public API.

## Rules that keep it that way

- Public structs and enums are `#[non_exhaustive]` unless they are a
  closed set that cannot grow. Types callers build have constructors or
  `with_*` setters.
- No third-party types in a public Rust API, except openmassspec-core
  types in the readers and Arrow types in openmassspec-arrow. Arrow
  releases new major versions often, so openmassspec-arrow versions on its
  own, and no other crate exposes Arrow types.
- Every Rust repo runs `cargo-semver-checks` in CI against the latest
  published version. An unplanned break fails the pull request.
- Python: a public name is deprecated (with a `DeprecationWarning`) for
  at least one minor release before it is removed in a breaking release.
- Breaking changes are collected and released together. Each breaking
  release lists every change in the CHANGELOG and, when users need to edit
  more than a few lines, ships a `MIGRATING-<version>.md`.

## 1.0

A crate reaching 1.0 is a commitment to this policy, not a claim that
every file decodes correctly. Each reader's README keeps a current "Known
issues and gaps" section covering instrument and mode coverage and
measured m/z accuracy.
