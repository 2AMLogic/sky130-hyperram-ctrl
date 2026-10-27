#!/usr/bin/env bash
# Re-run T1 item 4 (LVS) on the committed routed layout (#17).
#   layout/lvs/run.sh          extract the routed GDS (cells abstracted, DEF net
#                              names), compare against the as-built routed
#                              netlist, write layout/lvs/records/
#   layout/lvs/run.sh check    cheap: klt lvs --check on the committed report
# klt is pinned to the version in scripts/check_ci.sh (KLT_VERSION). After a
# re-run commit layout/lvs/records/, then follow manifests/README.md.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
KLT_VERSION=0.8.0
export PDK="${PDK:-sky130A}"
klt() { uvx --from "klayout-tools==${KLT_VERSION}" klt "$@"; }

if [[ "${1:-}" == check ]]; then
  klt lvs --check records/report.json
  exit
fi

klt extract extract.json --format json > records/extract.response.json
# exit 3 = grader ran, mismatch; the report is the evidence either way
klt lvs request.json --format json > records/report.json || [[ $? -eq 3 ]]
python3 -c 'import json;d=json.load(open("records/report.json"));print(d["status"],d.get("power_connectivity",{}).get("status"))'
