#!/usr/bin/env python3
"""Classify the routed controller's max-transition / max-capacitance violations.

Issue #173: the place-and-route response counts the electrical-limit
violations per corner but does not name the pins, and a count alone cannot
guide a repair. This script turns three tool-written inputs into a committed
classification record -- it parses tool output, it never re-derives a limit:

  1. layout/electrical/records/sta-response.json -- the `klt sta` response of
     layout/electrical/sta-request.json (DEF + SPEF geometry, one OpenSTA
     session per liberty corner). `klt sta` itself reports, per corner, the
     coverage / count / worst pin of each check; the full pin listing is in
     each session's retained engine stdout, which run.sh copies to
     records/opensta-<corner>.log as `report_check_types -max_slew|-max_capacitance
     -violators` rows plus the KLT_ELECTRICAL_NET pin-to-net map.
  2. layout/records/hyperram_ctrl.routed.v -- the as-built netlist; supplies
     each violating net's driver cell and its sink population (instance,
     cell, pin), from which the instance class is decided.
  3. layout/records/place-and-route.response.json -- the P&R sweep's own
     per-corner counts (library limits, global-routing-estimated parasitics),
     shown alongside the SPEF-annotated rows. The archived P&R sweep lacks
     its corresponding pin reports.

Writes layout/electrical/records/electrical-checks.json (the record) and
electrical-checks.md (the rendered tables).

Instance classes (evaluated per net, first match wins):
  delay-chain        driver is a dlygate4sd3_1 cell (the two hr_tap_delay lines)
  tap-mux            driver is any other cell instantiated under a u_*_dly
                     hierarchy (the tap-select muxes inside hr_tap_delay)
  clock-tree         >= 60% of sink pins are flop clock (CLK) pins
  reset-distribution >= 60% of sink pins are flop RESET_B/SET_B pins
  enable-fanout      >= 60% of sink pins are flop DE/CE enable pins
  control-fanout     8 or more sinks, none of the above
  weak-driver        fewer than 8 sinks, none of the above

Driver origin is `pnr-inserted` when the driver instance exists only in the
routed netlist (OpenROAD repair_design names the buffers it inserts
fanout<N>), `netlist` when the pre-CTS netlist
sim/hyperram/records/hyperram_ctrl.netlist.v already names it.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ELEC = REPO / "layout" / "electrical"
REC = ELEC / "records"
ROUTED = REPO / "layout" / "records" / "hyperram_ctrl.routed.v"
PR_RESPONSE = REPO / "layout" / "records" / "place-and-route.response.json"
NETLIST = REPO / "sim" / "hyperram" / "records" / "hyperram_ctrl.netlist.v"
REQUEST = ELEC / "sta-request.json"

OUT_PINS = {"X", "Y", "Z", "COUT", "SUM", "Q", "Q_N"}
RESET_PINS = {"RESET_B", "SET_B", "RESET", "SET"}
ENABLE_PINS = {"DE", "CE"}
CLOCK_PINS = {"CLK"}
CLASS_RULES = [
    ("delay-chain", lambda d, s: d and d["cell"] == "sky130_fd_sc_hd__dlygate4sd3_1"),
    ("tap-mux", lambda d, s: d and re.search(r"u_(ck|rwds)_dly", d["instance"])),
    ("clock-tree", lambda d, s: sum(s["pins"].values()) and
        sum(n for p, n in s["pins"].items() if p in CLOCK_PINS) / sum(s["pins"].values()) >= 0.6),
    ("reset-distribution", lambda d, s: sum(s["pins"].values()) and
        sum(n for p, n in s["pins"].items() if p in RESET_PINS) / sum(s["pins"].values()) >= 0.6),
    ("enable-fanout", lambda d, s: sum(s["pins"].values()) and
        sum(n for p, n in s["pins"].items() if p in ENABLE_PINS) / sum(s["pins"].values()) >= 0.6),
    ("control-fanout", lambda d, s: s["count"] >= 8),
    ("weak-driver", lambda d, s: s["count"] < 8),
]

NET_ROW = re.compile(r"KLT_ELECTRICAL_NET\s+(\S+)\s+(\S+)")
_NUM = re.compile(r"^-?\d+(?:\.\d+)?(?:e[-+]?\d+)?$", re.IGNORECASE)


def parse_violator_line(line: str):
    """One ``report_check_types -violators`` row -> dict, or None.

    The engine stdout is not always clean: measured logs contain rows with a
    duplicated slack column (``limit value slack slack``), rows whose suffix
    garbled into ``(VIOLATED) (VIOLATED)`` / ``(VIOLATED79 (VIOLATED`` (an
    interleaved-write artifact of the engine's own report), rows whose pin
    column carries a repeated name fragment (``_515_/RESET_B   T_B``), and
    rows where a ghost copy of the limit precedes the real columns
    (``pin  1.5000  1.50000  value slack``). The parse is therefore
    token-based rather than one regex: take the pin from the first token
    (plus an optional cell disambiguator), and keep the pair of measured
    columns which best satisfies slack = limit - value to print precision.
    The report sometimes interleaves a partial copy of a value between the
    real limit and value. The last column before the marker is the slack.
    """
    body = line.split("(VIOLATED", 1)[0].strip()
    if not body:
        return None
    tokens = body.split()
    pin = tokens[0]
    cell = None
    rest = tokens[1:]
    if rest and rest[0].startswith("("):
        cell = rest.pop(0).rstrip(")")
    nums = []
    while rest and _NUM.match(rest[-1]):
        nums.insert(0, float(rest.pop()))
    if (len(nums) < 3 or not all(map(math.isfinite, nums))
            or any(not pin.endswith(fragment) for fragment in rest)):
        return None
    slack = nums[-1]
    # Prefer the rightmost complete value on a tie. Independently rounded
    # five-decimal columns can differ by 0.00001 in their printed equation.
    candidates = [(nums[i], nums[j]) for j in range(len(nums) - 2, 0, -1)
                  for i in range(j - 1, -1, -1) if 0 <= nums[i] <= nums[j]]
    if not candidates or slack > 0:
        return None
    limit, value = min(candidates, key=lambda pair: abs(pair[0] - pair[1] - slack))
    if abs(limit - value - slack) > 0.000016:
        return None
    # KLT 0.8.0 accepts fragments before its numeric columns as part of
    # the pin name, but drops rows with a damaged violation suffix.
    return {
        "pin": pin, "cell": cell, "limit": limit, "value": value, "slack": slack,
        "extra_columns": len(nums) - 3 or None, "junk": " ".join(rest) or None,
        "klt_dropped": line.partition("(VIOLATED")[2].strip() != ")",
    }


INST = re.compile(r"(sky130_fd_sc_hd__\w+)\s+(\\?[^\s(]+)\s*\(\s*(\.[^;]*?)\);", re.S)


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def parse_routed_netlist(path: Path):
    """instance -> {cell, pins}; net -> {driver, sinks} for the flat netlist."""
    insts = {}
    for m in INST.finditer(path.read_text()):
        cell, inst, conns = m.group(1), m.group(2), m.group(3)
        pins = {k: v.strip().lstrip("\\") for k, v in
                re.findall(r"\.(\w+)\s*\(\s*([^()]*?)\s*\)", conns)}
        insts[inst.lstrip("\\")] = {"cell": cell, "pins": pins}
    nets = {}
    for inst, body in insts.items():
        for pin, net in body["pins"].items():
            entry = nets.setdefault(net, {"drivers": [], "sinks": []})
            if pin in OUT_PINS:
                entry["drivers"].append({"instance": inst, "cell": body["cell"], "pin": pin})
            else:
                entry["sinks"].append({"instance": inst, "cell": body["cell"], "pin": pin})
    return insts, nets


def netlist_instances(path: Path, top: str) -> dict[str, str]:
    """Expand the structural Yosys modules into OpenROAD's instance paths."""
    modules = dict(re.findall(r"^module\s+(\w+)\b(.*?)^endmodule\b",
                              path.read_text(), re.M | re.S))
    instances = {}

    def visit(module, prefix):
        for cell, inst in re.findall(r"^\s*(\w+)\s+(\S+)\s+\(", modules[module], re.M):
            name = prefix + inst.lstrip("\\")
            if cell in modules:
                visit(cell, name + "/")
            elif cell.startswith("sky130_fd_sc_hd__"):
                instances[name] = cell

    visit(top, "")
    return instances


def classify_net(net: str, nets: dict, synthesized: dict) -> dict:
    info = nets.get(net, {"drivers": [], "sinks": []})
    driver = info["drivers"][0] if info["drivers"] else None
    if driver:
        original_cell = synthesized.get(driver["instance"])
        origin = "pnr-inserted" if original_cell is None else "netlist"
        driver = {**driver, "origin": origin}
        if original_cell and original_cell != driver["cell"]:
            driver["synthesized_cell"] = original_cell
    sinks = {
        "count": len(info["sinks"]),
        "pins": dict(collections.Counter(s["pin"] for s in info["sinks"])),
        "cells": dict(collections.Counter(s["cell"].replace("sky130_fd_sc_hd__", "") for s in info["sinks"])),
        "modules": dict(collections.Counter(s["instance"].split("/")[0].lstrip("\\") for s in info["sinks"])),
    }
    klass = next((name for name, rule in CLASS_RULES if rule(driver, sinks)), "unclassified")
    return {
        "class": klass,
        "driver": driver,
        "sinks": sinks,
    }


def parse_log(path: Path):
    """(max_transition rows, max_capacitance rows, warnings) from one engine
    stdout log.

    Each row is the tool's own violator line (see :func:`parse_violator_line`)
    plus the net the KLT_ELECTRICAL_NET map assigns it."""
    lines = path.read_text().splitlines()
    out = {}
    warnings = []
    for flag, tag in (("MAX_SLEW", "max_transition"), ("MAX_CAP", "max_capacitance")):
        begin, end = (f"===KLT_STA_{flag}_{side}===" for side in ("BEGIN", "END"))
        if lines.count(begin) != 1 or lines.count(end) != 1:
            sys.exit(f"{path.name}: missing or duplicate {tag} block")
        block = [line.strip() for line in lines[lines.index(begin) + 1:lines.index(end)]
                 if line.strip()]
        if not block or block[-1] != "KLT_ELECTRICAL_OK":
            sys.exit(f"{path.name}: incomplete {tag} report")
        rows, netmap = [], {}
        for line in block[:-1]:
            if line in ("max slew", "max capacitance") or re.fullmatch(
                    r"Pin\s+Limit\s+(?:Slew|Cap)\s+Slack|-+", line):
                continue
            mapping = NET_ROW.fullmatch(line)
            if mapping:
                pin, net = mapping.groups()
                if pin in netmap:
                    sys.exit(f"{path.name}: duplicate {tag} mapping for {pin}")
                netmap[pin] = net
                continue
            parsed = parse_violator_line(line) if "(VIOLATED" in line else None
            if parsed is None:
                sys.exit(f"{path.name}: unreadable {tag} row: {line}")
            if parsed["klt_dropped"] or parsed["extra_columns"] or parsed["junk"]:
                why = []
                if parsed["junk"]:
                    why.append(f"junk tokens {parsed['junk']!r}")
                if parsed["klt_dropped"]:
                    why.append("garbled suffix")
                if parsed["extra_columns"]:
                    why.append(f"{parsed['extra_columns']} extra numeric column(s)")
                warnings.append(f"{tag}: {parsed['pin']}: {', '.join(why)} -- recovered")
            rows.append(parsed)
        pins = [r["pin"] for r in rows]
        if len(set(pins)) != len(rows) or set(pins) != netmap.keys():
            sys.exit(f"{path.name}: {tag} violation rows disagree with the pin map")
        for row in rows:
            row["net"] = netmap[row["pin"]]
        out[tag] = {"coverage": "checked", "rows": rows}
    return out, warnings


def geometry():
    request = json.loads(REQUEST.read_text())
    paths = {key: (ELEC / request[key]).resolve() for key in ("def", "spef")}
    paths["routed_netlist"] = ROUTED
    return {key: {"path": str(path.relative_to(REPO)), "sha256": sha256(path)}
            for key, path in paths.items()}


def measurement_files(rec, corners):
    names = ["sta-response.json", *(f"opensta-{corner}.log" for corner in corners)]
    return {name: sha256(rec / name) for name in names}


def measure():
    # Publish only after the completed session agrees with the captured inputs.
    corners = json.loads(REQUEST.read_text())["pdk"]["corners"]
    with tempfile.TemporaryDirectory(dir=ELEC) as tmp:
        stage = Path(tmp)
        inputs = geometry()
        with (stage / "sta-response.json").open("w") as output:
            subprocess.run([REPO / "scripts/klt.sh", "sta", "--pdk", os.getenv("PDK", "sky130A"),
                            "--format", "json", REQUEST.relative_to(REPO)],
                           cwd=REPO, stdout=output, check=True)
        response = json.loads((stage / "sta-response.json").read_text())
        if response.get("status") != "ok":
            sys.exit(f"STA failed with status {response.get('status')!r}")
        for corner in response["corners"]:
            log = corner["engine_log"]["stdout_path"]["path"]
            if not log:
                sys.exit(f"STA did not retain a stdout path for {corner['corner']}")
            shutil.copyfile(REPO / log, stage / f"opensta-{corner['corner']}.log")
        binding = {"geometry": inputs, "files": measurement_files(stage, corners)}
        (stage / "sta-inputs.json").write_text(json.dumps(binding, indent=2) + "\n")
        render(stage)
        REC.mkdir(exist_ok=True)
        for artifact in stage.iterdir():
            artifact.replace(REC / artifact.name)


def render(rec, check=False):
    response = json.loads((rec / "sta-response.json").read_text())
    corners = [c["corner"] for c in response["corners"]]
    request = json.loads(REQUEST.read_text())
    pr = json.loads(PR_RESPONSE.read_text())
    required = sorted(request["pdk"]["corners"])
    if (not required or len(required) != len(set(required)) or sorted(corners) != required
            or sorted(c["name"] for c in pr["corners"]) != required):
        sys.exit("Incomplete or duplicate corner coverage in STA or P&R")
    binding = json.loads((rec / "sta-inputs.json").read_text())
    inputs = geometry()
    if response["status"] != "ok" or response["provenance"]["input"]["content_hash"] != inputs["def"]["sha256"]:
        sys.exit("STA response does not verify the measured DEF")
    for key in ("def", "spef"):
        if response[key + "_path"]["path"] != inputs[key]["path"]:
            sys.exit(f"STA response used a different {key} path")
    if binding["geometry"] != inputs:
        sys.exit("STA inputs have changed since measurement")
    if binding["files"] != measurement_files(rec, corners):
        sys.exit("STA response or engine stdout has changed since measurement")
    if pr["provenance"]["input"]["content_hash"] != sha256(NETLIST):
        sys.exit("Synthesized netlist differs from the P&R input")
    insts, nets = parse_routed_netlist(ROUTED)
    synthesized = netlist_instances(NETLIST, response["hdl_toplevel"])
    pr_counts = {c["name"]: {
        "max_transition": c["max_transition_violation_count_vs_library"],
        "max_capacitance": c["max_capacitance_violation_count_vs_library"],
    } for c in pr.get("corners", [])}

    per_corner, net_names, all_warnings = {}, set(), []
    for resp_c in response["corners"]:
        corner = resp_c["corner"]
        log = rec / f"opensta-{corner}.log"
        parsed, warnings = parse_log(log)
        all_warnings += [f"{corner}: {w}" for w in warnings]
        # Reconcile against the response's own per-corner counts: the rows
        # parsed off the engine stdout must agree with what `klt sta` itself
        # counted, or the record refuses to render (a silently lossy parse
        # is worse than no record).
        for tag in ("max_transition", "max_capacitance"):
            ec = resp_c["electrical_checks"][tag]
            if ec["coverage"] != "checked" or resp_c["electrical_checks"]["parasitics_source"] != "spef":
                sys.exit(f"{corner}: {tag} lacks checked SPEF coverage")
            rows = parsed[tag]["rows"]
            for row in rows:
                instance, separator, port = row["pin"].rpartition("/")
                if separator and insts.get(instance, {}).get("pins", {}).get(port) != row["net"]:
                    sys.exit(f"{corner}: {row['pin']} disagrees with the routed netlist pin map")
            got = len(rows)
            delta = sum(r["klt_dropped"] for r in rows)
            if got - delta != ec["violation_count"] or len({r["net"] for r in rows}) != ec["net_count"]:
                sys.exit(f"{corner}: {tag} stdout disagrees with STA pin or net counts")
            if delta:
                all_warnings.append(
                    f"{corner} {tag}: klt sta response counts "
                    f"{ec['violation_count']}, the retained engine stdout holds "
                    f"{got}; the difference is klt's stricter stdout parse "
                    f"dropping garbled rows that this parser recovered")
            counted = [r for r in rows if not r["klt_dropped"]]
            pin = ec["worst_pin"]
            if counted:
                excess = max(r["value"] - r["limit"] for r in counted)
                if (ec["worst_excess"] is None or abs(excess - ec["worst_excess"]) > 1e-4
                        or not any(r["pin"] == pin and abs(r["value"] - r["limit"] - excess) < 1e-4
                                   for r in counted)):
                    sys.exit(f"{corner}: {tag} worst pin or excess disagrees with STA")
            elif pin is not None or ec["worst_excess"] is not None:
                sys.exit(f"{corner}: {tag} empty report has a worst violation")
        per_corner[corner] = parsed
        for tag in ("max_transition", "max_capacitance"):
            net_names.update(r["net"] for r in parsed[tag]["rows"])

    net_details = {n: classify_net(n, nets, synthesized) for n in sorted(net_names)}

    def worst(rows):
        if not rows:
            return None
        w = max(rows, key=lambda r: r["value"] - r["limit"])
        return {"pin": w["pin"], "net": w["net"], "value": w["value"], "limit": w["limit"],
                "excess": round(w["value"] - w["limit"], 5)}

    record = {
        "schema": "hyperram.electrical-checks/1",
        "issue": 173,
        "generated_by": "layout/electrical/classify.py (parses klt sta engine stdout; limits are the tool's own)",
        "parasitics_model": "committed SPEF (layout/records/hyperram_ctrl.spef), one klt sta DEF+SPEF session per corner",
        "geometry": inputs,
        "engine": {"openroad": response.get("engine_version"), "klt_pin": response["provenance"]["klt_version"] + " (scripts/klt.sh)"},
        "engine_stdout_artifacts": all_warnings,
        "place_and_route_sweep": {
            "path": str(PR_RESPONSE.relative_to(REPO)),
            "parasitics_model": "library limits with global-routing-estimated parasitics (estimate_parasitics -global_routing)",
            "pin_row_reconciliation": "unavailable",
            "evidence_gap": "https://github.com/2AMLogic/sky130-hyperram-ctrl/issues/179",
            "top_counts": {
                "max_transition_violation_count": pr.get("max_transition_violation_count_vs_library"),
                "max_capacitance_violation_count": pr.get("max_capacitance_violation_count_vs_library"),
                "antenna_violation_count": pr.get("antenna_violation_count"),
            },
        },
        "corners": [],
        "nets": net_details,
    }
    if "source_commit" in binding:
        record["source_commit"] = binding["source_commit"]
    for resp_c in response["corners"]:
        corner = resp_c["corner"]
        entry = {"corner": corner}
        entry["spef_annotation"] = resp_c.get("spef_annotation")
        entry["place_and_route_sweep_counts"] = pr_counts.get(corner)
        for tag in ("max_transition", "max_capacitance"):
            parsed = per_corner[corner][tag]
            rows = parsed["rows"]
            by_class = collections.defaultdict(list)
            for r in rows:
                by_class[net_details[r["net"]]["class"]].append(r)
            entry[tag] = {
                "coverage": parsed["coverage"],
                "violation_count": len(rows),
                "net_count": len({r["net"] for r in rows}),
                "worst": worst(rows),
                "by_class": {
                    klass: {"rows": len(rs), "nets": sorted({r["net"] for r in rs}), "worst": worst(rs)}
                    for klass, rs in sorted(by_class.items())
                },
                "rows": rows,
            }
        record["corners"].append(entry)

    # ---- render the markdown summary -------------------------------------
    lines = [
        "# Electrical-limit violation classification (issue #173)", "",
        f"Tool-written record rendered by `layout/electrical/classify.py` from the"
        f" `klt sta` DEF+SPEF response (`records/sta-response.json`) and each"
        f" corner's engine stdout (`records/opensta-<corner>.log`). OpenROAD"
        f" {response.get('engine_version')}, klt {response['provenance']['klt_version']}. Limits are the liberty's"
        f" own, as reported by the tool; nothing here is hand-typed.", "",
        f"Parasitics model: committed SPEF. The place-and-route sweep's counts"
        f" (global-routing-estimated parasitics) are quoted side by side and are"
        f" a different measurement of the same routed geometry. The archived P&R"
        f" pin rows are unavailable for reconciliation. [Evidence gap #179]"
        f"({record['place_and_route_sweep']['evidence_gap']}).", "",
        "| Corner | P&R max-tran / max-cap | SPEF max-tran rows (nets) | SPEF max-cap rows (nets) | classes |",
        "|---|---|---|---|---|",
    ]
    if "source_commit" in binding:
        lines[2:2] = [f"Baseline inputs and engine logs come from commit `{binding['source_commit']}`.", ""]
    for e in record["corners"]:
        pc = e["place_and_route_sweep_counts"]
        pc_s = f"{pc['max_transition']} / {pc['max_capacitance']}" if pc else "-"
        tr, ca = e["max_transition"], e["max_capacitance"]
        classes = ", ".join(f"{k}:{v['rows']}" for k, v in tr["by_class"].items()) or "-"
        lines.append(f"| `{e['corner']}` | {pc_s} | {tr['violation_count']} ({tr['net_count']}) | "
                     f"{ca['violation_count']} ({ca['net_count']}) | {classes} |")
    lines += ["", "## Violating nets (union over corners)", "",
              "| Net | Class | Driver | Origin | Sinks | Worst slew (corner, value/limit ns) | Worst cap (corner, value/limit pF) |",
              "|---|---|---|---|---|---|---|"]
    for name, d in net_details.items():
        drv = f"{d['driver']['cell'].replace('sky130_fd_sc_hd__', '')} `{d['driver']['instance']}`" if d["driver"] else "-"
        origin = d["driver"]["origin"] if d["driver"] else "-"
        slew_w, cap_w = None, None
        for e in record["corners"]:
            for r in e["max_transition"]["rows"]:
                if r["net"] == name and (slew_w is None or r["value"] - r["limit"] > slew_w[1] - slew_w[2]):
                    slew_w = (e["corner"], r["value"], r["limit"])
            for r in e["max_capacitance"]["rows"]:
                if r["net"] == name and (cap_w is None or r["value"] - r["limit"] > cap_w[1] - cap_w[2]):
                    cap_w = (e["corner"], r["value"], r["limit"])
        slew_s = f"`{slew_w[0]}` {slew_w[1]:.3f}/{slew_w[2]:.3f}" if slew_w else "-"
        cap_s = f"`{cap_w[0]}` {cap_w[1]:.3f}/{cap_w[2]:.3f}" if cap_w else "-"
        lines.append(f"| `{name}` | {d['class']} | {drv} | {origin} | {d['sinks']['count']} | {slew_s} | {cap_s} |")
    reports = {"electrical-checks.json": json.dumps(record, indent=2) + "\n",
               "electrical-checks.md": "\n".join(lines) + "\n"}
    for name, content in reports.items():
        if check:
            if (rec / name).read_text() != content:
                sys.exit(f"STALE: {name} differs from its measured inputs")
        else:
            (rec / name).write_text(content)
    print(f"electrical-checks: {len(corners)} corners, {len(net_names)} violating nets")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify both committed reports")
    mode.add_argument("--measure", action="store_true", help="run klt sta and capture its inputs")
    args = parser.parse_args()
    if args.measure:
        measure()
    elif args.check:
        try:
            render(REC, check=True)
        except (SystemExit, OSError, ValueError, KeyError) as error:
            print(f"Electrical evidence check failed: {error}", file=sys.stderr)
            sys.exit(3)
    else:
        render(REC)
