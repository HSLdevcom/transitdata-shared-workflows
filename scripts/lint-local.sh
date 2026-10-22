#!/bin/bash
set -euo pipefail
SHARED="$(cd "$(dirname "$0")/.." && pwd)"
# Same MegaLinter version and config commit as this checkout's lint.yml (the commit must be pushed).
VERSION=$(grep -oE 'megalinter/flavors/java@[0-9a-f]+ # v[0-9.]+' "${SHARED}/.github/workflows/lint.yml" | grep -oE 'v[0-9.]+$')
BASE_URL="https://raw.githubusercontent.com/HSLdevcom/transitdata-shared-workflows/$(git -C "${SHARED}" rev-parse HEAD)/megalinter"

FLAVOR="${1:?usage: $0 <java|javascript> [extra docker args]}" # matches CI: java (java/kotlin repos), javascript (typescript repos)
shift

args=()
[ -f .mega-linter.yml ] || args+=(-e "MEGALINTER_CONFIG=${BASE_URL}/base.yml")

exec docker run --rm \
  -v "$PWD:/tmp/lint" \
  -e VALIDATE_ALL_CODEBASE=true \
  ${args[@]+"${args[@]}"} "$@" \
  "ghcr.io/oxsecurity/megalinter-${FLAVOR}:${VERSION}"
