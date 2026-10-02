#!/usr/bin/env bash
set -euo pipefail

version="${PMAT_VERSION:?PMAT_VERSION is required}"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "::error::pmat-version must look like 3.42.0 (got '$version')"
  exit 1
fi

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "::error::Only Linux x86_64 runners are supported (got $(uname -s) $(uname -m))"
  exit 1
fi

base="https://github.com/paiml/paiml-mcp-agent-toolkit/releases/download/v${version}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

echo "::group::Install PMAT ${version}"
asset=""
# Prefer the glibc build; some releases only ship musl.
for target in x86_64-unknown-linux-gnu x86_64-unknown-linux-musl; do
  candidate="pmat-v${version}-${target}.tar.gz"
  if curl -fsSL --retry 3 -o "${work}/${candidate}" "${base}/${candidate}"; then
    asset="$candidate"
    break
  fi
done
if [[ -z "$asset" ]]; then
  echo "::error::No Linux x86_64 release asset found for PMAT v${version}"
  exit 1
fi

# The .sha256 file may be "<hash>" or "<hash>  <filename>"; only the first field matters.
expected="$(curl -fsSL --retry 3 "${base}/${asset}.sha256" | awk '{print $1; exit}')"
actual="$(sha256sum "${work}/${asset}" | awk '{print $1}')"
if [[ -z "$expected" || "$expected" != "$actual" ]]; then
  echo "::error::SHA256 mismatch for ${asset} (expected '${expected}', got '${actual}')"
  exit 1
fi

tar -xzf "${work}/${asset}" -C "$work"
binary="$(find "$work" -type f -name pmat | head -n 1)"
if [[ -z "$binary" ]]; then
  echo "::error::'pmat' binary not found inside ${asset}"
  exit 1
fi

bin_dir="${RUNNER_TEMP:-/tmp}/pmat-bin"
mkdir -p "$bin_dir"
install -m 0755 "$binary" "${bin_dir}/pmat"
echo "$bin_dir" >> "${GITHUB_PATH:?GITHUB_PATH is not set}"
"${bin_dir}/pmat" --version
echo "::endgroup::"
