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
#      --attest 10 --check; local_only commands such as the controller
#      cold-start check are skipped)
#   5. the committed item-1 attestation still reproduces (hashes of RTL + netlist;
#      the local_only re-synthesis check is skipped)
#   6. the committed klt drc report is bound to the cited GDS and deck (--check, no rerun)
#   6b. the committed SDF-annotated post-layout evidence (report checksums,
#       SDF vs its producing klt sta response) is fresh -- no simulator needed
#   6c. the post-route STA records match the current requests, DEF and SPEF
#       (self-tested first so `sta-postroute-note` cannot re-stamp stale inputs)
#   7. the committed pre-layout STA note equals a fresh render of the
#       committed record it sits beside (self-tested first; only the
#       note<->record binding -- the record's own binding to the netlist
#       stays local_only)
#   8. the committed klt signoff record equals a fresh render of the manifest
#       and no item in it is downgraded to unmet/stale_evidence or
#       unmet/unverifiable_provenance (a stale
#       manifest content_hash pin re-rendered and committed would pass the
#       byte-compare alone; issues #212, #214)
#   (the --help assertion for the two shell drivers runs as step 2b, beside
#    the other tool-free gates; the delay-chain derivation unit check runs as
#    step 3b; the tap-decode structural check runs as step 3c, self-tested
#    first; the PDK-root provenance check runs as step 3d, self-tested
#    first; the fleet PDK_ROOT runtime guard fixture runs as step 3e; the
#    item-9 testbench attestation is checked as step 4b, and
#    step 4c asserts that attestation declares every controller bench present
#    on disk -- a bench the inventory omits is invisible to 4b rather than
#    drift)
set -euo pipefail

BLOCK="sky130-hyperram-ctrl"
MANIFEST="manifests/${BLOCK}.json"
RECORD="manifests/${BLOCK}.signoff.json"

cd "$(dirname "$0")/.."

KLT=(scripts/klt.sh)

