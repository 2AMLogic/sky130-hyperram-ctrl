#!/usr/bin/env bash
# The one CI command set: called by .github/workflows/ci.yml and by
# `npm run check:ci`, so the two cannot drift.
#
# klt runs through scripts/klt.sh, which holds the only klt version pin and
# the only rule for choosing which klt binary runs (never touches the host
# tool install).
#
# Steps:
#   1. every flow/*.json, layout/*.json and manifests/*.json that exists parses
#      as JSON (a missing file is not an error; a malformed one is). flow/ holds
#      the klt request documents; a malformed one is only otherwise discovered
#      by a local run that needs the PDK, which CI does not have.
#   2. README relative links resolve
#   3. flow/hyperram.py's pinned-yosys gate rejects an unpinned yosys build
#      (the synthesis it guards is local_only; the gate itself is not)
#   4. the committed item-10 attestation still reproduces (klt signoff
#      --attest 10 --check; local_only commands such as `make smoke` are skipped)
#   5. the committed item-1 attestation still reproduces (hashes of RTL + netlist;
#      the local_only re-synthesis check is skipped)
#   6. the committed klt drc report is bound to the cited GDS and deck (--check, no rerun)
#   6b. the committed SDF-annotated post-layout evidence (report checksums,
#       SDF vs its producing klt sta response) is fresh -- no simulator needed
#   7. the committed klt signoff record equals a fresh render of the manifest
#   (the --help assertion for the two shell drivers runs as step 2b, beside
#    the other tool-free gates; the delay-chain derivation unit check runs as
#    step 3b; the tap-decode structural check runs as step 3c, self-tested
#    first; the PDK-root provenance check runs as step 3d, self-tested
#    first; the item-9 testbench attestation is checked as step 4b, and
#    step 4c asserts that attestation declares every controller bench present
#    on disk -- a bench the inventory omits is invisible to 4b rather than
#    drift)
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
for f in flow/*.json layout/*.json manifests/*.json; do
  python3 -I -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" \
    || { echo "::error file=$f::malformed JSON"; exit 1; }
  echo "ok $f"
done

echo "== 2/7 README relative links =="
python3 -I scripts/check_links.py README.md

echo "== 2b/7 --help of the shell drivers prints comment text only =="
# setup-env.sh and sim/pad-sta/run-opensta.sh print their leading comment
# block as --help through a pattern-anchored sed range (issue #124). Their
# upper bounds used to be hardcoded line numbers that drifted on every edit
# above them. This asserts the invariant, not a snapshot: --help must exit
# 0, write nothing to stderr, and print nothing but comment and blank
# lines, one of them the "# Usage:" header -- a reintroduced overshooting
# bound fails closed instead of silently truncating or dumping shell
# source. Needs no PDK, no yosys, no klt: both scripts exit from their
# argument loop before touching a tool.
help_err="$(mktemp)"
help_fail() {
  rm -f "$help_err"
  echo "::error file=$1::$2"
  exit 1
}
for s in scripts/setup-env.sh sim/pad-sta/run-opensta.sh; do
  rc=0
  out="$(bash "$s" --help 2>"$help_err")" || rc=$?
  if [ "$rc" -ne 0 ]; then
    help_fail "$s" "--help exited $rc (expected 0)"
  fi
  if [ -s "$help_err" ]; then
    help_fail "$s" "--help wrote to stderr: $(head -c 200 "$help_err")"
  fi
  if ! printf '%s\n' "$out" | grep -q '^# Usage:'; then
    help_fail "$s" "--help has no '# Usage:' line"
  fi
  if printf '%s\n' "$out" | grep -qv -e '^[[:space:]]*$' -e '^[[:space:]]*#'; then
    help_fail "$s" "--help printed shell source, not comment text only"
  fi
  echo "ok $s: --help is comment lines only"
done
rm -f "$help_err"

echo "== 3/7 pinned-yosys gate rejects an unpinned build =="
# flow/hyperram.py's gate is the only thing between a yosys that merely reports
# the pinned version and a committed netlist or freshness result (issues #81,
# #89). The synthesis it guards is local_only -- CI has no yosys and no PDK --
# so the gate is driven directly here, with fabricated klt responses and
# temporary $PATHs. Needs no yosys, no klt and no PDK.
python3 -I scripts/check_yosys_gate.py

echo "== 3b/7 delay-chain derivation unit check =="
# flow/delay_chain.py's derive turns the campaign report into the committed
# record (taps.csv, summary.csv, RECORD.md) and is pure -- the ngspice
# campaign itself is local_only -- so the derivation is unit-checked directly
# here, against fixed report fixtures, including a deliberately non-monotonic
# one (issue #117). Needs no ngspice, no klt and no PDK.
python3 -I scripts/check_delay_chain_derive.py

echo "== 3c/7 tap-decode structural check =="
# The controller benches cannot cover the tap arithmetic of hr_tap_delay: the
# sim stand-ins are zero-delay pass-throughs, so no tap decode or chain-length
# mutation can change a bench result (PR #148 review -- both mutations were
# shown to leave the 43/43 suite green). This is the structural guard instead,
# a pure read of the committed netlist: one linear 16-cell dlygate series and
# a tap mux selecting depths 2,4,..16 for tap_sel=0..7. Self-tested first,
# over fixtures carrying exactly the mutations the benches miss, because it
# is now the only thing standing between a broken decode and a green CI.
# Needs no yosys, no klt and no PDK.
python3 -I scripts/check_tap_decode.py --self-test
python3 -I scripts/check_tap_decode.py

echo "== 3d/7 PDK-root provenance check =="
# ensure_pdk in scripts/fleet-regen-layout.sh fetches the pinned sky130A PDK
# outside the repo root (issue #142): a PDK under ${REPO_ROOT} makes klt
# record the liberty deck as repo-scoped evidence -- a path into a tree
# .gitignore deliberately excludes, unresolvable in every checkout -- while
# outside the repo the same field records scope "external". Every bench is
# blind to the regression and it surfaces only when a fleet job runs the
# regeneration end to end, by which time the wrong evidence is already
# committed, so this is the structural guard: a pure read of the committed
# script asserting every `export PDK_ROOT=` target in ensure_pdk is /opt/pdk,
# a caller-supplied ${PDK_ROOT}, or rooted at ${TMPDIR:-/var/tmp}, and never
# ${REPO_ROOT} (issue #155). It fails closed on a missing ensure_pdk or a
# missing export -- a rename must not silently pass -- and is self-tested
# first, over fixtures carrying exactly the regression. Needs no PDK, no
# klt and no network.
python3 -I scripts/check_pdk_root.py --self-test
python3 -I scripts/check_pdk_root.py

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

echo "== 6b/7 post-route SDF evidence is fresh =="
# The item-7 probe (issue #171): klt 0.9.2's functional-verification report
# writer emits no design-input digests, so `make -C verification/ctrl sdf`
# records them in a companion checksum file instead. This gate recomputes the
# routed-netlist, SDF and raw-report digests from checkout-relative paths,
# cross-checks the SDF against the producing klt sta response's
# sdf.content_hash, binds that response to the DEF it was produced from via
# its provenance.input.content_hash, and asserts the report's
# environment.sdf.annotated is literal true. The SPEF is not bound: the
# response records no SPEF digest, so a re-generated SPEF is not caught here.
# Needs no simulator, no PDK and no klt. Self-tested first, over fixtures
# carrying exactly the drift and unbind cases, because it is the only thing
# standing between a stale SDF run and a green CI.
python3 -I scripts/check_sdf_evidence.py --self-test
python3 -I scripts/check_sdf_evidence.py

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
