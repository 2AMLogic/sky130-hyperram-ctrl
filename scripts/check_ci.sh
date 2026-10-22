#!/usr/bin/env bash
# The one CI command set: called by .github/workflows/ci.yml and by
# `npm run check:ci`, so the two cannot drift.
#
# klt is pinned to KLT_VERSION. Locally, if the installed klt is not that
# version this script uses `uvx --from klayout-tools==KLT_VERSION klt`
# (never touches the host tool install).
#
# Steps:
#   1. every layout/*.json and manifests/*.json that exists parses as JSON
#      (a missing file is not an error; a malformed one is)
#   2. README relative links resolve
#   3. the committed klt signoff record equals a fresh render of the manifest
#
# RTL lint and the cocotb smoke test are added with the toolchain skeleton
# (issue #3), not here.
set -euo pipefail

KLT_VERSION="0.7.0"
BLOCK="sky130-hyperram-ctrl"
MANIFEST="manifests/${BLOCK}.json"
RECORD="manifests/${BLOCK}.signoff.json"
TIERS_DOC="manifests/design-evidence-tiers.md"

cd "$(dirname "$0")/.."

if command -v klt >/dev/null 2>&1 && [ "$(klt --version 2>/dev/null | awk '{print $NF}')" = "$KLT_VERSION" ]; then
  KLT=(klt)
else
  KLT=(uvx --from "klayout-tools==${KLT_VERSION}" klt)
fi

echo "== 1/3 JSON validity =="
shopt -s nullglob
for f in layout/*.json manifests/*.json; do
  python3 -I -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" \
    || { echo "::error file=$f::malformed JSON"; exit 1; }
  echo "ok $f"
done

echo "== 2/3 README relative links =="
python3 -I scripts/check_links.py README.md

echo "== 3/3 klt signoff record is fresh =="
fresh="$(mktemp)"
trap 'rm -f "$fresh"' EXIT
rc=0
"${KLT[@]}" signoff --manifest "$MANIFEST" --tiers-doc "$TIERS_DOC" --format json >"$fresh" || rc=$?
# 0 = every T1 item met; 3 = grader ran clean, some item unmet. Both are
# valid runs; anything else is a hard error.
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "::error::klt signoff exited $rc (expected 0 or 3): manifest, tier doc or cited evidence is broken"
  exit 1
fi
if ! cmp -s "$fresh" "$RECORD"; then
  echo "::error::fresh klt signoff output differs from committed $RECORD; regenerate it in this PR:"
  echo "  uvx --from klayout-tools==${KLT_VERSION} klt signoff --manifest $MANIFEST \\"
  echo "      --tiers-doc $TIERS_DOC --format json > $RECORD"
  diff <(python3 -m json.tool "$fresh") <(python3 -m json.tool "$RECORD") || true
  exit 1
fi
echo "committed signoff record is fresh"
