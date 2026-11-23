#!/usr/bin/env bash
# Re-run T1 item 4 (LVS) on the committed routed layout (#17).
#   layout/lvs/run.sh          extract the routed GDS (cells abstracted, DEF net
#                              names), compare against the as-built routed
#                              netlist, write layout/lvs/records/
#   layout/lvs/run.sh check    cheap: klt lvs --check on the committed report,
#                              klt extract --check on the extract response
# records/extract.response.json is klt's response with one edit: the
# `dead_metal` list (~13k entries, nothing reads it) is emptied. The count
# stays in the klt warning text (#78).
# klt runs through scripts/klt.sh, which holds the only klt pin and resolver.
# After a re-run commit layout/lvs/records/, then follow manifests/README.md.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd ../.. && pwd)"
export PDK="${PDK:-sky130A}"
klt() { "${REPO_ROOT}/scripts/klt.sh" "$@"; }

if [[ "${1:-}" == check ]]; then
  klt lvs --check records/report.json
  klt extract --check records/extract.response.json
  exit
fi

# Written via a temp file so a failed klt/jq never leaves a half-written record.
tmp="$(mktemp records/.extract.response.XXXXXX)"
trap 'rm -f "$tmp"' EXIT
klt extract extract.json --format json | jq --indent 2 '.dead_metal=[]' > "$tmp"
mv "$tmp" records/extract.response.json
# exit 3 = grader ran, mismatch; the report is the evidence either way
klt lvs request.json --format json > records/report.json || [[ $? -eq 3 ]]
python3 -c 'import json;d=json.load(open("records/report.json"));print(d["status"],d.get("power_connectivity",{}).get("status"))'
