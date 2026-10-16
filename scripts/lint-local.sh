#!/bin/bash
set -euo pipefail
VERSION="v9.6.0" # keep in sync with .github/workflows/ci-cd-*.yml
BASE_URL="https://raw.githubusercontent.com/HSLdevcom/transitdata-shared-workflows/main/megalinter"

args=()
[ -f .mega-linter.yml ] || args+=(-e "MEGALINTER_CONFIG=${BASE_URL}/base.yml" -e "LINTER_RULES_PATH=${BASE_URL}/linters")

exec docker run --rm \
  -v "$PWD:/tmp/lint" \
  -e VALIDATE_ALL_CODEBASE=true \
  ${args[@]+"${args[@]}"} "$@" \
  "ghcr.io/oxsecurity/megalinter:${VERSION}"
