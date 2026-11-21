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
     reconciled against the SPEF-annotated rows. The two parasitic models
     are reported side by side and never mixed.

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

import collections
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ELEC = REPO / "layout" / "electrical"
REC = ELEC / "records"
ROUTED = REPO / "layout" / "records" / "hyperram_ctrl.routed.v"
PR_RESPONSE = REPO / "layout" / "records" / "place-and-route.response.json"
NETLIST = REPO / "sim" / "hyperram" / "records" / "hyperram_ctrl.netlist.v"

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

NET_ROW = re.compile(r"^KLT_ELECTRICAL_NET (\S+) (\S+)$", re.MULTILINE)
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
    (plus an optional ``(cell)`` disambiguation token), drop everything from
    the first ``(VIOLATED``, and anchor the numbers from the RIGHT --
    slack is the last token, then walk (value, limit) leftwards until
    ``slack ~= limit - value`` holds. Any tokens the walk leaves unconsumed
    (ghost columns, name fragments) are recorded as junk, and a row with no
    self-consistent assignment is rejected, not guessed.
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
    if len(nums) < 3:
        return None
    slack = nums[-1]
    for li in range(len(nums) - 3, -1, -1):
        limit, value = nums[li], nums[li + 1]
        if abs((limit - value) - slack) <= max(0.02, 0.01 * abs(limit)):
            # `klt`'s own electrical_checks counter parses this same stdout
            # with a stricter grammar and silently drops a row whose pin
            # column carries junk tokens (a duplicated name fragment) or
            # whose suffix garbled past a bare "(VIOLATED)". Those rows are
            # real engine-reported violations (the KLT_ELECTRICAL_NET map,
            # emitted from the engine's own pin iteration, still lists
            # them), so this parser recovers them and flags
            # `klt_dropped=True` -- the response-count reconciliation in
            # main() requires the undercount to equal exactly this set.
            klt_dropped = bool(rest) or not line.rstrip().endswith("(VIOLATED)")
            return {
                "pin": pin,
                "cell": cell,
                "limit": limit,
                "value": value,
                "slack": slack,
                "extra_columns": (len(nums) - 3 - li) or (li and 1) or None,
                "junk": " ".join(rest) or None,
                "klt_dropped": klt_dropped,
            }
    return None
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


def netlist_instances(path: Path) -> set[str]:
    return {m.group(2).lstrip("\\") for m in INST.finditer(path.read_text())}


def classify_net(net: str, nets: dict, origin_of) -> dict:
    info = nets.get(net, {"drivers": [], "sinks": []})
    driver = info["drivers"][0] if info["drivers"] else None
    sinks = {
        "count": len(info["sinks"]),
        "pins": dict(collections.Counter(s["pin"] for s in info["sinks"])),
        "cells": dict(collections.Counter(s["cell"].replace("sky130_fd_sc_hd__", "") for s in info["sinks"])),
        "modules": dict(collections.Counter(s["instance"].split("/")[0].lstrip("\\") for s in info["sinks"])),
    }
    klass = next((name for name, rule in CLASS_RULES if rule(driver, sinks)), "unclassified")
    return {
        "class": klass,
        "driver": {**driver, "origin": origin_of(driver["instance"])} if driver else None,
        "sinks": sinks,
    }


def parse_log(path: Path):
    """(max_transition rows, max_capacitance rows, warnings) from one engine
    stdout log.

    Each row is the tool's own violator line (see :func:`parse_violator_line`)
    plus the net the KLT_ELECTRICAL_NET map assigns it."""
    text = path.read_text()
    out = {}
    warnings = []
    for flag, tag in (("MAX_SLEW", "max_transition"), ("MAX_CAP", "max_capacitance")):
        b = re.search(r"===KLT_STA_%s_BEGIN===(.*?)===KLT_STA_%s_END===" % (flag, flag), text, re.S)
        if b is None:
            out[tag] = {"coverage": "not_run", "rows": []}
            continue
        block = b.group(1)
        if "KLT_ELECTRICAL_OK" not in block:
            out[tag] = {"coverage": "unsupported", "rows": []}
            continue
        netmap = dict(NET_ROW.findall(block))
        rows, rejected = [], []
        for line in block.splitlines():
            if "(VIOLATED" not in line:
                continue
            parsed = parse_violator_line(line)
            if parsed is None:
                rejected.append(line.strip())
                continue
            parsed["net"] = netmap.get(parsed["pin"], parsed["pin"])
            if parsed["klt_dropped"] or parsed["extra_columns"]:
                why = []
                if parsed["junk"]:
                    why.append(f"junk tokens {parsed['junk']!r}")
                if not why:
                    why.append("garbled suffix")
                if parsed["extra_columns"]:
                    why.append(f"{parsed['extra_columns']} extra numeric column(s)")
                warnings.append(f"{tag}: {parsed['pin']}: {', '.join(why)} -- recovered")
            rows.append(parsed)
        if rejected:
            warnings.append(f"{tag}: {len(rejected)} unparseable row(s) dropped: " +
                            "; ".join(rejected[:3]))
        netmap_pins = {p for p, _ in
                       re.findall(r"^KLT_ELECTRICAL_NET (\S+) (\S+)$", block, re.M)}
        row_pins = {r["pin"] for r in rows}
        if row_pins != netmap_pins:
            warnings.append(
                f"{tag}: stdout rows and KLT_ELECTRICAL_NET pins disagree "
                f"(rows-only={sorted(row_pins - netmap_pins)[:3]}, "
                f"netmap-only={sorted(netmap_pins - row_pins)[:3]})")
        out[tag] = {"coverage": "checked", "rows": rows}
    return out, warnings


def main() -> int:
    response = json.loads((REC / "sta-response.json").read_text())
    corners = [c["corner"] for c in response["corners"]]
    insts, nets = parse_routed_netlist(ROUTED)
    prenet = netlist_instances(NETLIST)
    origin_of = lambda inst: "pnr-inserted" if inst not in prenet else "netlist"

    pr = json.loads(PR_RESPONSE.read_text())
    pr_counts = {c["name"]: {
        "max_transition": c["max_transition_violation_count_vs_library"],
        "max_capacitance": c["max_capacitance_violation_count_vs_library"],
    } for c in pr.get("corners", [])}

    per_corner, net_names, all_warnings = {}, set(), []
    for corner in corners:
        log = REC / f"opensta-{corner}.log"
        parsed, warnings = parse_log(log)
        all_warnings += [f"{corner}: {w}" for w in warnings]
        # Reconcile against the response's own per-corner counts: the rows
        # parsed off the engine stdout must agree with what `klt sta` itself
        # counted, or the record refuses to render (a silently lossy parse
        # is worse than no record).
        resp_c = next(c for c in response["corners"] if c["corner"] == corner)
        for tag in ("max_transition", "max_capacitance"):
            ec = resp_c["electrical_checks"][tag]
            if ec["coverage"] != "checked":
                continue
            rows = parsed[tag]["rows"]
            got = len(rows)
            anomalous = sum(1 for r in rows if r["klt_dropped"] or r["extra_columns"])
            delta = got - ec["violation_count"]
            if delta < 0:
                sys.exit(
                    f"FATAL: {corner} {tag}: parsed {got} violator rows but the "
                    f"klt sta response counted {ec['violation_count']}")
            if delta > anomalous:
                sys.exit(
                    f"FATAL: {corner} {tag}: response undercounts by {delta} rows "
                    f"but only {anomalous} garbled/extra-column row(s) could "
                    f"explain it")
            if delta:
                all_warnings.append(
                    f"{corner} {tag}: klt sta response counts "
                    f"{ec['violation_count']}, the retained engine stdout holds "
                    f"{got}; the difference is klt's stricter stdout parse "
                    f"dropping garbled rows that this parser recovered")
            if rows and ec["worst_excess"] is not None:
                mine = max(rows, key=lambda r: r["value"] - r["limit"])
                excess = round(mine["value"] - mine["limit"], 5)
                if abs(excess - ec["worst_excess"]) > 1e-4 and not mine["klt_dropped"]:
                    sys.exit(
                        f"FATAL: {corner} {tag}: worst excess parsed {excess} on "
                        f"{mine['pin']} but the klt sta response reports "
                        f"{ec['worst_excess']} on {ec['worst_pin']}")
        per_corner[corner] = parsed
        for tag in ("max_transition", "max_capacitance"):
            net_names.update(r["net"] for r in parsed[tag]["rows"])

    net_details = {n: classify_net(n, nets, origin_of) for n in sorted(net_names)}

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
        "geometry": {
            "def": {"path": str(ROUTED.relative_to(REPO)).replace("hyperram_ctrl.routed.v", "hyperram_ctrl.def"),
                    "sha256": sha256(ROUTED.parent / "hyperram_ctrl.def")},
            "spef": {"path": "layout/records/hyperram_ctrl.spef", "sha256": sha256(ROUTED.parent / "hyperram_ctrl.spef")},
            "routed_netlist": {"path": str(ROUTED.relative_to(REPO)), "sha256": sha256(ROUTED)},
        },
        "engine": {"openroad": response.get("engine_version"), "klt_pin": "0.8.0 (scripts/klt.sh)"},
        "engine_stdout_artifacts": all_warnings,
        "place_and_route_sweep": {
            "path": str(PR_RESPONSE.relative_to(REPO)),
            "parasitics_model": "library limits with global-routing-estimated parasitics (estimate_parasitics -global_routing)",
            "top_counts": {
                "max_transition_violation_count": pr.get("max_transition_violation_count_vs_library"),
                "max_capacitance_violation_count": pr.get("max_capacitance_violation_count_vs_library"),
                "antenna_violation_count": pr.get("antenna_violation_count"),
            },
        },
        "corners": [],
        "nets": net_details,
    }
    for corner in corners:
        entry = {"corner": corner}
        resp_c = next(c for c in response["corners"] if c["corner"] == corner)
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

    REC.mkdir(parents=True, exist_ok=True)
    (REC / "electrical-checks.json").write_text(json.dumps(record, indent=2) + "\n")

    # ---- render the markdown summary -------------------------------------
    lines = [
        "# Electrical-limit violation classification (issue #173)", "",
        f"Tool-written record rendered by `layout/electrical/classify.py` from the"
        f" `klt sta` DEF+SPEF response (`records/sta-response.json`) and each"
        f" corner's engine stdout (`records/opensta-<corner>.log`). OpenROAD"
        f" {response.get('engine_version')}, klt 0.8.0. Limits are the liberty's"
        f" own, as reported by the tool; nothing here is hand-typed.", "",
        f"Parasitics model: committed SPEF. The place-and-route sweep's counts"
        f" (global-routing-estimated parasitics) are quoted side by side and are"
        f" a different measurement of the same routed geometry.", "",
        "| Corner | P&R max-tran / max-cap | SPEF max-tran rows (nets) | SPEF max-cap rows (nets) | classes |",
        "|---|---|---|---|---|",
    ]
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
    (REC / "electrical-checks.md").write_text("\n".join(lines) + "\n")
    print(f"electrical-checks: {len(corners)} corners, {len(net_names)} violating nets -> "
          f"{REC / 'electrical-checks.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
