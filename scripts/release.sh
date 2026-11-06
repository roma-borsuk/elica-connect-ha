#!/usr/bin/env bash
# Usage: ./scripts/release.sh 0.3.1
# Bumps the version in manifest.json, commits, tags v<version> and pushes.
# The GitHub Action then creates the release that HACS picks up.
set -euo pipefail

VERSION="${1:?Usage: $0 <version>, e.g. 0.3.1}"
MANIFEST="custom_components/elica_connect/manifest.json"

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree is not clean, commit your changes first." >&2
  exit 1
fi

tmp=$(mktemp)
jq --arg v "$VERSION" '.version = $v' "$MANIFEST" > "$tmp" && mv "$tmp" "$MANIFEST"

git add "$MANIFEST"
git commit -m "chore: release v$VERSION"
git tag "v$VERSION"
git push origin HEAD "v$VERSION"
echo "Pushed v$VERSION, GitHub Actions will create the release."
