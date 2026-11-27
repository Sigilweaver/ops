#!/usr/bin/env bash
# Helper for the fetch-fixture action. Subcommands: prepare, download, install.
# Reads the fixture list from $FIXTURES (see action.yml for the format).
set -euo pipefail

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum < "$1" | cut -d' ' -f1
  else
    shasum -a 256 < "$1" | cut -d' ' -f1
  fi
}

# Print "name sha url [fallback]" for each fixture line.
fixture_lines() {
  printf '%s\n' "$FIXTURES" | tr -d '\r' | awk 'NF && $1 !~ /^#/'
}

prepare() {
  local key stage
  if [ -z "$(fixture_lines)" ]; then
    echo "::error::the fixtures input has no entries"
    return 1
  fi
  key="$(fixture_lines | { sha256sum 2>/dev/null || shasum -a 256; } | cut -c1-32)"
  stage="${RUNNER_TEMP:-/tmp}/fixtures-$key"
  mkdir -p "$stage"
  {
    echo "key=fixtures-${RUNNER_OS:-local}-$key"
    echo "stage=$stage"
  } >> "${GITHUB_OUTPUT:-/dev/stdout}"
}

# Download $2 (URL) to $1 (final path) via a .part file; success only if the
# SHA-256 in $3 matches.
try_url() {
  local dest="$1" url="$2" want="$3" got
  rm -f "$dest.part"
  if ! curl --fail --location --silent --show-error \
      --retry 5 --retry-all-errors --retry-connrefused --retry-delay 10 \
      --connect-timeout 30 --max-time 900 \
      --user-agent "${USER_AGENT:-Sigilweaver-CI/1.0}" \
      --output "$dest.part" "$url"; then
    echo "::warning::download failed: $url"
    rm -f "$dest.part"
    return 1
  fi
  got="$(sha256_of "$dest.part")"
  if [ "$got" != "$want" ]; then
    echo "::warning::sha256 mismatch for $url (got $got, want $want)"
    rm -f "$dest.part"
    return 1
  fi
  mv "$dest.part" "$dest"
}

download() {
  local name sha url fallback status=0 got round
  mkdir -p "$STAGE"
  while read -r name sha url fallback _; do
    if [ -z "$sha" ] || [ -z "$url" ]; then
      echo "::error::bad fixture line for '$name': need <name> <sha256> <url>"
      status=1
      continue
    fi
    if [ -f "$STAGE/$name" ] && [ "$(sha256_of "$STAGE/$name")" = "$sha" ]; then
      echo "Already present: $name"
      continue
    fi
    # The hosts can refuse connections from a runner address for a few
    # minutes, so make several passes over the URLs with a pause between.
    got=0
    for round in $(seq 1 "${ROUNDS:-3}"); do
      if try_url "$STAGE/$name" "$url" "$sha" \
          || { [ -n "${fallback:-}" ] && try_url "$STAGE/$name" "$fallback" "$sha"; }; then
        got=1
        break
      fi
      if [ "$round" -lt "${ROUNDS:-3}" ]; then
        echo "Round $round failed for $name; waiting ${ROUND_PAUSE:-60}s"
        sleep "${ROUND_PAUSE:-60}"
      fi
    done
    if [ "$got" = 1 ]; then
      echo "Fetched $name ($(wc -c < "$STAGE/$name" | tr -d ' ') bytes, sha256 ok)"
    else
      echo "::error::could not fetch $name from any URL"
      status=1
    fi
  done < <(fixture_lines)
  return "$status"
}

install() {
  local name sha rest status=0
  mkdir -p "$DESTINATION"
  while read -r name sha rest; do
    if [ ! -f "$STAGE/$name" ] || [ "$(sha256_of "$STAGE/$name")" != "$sha" ]; then
      echo "::error::cached fixture $name is missing or fails its checksum"
      status=1
      continue
    fi
    cp "$STAGE/$name" "$DESTINATION/$name"
    echo "Installed $DESTINATION/$name"
  done < <(fixture_lines)
  return "$status"
}

"$@"