echo "== 1/8 JSON validity =="
shopt -s nullglob
for f in flow/*.json layout/*.json manifests/*.json; do
  python3 -I -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" \
    || { echo "::error file=$f::malformed JSON"; exit 1; }
  echo "ok $f"
done

echo "== 2/8 README relative links =="
python3 -I scripts/check_links.py README.md

echo "== 2b/8 --help of the shell drivers prints comment text only =="
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

echo "== 3/8 pinned-yosys gate rejects an unpinned build =="
# flow/hyperram.py's gate is the only thing between a yosys that merely reports
# the pinned version and a committed netlist or freshness result (issues #81,
# #89). The synthesis it guards is local_only -- CI has no yosys and no PDK --
# so the gate is driven directly here, with fabricated klt responses and
# temporary $PATHs. Needs no yosys, no klt and no PDK.
python3 -I scripts/check_yosys_gate.py

echo "== 3b/8 delay-chain derivation unit check =="
# flow/delay_chain.py's derive turns the campaign report into the committed
# record (taps.csv, summary.csv, RECORD.md) and is pure -- the ngspice
# campaign itself is local_only -- so the derivation is unit-checked directly
# here, against fixed report fixtures, including a deliberately non-monotonic
# one (issue #117). Needs no ngspice, no klt and no PDK.
python3 -I scripts/check_delay_chain_derive.py

echo "== 3c/8 tap-decode structural check =="
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

echo "== 3d/8 PDK-root provenance check =="
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

echo "== 3e/8 fleet PDK_ROOT runtime guard =="
# The runtime PDK_ROOT guard in scripts/fleet-regen-layout.sh -- the
# value-level assertion AFTER the ensure_pdk call, which rejects a
# repo-local PDK even through a symlink (issue #142; guard landed with
# issue #160 / PR #191) -- is covered by nothing else: step 3d parses only
# the body of ensure_pdk, and the guard lives outside that function on
# purpose, so it also covers the verified-PDK early return. This fixture
# runs the production fleet script itself in a throwaway checkout against
# fixture PDK roots, with stub tools and no network: every repo-local
# shape (at the checkout root, in a subdirectory, through a symlink, and
# through a symlinked checkout) must exit 4 with the issue #142
# diagnostic, and an external sibling sharing the checkout's name prefix
# must reach ensure_yowasp_yosys, the first step after the guard. It is
# built to fail on both silent weakenings: a logical (non -P) REPO_ROOT
# and a guard relocated where ensure_pdk's early return skips it
# (issue #193). Needs no PDK, no EDA tools, no klt beyond
# scripts/klt.sh --pin and no network.
scripts/test_fleet_pdk_root.sh

echo "== 4/8 item-10 attestation is fresh =="
# Hashes are raw bytes: any edit to README.md, LICENSE, ci.yml or
# attest/item10.json is drift until this is re-run and the envelope committed:
#   klt signoff --attest 10 --inventory attest/item10.json -o evidence/item10.json
"${KLT[@]}" signoff --attest 10 --inventory attest/item10.json --check evidence/item10.json

echo "== 4b/8 item-9 attestation is fresh =="
# Hashes are raw bytes of every testbench file listed in attest/item9.json
# (model, benches, README, the functional-verification request): editing any of
# them is drift until this is re-run and the envelope, the manifest hash and the
# signoff record are regenerated, in this order and last:
#   klt signoff --attest 9 --inventory attest/item9.json -o evidence/item9.json
# The cold-start command (make -C verification) is local_only and is skipped here.
"${KLT[@]}" signoff --attest 9 --inventory attest/item9.json --check evidence/item9.json

echo "== 4c/8 item-9 attestation declares every controller bench on disk =="
# Step 4b hashes the paths attest/item9.json lists, so a bench file the
# inventory omits is not drift -- it is invisible, and can ship unexecuted
# inside append-only evidence (issue #93). This is the assertion that closes
# that: every bench file under verification/ctrl/ must be declared. The
# checker is self-tested first, over fixture directories, because it is now the
# only thing standing between an undeclared bench and a green CI. Needs no klt,
# no cocotb and no PDK.
python3 -I scripts/check_bench_coverage.py --self-test
python3 -I scripts/check_bench_coverage.py

echo "== 5/8 item-1 attestation is fresh =="
# Per-file hashes of the RTL and netlist; the re-synthesis freshness command is
# local_only (needs yosys + PDK) and is skipped here. After any RTL change run:
#   make hyperram-synth
#   klt signoff --attest 1 --inventory attest/item1.json -o evidence/item1.json
"${KLT[@]}" signoff --attest 1 --inventory attest/item1.json --check evidence/item1.json

echo "== 6/8 DRC report is fresh =="
# Input and deck hashes only (no --rerun: the full DRC is local). After any GDS change:
#   make drc
"${KLT[@]}" drc --check layout/records/drc.report.json
# Item-11 ERC supply report: cheap re-hash of layout and spec (full re-run: layout/erc/run.sh)
"${KLT[@]}" erc --check layout/records/erc.report.json

echo "== 6b/8 post-route SDF evidence is fresh =="
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

echo "== 6c/8 post-route STA record is fresh =="
# The multi-corner post-route STA itself is local_only (needs OpenROAD + PDK;
# `make hyperram-sta-postroute`); CI re-derives only its input binding: the
# DEF against each response's own provenance hash, and the DEF/SPEF/request
# hashes against the marker line minted by `sta-postroute` in STA-postroute.md,
# the way layout-check gates the place-and-route response (issue #172).
# Self-tested first over fixture trees so `sta-postroute-note` cannot overwrite
# stale SPEF or request provenance and mask a needed STA rerun.
python3 -I flow/hyperram_selftest.py sta-postroute-check
python3 -I flow/hyperram.py sta-postroute-check

echo "== 7/8 pre-layout STA note is fresh =="
# The pre-layout STA itself is local_only (needs OpenROAD + PDK; `make
# hyperram-sta`); this step checks only the note<->record binding: the
# committed STA.md must equal byte-for-byte a fresh sta_note() render of the
# committed sta.json + synth-stat.json blackbox list (issue #208, the drift
# class of #81/#189/#192). It does NOT check that sta.json matches the
# netlist it was minted from -- that binding needs the STA rerun and stays
# local_only. Self-tested first over fixture trees, the way 6c gates the
# post-route twin.
python3 -I flow/hyperram_selftest.py sta-check
python3 -I flow/hyperram.py sta-check

echo "== 8/8 klt signoff record is fresh =="
fresh="$(mktemp)"
trap 'rm -f "$fresh"' EXIT
rc=0
"${KLT[@]}" signoff --manifest "$MANIFEST" --format json >"$fresh" || rc=$?
# 0 = every T1 item met; 3 = grader ran clean, some item unmet. Both are
# valid runs; anything else is a hard error.
if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then
  echo "::error::klt signoff exited $rc (expected 0 or 3): manifest or cited evidence is broken"
  exit 1
fi
if ! cmp -s "$fresh" "$RECORD"; then
  echo "::error::fresh klt signoff output differs from committed $RECORD; regenerate it in this PR:"
  echo "  scripts/klt.sh signoff --manifest $MANIFEST --format json > $RECORD"
  diff <(python3 -m json.tool "$fresh") <(python3 -m json.tool "$RECORD") || true
  exit 1
fi
# A record can be byte-fresh and still wrong: klt signoff downgrades a
# previously-met T1 item to unmet/stale_evidence when the manifest's pinned
# content_hash no longer matches the cited evidence, and a downgraded record
# re-rendered and committed passes the cmp above by comparing to itself
# (issue #212). The reason token is the discriminator -- klt 0.9.2 defines
# forty-eight `_REASON_*` tokens and the set grows release by release, so
# this reject-lists the two downgrade tokens, stale_evidence and
# unverifiable_provenance (issue #214), and nothing else,
# self-tested first, over fixtures, because it is the only thing standing
# between a silent T1 downgrade and a green CI. $RECORD is byte-equal to
# $fresh here (the cmp above), so checking it checks both. Needs no klt
# beyond the render above, no PDK and no network.
python3 -I scripts/check_signoff_reasons.py --self-test
python3 -I scripts/check_signoff_reasons.py "$RECORD"
echo "committed signoff record is fresh"
