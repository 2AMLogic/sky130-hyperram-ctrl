#!/usr/bin/env bash
# Re-run T1 item 11 (ERC supply evidence) on the committed routed layout (#19).
#   layout/erc/run.sh          run klt erc on the routed GDS, write
#                              layout/records/erc.report.json
#   layout/erc/run.sh check    cheap: klt erc --check on the committed report
# klt is pinned to the version in scripts/check_ci.sh (KLT_VERSION). After a
# re-run commit layout/records/erc.report.json, then follow manifests/README.md.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
KLT_VERSION=0.8.0
klt() { uvx --from "klayout-tools==${KLT_VERSION}" klt "$@"; }

if [[ "${1:-}" == check ]]; then
  klt erc --check layout/records/erc.report.json
  exit
fi

klt erc --validate-spec layout/erc/supply-spec.json
# exit 4 = antenna half not checked (no --pdk, by design); erc_status is the verdict
klt erc layout/records/hyperram_ctrl.gds layout/erc/supply-spec.json \
  --top hyperram_ctrl --deck sky130 --findings-only --omit-antenna-tables --compact \
  --format json > layout/records/erc.report.json || [[ $? -eq 4 ]]
jq -r '"erc_status=\(.erc_status) findings=\(.erc_findings|length)"' layout/records/erc.report.json
