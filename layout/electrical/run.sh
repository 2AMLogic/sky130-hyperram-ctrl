#!/usr/bin/env bash
# Classify the routed layout's electrical-limit violations (issue #173).
#   layout/electrical/run.sh          run `klt sta` (DEF+SPEF, every shipped
#                                      liberty corner) through scripts/klt.sh,
#                                      keep each corner's engine stdout as
#                                      records/opensta-<corner>.log, then
#                                      classify -> records/electrical-checks.{json,md}
#   layout/electrical/run.sh check    cheap: the committed classification
#                                      record still binds the committed DEF/SPEF
#
# The full pin/limit/value listing lives in the engine stdout (issue #3005's
# `report_check_types -violators` rows), so the logs are committed evidence --
# the same append-only convention as sim/pad-sta/records. Nothing here
# re-derives a limit; classify.py only parses tool output.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

REQ=layout/electrical/sta-request.json
REC=layout/electrical/records

if [[ "${1:-}" == check ]]; then
  python3 -I - "$REC" <<'PY'
import hashlib, json, sys
from pathlib import Path
rec = Path(sys.argv[1])
doc = json.loads((rec / "electrical-checks.json").read_text())
for key, rel in (("def", "layout/records/hyperram_ctrl.def"),
                 ("spef", "layout/records/hyperram_ctrl.spef")):
    want = doc["geometry"][key]["sha256"]
    got = "sha256:" + hashlib.sha256(Path(rel).read_bytes()).hexdigest()
    if want != got:
        print(f"STALE: electrical-checks.json binds a different {key}: {want} != {got}")
        sys.exit(3)
print("electrical-checks record is fresh")
PY
  exit
fi

mkdir -p "$REC"
scripts/klt.sh sta --pdk "${PDK:-sky130A}" --format json "$REQ" > "$REC/sta-response.json"

# Keep the engine stdout the response's engine_log paths point at under their
# stable per-corner names (the .klt scratch is gitignored and regenerated).
python3 -I - "$REC" <<'PY'
import json, shutil, sys
from pathlib import Path
rec = Path(sys.argv[1])
resp = json.loads((rec / "sta-response.json").read_text())
if resp.get("status") != "ok":
    sys.exit(f"FATAL: klt sta status is {resp.get('status')!r}")
for corner in resp["corners"]:
    log = corner["engine_log"]["stdout_path"]
    src = Path(log["path"]) if log.get("path") else None
    if src is None or not src.exists():
        sys.exit(f"FATAL: engine stdout for corner {corner['corner']} is not retained ({log})")
    shutil.copyfile(src, rec / f"opensta-{corner['corner']}.log")
print(f"kept {len(resp['corners'])} engine stdout logs")
PY

python3 -I layout/electrical/classify.py
