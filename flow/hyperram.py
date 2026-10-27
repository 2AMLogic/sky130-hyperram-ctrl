#!/usr/bin/env python3
"""Synthesis runner for the controller RTL (rtl/hyperram_ctrl/).

  hyperram.py synth   run `klt synthesize` on flow/synthesize-hyperram.json and
                      write the netlist + stat report to sim/hyperram/records/
  hyperram.py check   re-synthesize into a temp dir and compare byte-for-byte
                      with the committed netlist; exit 3 if stale (T1 item 1
                      freshness check, see attest/item1.json)
  hyperram.py layout  run `klt place-and-route` on layout/place-and-route.json
                      (the netlist above, 50 MHz, PDN + tapcells) and commit
                      the routed outputs to layout/records/ plus the T1 item 2
                      envelope evidence/item2.json
  hyperram.py layout-check
                      verify the committed response against the request
                      (netlist and liberty hashes) and the item-2 envelope
                      against the committed GDS; no OpenROAD run

Needs yosys and the PDK on the path (scripts/setup-env.sh); .venv/bin first.
"""

import hashlib
import json
import os
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
LAYOUT = REPO / "layout"
LREC = LAYOUT / "records"
LREQ = LAYOUT / "place-and-route.json"
SCRATCH = LAYOUT / ".klt/place-and-route"
RESPONSE = LREC / "place-and-route.response.json"
AREA = LREC / "area.json"
ITEM2 = REPO / "evidence/item2.json"
# klt names its outputs after hdl_toplevel in the scratch dir; the committed names
ROUTED = {
    "hyperram_ctrl.gds": "hyperram_ctrl.gds",
    "hyperram_ctrl.def": "hyperram_ctrl.def",
    "hyperram_ctrl.v": "hyperram_ctrl.routed.v",
    "hyperram_ctrl_route.spef": "hyperram_ctrl.spef",
}
ROW17_MAX_UM2 = 100_000  # spec/target-spec.md row 17: <= 0.10 mm2 core (budget, proposal)
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


def sha256(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).relative_to(REPO))


def remap(node):
    """Point scratch-dir artifact paths at layout/records/; drop engine log
    paths (the logs stay in the untracked scratch dir, only their hashes stay)."""
    if isinstance(node, dict):
        if set(node) == {"path", "scope"} and isinstance(node["path"], str):
            name = Path(node["path"]).name
            if node["path"].startswith(rel(SCRATCH)) and name in ROUTED:
                return {"path": rel(LREC / ROUTED[name]), "scope": node["scope"]}
        return {k: remap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [remap(v) for v in node]
    return node


def layout():
    shutil.rmtree(LAYOUT / ".klt", ignore_errors=True)
    env = dict(os.environ, PDK=os.environ.get("PDK", "sky130A"))
    proc = subprocess.run(["klt", "place-and-route", str(LREQ), "--format", "json"],
                          capture_output=True, text=True, env=env)
    try:
        doc = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"FATAL: klt place-and-route gave no JSON (rc={proc.returncode}): {proc.stderr.strip()[:500]}")
    if proc.returncode != 0 or "error" in doc:
        sys.exit(f"FATAL: klt place-and-route failed: {json.dumps(doc.get('error', doc))[:800]}")
    publish(doc)


def publish(doc):
    power = doc.get("power") or {}
    if doc["status"] != "ok" or doc["stage_reached"] != "route" or not power.get("pdn") or not power.get("tapcell_master"):
        sys.exit("FATAL: response is not a routed result with power.pdn and power.tapcell_master")
    LREC.mkdir(parents=True, exist_ok=True)
    for src, dst in ROUTED.items():
        shutil.copyfile(SCRATCH / src, LREC / dst)
    for entry in doc["engine_logs"]:
        for key in ("script_path", "metrics_path", "directory", "stdout_path", "stderr_path", "metadata_path"):
            entry.pop(key, None)
    RESPONSE.write_text(json.dumps(remap(doc), indent=2) + "\n")
    core = doc["core_area_um2"]
    AREA.write_text(json.dumps({
        "note": "reported only, not graded: target-spec row 17 is a proposal (budget <= 0.10 mm2 core, corner typ)",
        "core_area_um2": core, "core_area_mm2": round(core / 1e6, 5), "die_area_um2": doc["die_area_um2"],
        "utilization_pct": doc["utilization_pct"], "row17_max_core_um2": ROW17_MAX_UM2,
        "within_row17_budget": core <= ROW17_MAX_UM2,
        "synth_stdcell_area_um2": json.loads(STAT.read_text())["area_um2"],
    }, indent=2) + "\n")
    gds = LREC / "hyperram_ctrl.gds"
    ITEM2.write_text(json.dumps({
        "schema_version": 1, "kind": "generic", "status": "pass", "t1_item": 2,
        "summary": "T1 item 2 (Layout): routed GDS from klt place-and-route (stage route, power.pdn true, "
                   f"tapcell {power['tapcell_master']}) of the item-1 netlist; request layout/place-and-route.json",
        "source": rel(RESPONSE),
        "provenance": {**remap(doc["provenance"]),
                       "input": {"path": {"path": rel(gds), "scope": "repo"}, "content_hash": sha256(gds)}},
    }, indent=2) + "\n")
    print(f"layout ok: core {core} um2 ({core / 1e6:.4f} mm2) -> {rel(LREC)}/")


def layout_check():
    for p in (RESPONSE, ITEM2, LREC / "hyperram_ctrl.gds"):
        if not p.exists():
            sys.exit(f"FATAL: {rel(p)} missing; run `make layout`")
    proc = subprocess.run(["klt", "place-and-route", str(LREQ), "--check", str(RESPONSE)],
                          capture_output=True, text=True, env=dict(os.environ, PDK=os.environ.get("PDK", "sky130A")))
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        print(f"STALE: {rel(RESPONSE)} no longer matches the request inputs; run `make layout`")
        sys.exit(3)
    bound = json.loads(ITEM2.read_text())["provenance"]["input"]["content_hash"]
    if bound != sha256(LREC / "hyperram_ctrl.gds"):
        print(f"STALE: {rel(ITEM2)} binds a different GDS than {rel(LREC)}/hyperram_ctrl.gds; run `make layout`")
        sys.exit(3)
    print("layout record is fresh")


COMMANDS = {"synth": synth, "check": check, "layout": layout, "layout-check": layout_check}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]]()
