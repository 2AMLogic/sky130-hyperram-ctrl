#!/usr/bin/env python3
"""Runner for the toolchain smoke flow (rtl/smoke/, NOT the design).

  smoke.py synth    run `klt synthesize`, copy netlist + stat report to the records dir
  smoke.py sta      run `klt sta` at tt/ss/ff on that netlist, fail unless setup+hold slack >= 0
  smoke.py record   write sim/smoke/records/RECORD.md (tool versions, PDK revision)

Records dir: sim/smoke/records/. Invoked by the Makefile; needs .venv/bin on PATH.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REC = REPO / "sim/smoke/records"
NETLIST = REC / "smoke_counter.netlist.v"
SYNTH_REQ = REPO / "flow/synthesize-smoke.json"
STA_REQ = REPO / "flow/sta-smoke.json"


def klt_json(*args):
    proc = subprocess.run(["klt", *args, "--format", "json"], capture_output=True, text=True)
    try:
        doc = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"FATAL: klt {args[0]} gave no JSON (rc={proc.returncode}): {proc.stderr.strip()[:500]}")
    if proc.returncode != 0 or "error" in doc:
        sys.exit(f"FATAL: klt {args[0]} failed: {json.dumps(doc.get('error', doc))[:500]}")
    return doc


def tool_version(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).strip().splitlines()
    return out[0] if proc.returncode == 0 and out else f"UNAVAILABLE ({out[0] if out else 'no output'})"


def synth():
    REC.mkdir(parents=True, exist_ok=True)
    doc = klt_json("synthesize", str(SYNTH_REQ))
    run_dir = REPO / doc["netlist_path"]["path"]
    shutil.copyfile(run_dir, NETLIST)
    stat = {k: doc[k] for k in ("engine", "engine_version", "hdl_toplevel", "instance_count", "area_um2",
                                "sequential_area_um2", "instance_counts_by_type", "leakage_power_nw", "structural")}
    stat["pdk"] = doc["provenance"]["pdk"]["version"]
    stat["klt_version"] = doc["provenance"]["klt_version"]
    (REC / "synth-stat.json").write_text(json.dumps(stat, indent=2) + "\n")
    shutil.rmtree(REPO / "flow/.klt", ignore_errors=True)
    print(f"synth ok: {doc['instance_count']} cells, {doc['area_um2']} um2 -> {NETLIST.relative_to(REPO)}")


def sta():
    if not NETLIST.exists():
        sys.exit(f"FATAL: {NETLIST} missing; run synth first")
    doc = klt_json("sta", str(STA_REQ))
    (REC / "sta.json").write_text(json.dumps(doc, indent=2) + "\n")
    corners = doc.get("corners") or []
    if len(corners) != 3:
        sys.exit(f"FATAL: expected 3 corners, got {len(corners)}")
    bad = 0
    for c in corners:
        setup, hold = c.get("worst_slack_ns"), c.get("worst_hold_slack_ns")
        ok = c.get("timing_status") == "constrained" and setup is not None and hold is not None \
            and setup >= 0 and hold >= 0
        bad += not ok
        print(f"  {c.get('corner'):<16} setup={setup} hold={hold} {'PASS' if ok else 'FAIL'}")
    if bad:
        sys.exit(f"FATAL: {bad} corner(s) failed")


def record():
    stat = json.loads((REC / "synth-stat.json").read_text())
    sta_doc = json.loads((REC / "sta.json").read_text())
    versions = {
        "klt": tool_version(["klt", "--version"]),
        "yosys (klt synthesize)": f"{stat['engine']} {stat['engine_version']}",
        "yosys binary on PATH": tool_version(["yosys", "-V"]),
        "iverilog": tool_version(["iverilog", "-V"]),
        "verilator": tool_version(["verilator", "--version"]),
        "cocotb": tool_version([sys.executable, "-c", "import cocotb;print(cocotb.__version__)"]),
        "openroad (klt sta)": sta_doc.get("engine_version", "unknown"),
    }
    lines = ["# Smoke flow record (toolchain bring-up; module is NOT part of the design)", "",
             f"- PDK: {stat['pdk']}", "- Tool versions:"]
    lines += [f"  - {k}: {re.sub(chr(10), ' ', v)}" for k, v in versions.items()]
    lines += ["", "## Synthesis", f"- {stat['instance_count']} cells, {stat['area_um2']} um2", "",
              "## STA (clk 20 ns, ideal clock, no wire load)", "", "| corner | setup slack (ns) | hold slack (ns) |", "|---|---|---|"]
    lines += [f"| {c['corner']} | {c['worst_slack_ns']} | {c['worst_hold_slack_ns']} |" for c in sta_doc["corners"]]
    (REC / "RECORD.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {REC / 'RECORD.md'}")


if __name__ == "__main__" and len(sys.argv) == 2 and sys.argv[1] in ("synth", "sta", "record"):
    {"synth": synth, "sta": sta, "record": record}[sys.argv[1]]()
else:
    sys.exit(__doc__)
