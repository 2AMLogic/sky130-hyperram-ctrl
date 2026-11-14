#!/usr/bin/env bash
# The one CI command set: called by .github/workflows/ci.yml and by
# `npm run check:ci`, so the two cannot drift.
#
# klt runs through scripts/klt.sh, which holds the only klt version pin and
# the only rule for choosing which klt binary runs (never touches the host
# tool install).
#
# Steps:
#   1. every layout/*.json and manifests/*.json that exists parses as JSON
#      (a missing file is not an error; a malformed one is)
#   2. README relative links resolve
#   3. flow/hyperram.py's pinned-yosys gate rejects an unpinned yosys build
#      (the synthesis it guards is local_only; the gate itself is not)
#   4. the committed item-10 attestation still reproduces (klt signoff
#      --attest 10 --check; local_only commands such as `make smoke` are skipped)
#   5. the committed item-1 attestation still reproduces (hashes of RTL + netlist;
#      the local_only re-synthesis check is skipped)
#   6. the committed klt drc report is bound to the cited GDS and deck (--check, no rerun)
#   7. the committed klt signoff record equals a fresh render of the manifest
#   (the item-9 testbench attestation is checked as step 4b, and step 4c asserts
#    that attestation declares every controller bench present on disk -- a bench
#    the inventory omits is invisible to 4b rather than drift)
#
# RTL lint and the cocotb smoke test are added with the toolchain skeleton
# (issue #3), not here.
set -euo pipefail

BLOCK="sky130-hyperram-ctrl"
MANIFEST="manifests/${BLOCK}.json"
RECORD="manifests/${BLOCK}.signoff.json"
TIERS_DOC="manifests/design-evidence-tiers.md"

cd "$(dirname "$0")/.."

KLT=(scripts/klt.sh)

echo "== 1/7 JSON validity =="
shopt -s nullglob
for f in layout/*.json manifests/*.json; do
  python3 -I -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" \
    || { echo "::error file=$f::malformed JSON"; exit 1; }
  echo "ok $f"
done

echo "== 2/7 README relative links =="
python3 -I scripts/check_links.py README.md

echo "== 3/7 pinned-yosys gate rejects an unpinned build =="
# flow/hyperram.py's gate is the only thing between a yosys that merely reports
# the pinned version and a committed netlist or freshness result (issues #81,
# #89). The synthesis it guards is local_only -- CI has no yosys and no PDK --
# so the gate is driven directly here, with fabricated klt responses and
# temporary $PATHs. Needs no yosys, no klt and no PDK.
python3 -I scripts/check_yosys_gate.py

echo "== 4/7 item-10 attestation is fresh =="
# Hashes are raw bytes: any edit to README.md, LICENSE, ci.yml or
# attest/item10.json is drift until this is re-run and the envelope committed:
#   klt signoff --attest 10 --inventory attest/item10.json -o evidence/item10.json
"${KLT[@]}" signoff --attest 10 --inventory attest/item10.json --check evidence/item10.json

echo "== 4b/7 item-9 attestation is fresh =="
# Hashes are raw bytes of every testbench file listed in attest/item9.json
# (model, benches, README, the functional-verification request): editing any of
# them is drift until this is re-run and the envelope, the manifest hash and the
# signoff record are regenerated, in this order and last:
#   klt signoff --attest 9 --inventory attest/item9.json -o evidence/item9.json
# The cold-start command (make -C verification) is local_only and is skipped here.
"${KLT[@]}" signoff --attest 9 --inventory attest/item9.json --check evidence/item9.json

echo "== 4c/7 item-9 attestation declares every controller bench on disk =="
# Step 4b hashes the paths attest/item9.json lists, so a bench file the
# inventory omits is not drift -- it is invisible, and can ship unexecuted
# inside append-only evidence (issue #93). This is the assertion that closes
# that: every bench file under verification/ctrl/ must be declared. The
# checker is self-tested first, over fixture directories, because it is now the
# only thing standing between an undeclared bench and a green CI. Needs no klt,
# no cocotb and no PDK.
python3 -I scripts/check_bench_coverage.py --self-test
python3 -I scripts/check_bench_coverage.py

echo "== 5/7 item-1 attestation is fresh =="
# Per-file hashes of the RTL and netlist; the re-synthesis freshness command is
# local_only (needs yosys + PDK) and is skipped here. After any RTL change run:
#   make hyperram-synth
#   klt signoff --attest 1 --inventory attest/item1.json -o evidence/item1.json
"${KLT[@]}" signoff --attest 1 --inventory attest/item1.json --check evidence/item1.json

echo "== 6/7 DRC report is fresh =="
# Input and deck hashes only (no --rerun: the full DRC is local). After any GDS change:
#   make drc
"${KLT[@]}" drc --check layout/records/drc.report.json
# Item-11 ERC supply report: cheap re-hash of layout and spec (full re-run: layout/erc/run.sh)
"${KLT[@]}" erc --check layout/records/erc.report.json

echo "== 7/7 klt signoff record is fresh =="
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
  echo "  scripts/klt.sh signoff --manifest $MANIFEST \\"
  echo "      --tiers-doc $TIERS_DOC --format json > $RECORD"
  diff <(python3 -m json.tool "$fresh") <(python3 -m json.tool "$RECORD") || true
  exit 1
fi
echo "committed signoff record is fresh"
