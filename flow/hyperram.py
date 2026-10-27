#!/usr/bin/env python3
"""Synthesis runner for the controller RTL (rtl/hyperram_ctrl/).

  hyperram.py synth   run `klt synthesize` on flow/synthesize-hyperram.json and
                      write the netlist + stat report to sim/hyperram/records/
  hyperram.py check   re-synthesize into a temp dir and compare byte-for-byte
                      with the committed netlist; exit 3 if stale (T1 item 1
                      freshness check, see attest/item1.json)

Needs yosys and the PDK on the path (scripts/setup-env.sh); .venv/bin first.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REC = REPO / "sim/hyperram/records"
NETLIST = REC / "hyperram_ctrl.netlist.v"
STAT = REC / "synth-stat.json"
REQ = REPO / "flow/synthesize-hyperram.json"
KEYS = ("engine", "engine_version", "hdl_toplevel", "instance_count", "area_um2", "sequential_area_um2",
        "instance_counts_by_type", "leakage_power_nw", "blackbox_modules", "structural")


def run_synth():
    proc = subprocess.run(["klt", "synthesize", str(REQ), "--format", "json"], capture_output=True, text=True)
    try:
        doc = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"FATAL: klt synthesize gave no JSON (rc={proc.returncode}): {proc.stderr.strip()[:500]}")
    if proc.returncode != 0 or "error" in doc:
        sys.exit(f"FATAL: klt synthesize failed: {json.dumps(doc.get('error', doc))[:500]}")
    netlist = (REPO / doc["netlist_path"]["path"]).read_bytes()
    shutil.rmtree(REPO / "flow/.klt", ignore_errors=True)
    return doc, netlist


def synth():
    REC.mkdir(parents=True, exist_ok=True)
    doc, netlist = run_synth()
    NETLIST.write_bytes(netlist)
    stat = {k: doc[k] for k in KEYS}
    stat["pdk"] = doc["provenance"]["pdk"]["version"]
    stat["klt_version"] = doc["provenance"]["klt_version"]
    STAT.write_text(json.dumps(stat, indent=2) + "\n")
    print(f"synth ok: {doc['instance_count']} cells, {doc['area_um2']} um2 -> {NETLIST.relative_to(REPO)}")


def check():
    if not NETLIST.exists():
        sys.exit(f"FATAL: {NETLIST.relative_to(REPO)} missing; run `make hyperram-synth`")
    _, fresh = run_synth()
    if fresh != NETLIST.read_bytes():
        print(f"STALE: {NETLIST.relative_to(REPO)} differs from a fresh synthesis of the RTL; run `make hyperram-synth`")
        sys.exit(3)
    print("netlist is fresh")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("synth", "check"):
        sys.exit(__doc__)
    {"synth": synth, "check": check}[sys.argv[1]]()
