#!/usr/bin/env python3
"""Runner for the RWDS delay-chain ngspice campaign (spec open question (b)).

  delay_chain.py sim     check the request against sim/delay-chain/corners.json,
                         submit the 45-corner campaign to the batch fleet, write
                         the raw report to sim/delay-chain/records/sim.report.json,
                         re-check the report against the same matrix, and derive
                         taps.csv, summary.csv and RECORD.md
  delay_chain.py derive  re-derive the three records from a report (default the
                         committed one); no ngspice, no fleet

klt runs through scripts/klt.sh (the pin and the resolution rule). The
campaign itself is a batch-fleet job submitted with --wait-for-capacity 600
(never a hand-run ngspice grid: the dispatch hosts forbid it and a hand grid
would carry no machine-checkable corner provenance). The request sets
batch.runner_version_check to "warn": the fleet image's runner is NEWER than
this repo's pinned client (it refused an unqualified submit with the
runner-side preflight, exit 87), a newer runner cannot silently drop a
request feature an older one would, and the skew is recorded in the report's
environment.remote (runner_klt_version vs client_klt_version) and quoted in
RECORD.md. The derivation is pure;
scripts/check_delay_chain_derive.py unit-checks it, including a deliberately
non-monotonic fixture that must be reported as a failure rather than smoothed
over. Every corner that returns a measurement error appears in taps.csv as a
failure; the runner then exits non-zero, so `make delay-chain` fails loudly
instead of filing a partial record.
"""

import csv
import json
import os
import sys
from pathlib import Path

# flow/klt_run.py is the only way this runner reaches klt; `python3 -I` keeps
# flow/ off sys.path, so put it there from __file__ before importing.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from klt_run import REPO, klt_json  # noqa: E402

REQ = REPO / "flow/sim-delay-chain.json"
MATRIX = REPO / "sim/delay-chain/corners.json"
REC = REPO / "sim/delay-chain/records"
REPORT = REC / "sim.report.json"
TAPS_CSV = REC / "taps.csv"
SUMMARY_CSV = REC / "summary.csv"
RECORD_MD = REC / "RECORD.md"

# Tap k selects dly[2*(k+1)] (hr_rd_capture.v); the bench names the nodes
# dly01..dly16. Cell counts are 2*(k+1) by construction.
TAP_NODES = ["dly02", "dly04", "dly06", "dly08", "dly10", "dly12", "dly14", "dly16"]
TAP_CELLS = [2 * (k + 1) for k in range(len(TAP_NODES))]
N_CORNERS = 45  # 5 process x 3 temperature x 3 supply (decision 0004)

EXPECTED_MEASUREMENTS = (
    ["in_rise", "in_fall"]
    + [f"tap{k}_{edge}" for k in range(len(TAP_NODES)) for edge in ("rise", "fall")]
)


class DeriveError(Exception):
    """The report cannot yield a record (a corner is missing entirely)."""


def _client_env():
    """Env for the klt subprocess, with $PDK_ROOT defaulted like
    scripts/setup-env.sh does. Two reasons: the netlist body's
    `.include $PDK_ROOT/...` is expanded by the executing host, and a client
    that leaves the variable unset lets klt's first-match PDK search pick
    between the ciel and volare installs silently."""
    env = dict(os.environ)
    env.setdefault("PDK_ROOT", os.path.expanduser("~/.ciel"))
    return env


def _first_crossing(corner, name):
    """The first crossing time (s) of measurement `name` in `corner`.

    Returns (time, None) or (None, reason). A measurement that came back with
    a non-pass status, no crossings member, or an empty series is a failure
    the record must show, never a silent drop."""
    meas = next((m for m in corner.get("measurements", []) if m.get("name") == name), None)
    if meas is None:
        return None, f"measurement '{name}' absent"
    if meas.get("status") != "pass":
        return None, f"measurement '{name}' status={meas.get('status')!r}"
    crossings = meas.get("crossings")
    if not isinstance(crossings, dict):
        return None, f"measurement '{name}' has no crossings series"
    times = crossings.get("times")
    if not times:
        return None, f"measurement '{name}' has an empty crossing series"
    if crossings.get("truncated"):
        return None, f"measurement '{name}' crossing series truncated (max cap too low)"
    return times[0], None


def derive(report, expected_ids=None):
    """Pure: report dict -> record dict (no files, no klt, no exit).

    Raises DeriveError when a corner the report is expected to carry is
    missing entirely (a partial collection) -- ratio-ing over what happened
    to come back is exactly the failure mode this must not have. A corner
    that IS present but whose measurements failed stays in the record as a
    failure (note set, delays None, monotonic None); the caller decides the
    exit code.
    """
    corners = report.get("corners") or []
    if expected_ids is not None:
        present = {c.get("corner_id") for c in corners}
        missing = [cid for cid in expected_ids if cid not in present]
        if missing:
            raise DeriveError(
                f"report is missing {len(missing)} of {len(expected_ids)} expected "
                f"corners (partial collection?): e.g. {missing[:5]}"
            )

    rows = []
    for c in corners:
        row = {
            "corner_id": c.get("corner_id", "?"),
            "process": c.get("process", "?"),
            "temperature_c": c.get("temperature_c"),
            "supply_v": (c.get("supply_v") or {}).get("vdd"),
            "note": "",
            "taps": [None] * len(TAP_NODES),  # each {"rise_ns": , "fall_ns": }
            "monotonic_rise": None,
            "monotonic_fall": None,
        }
        rows.append(row)
        if c.get("status") != "pass":
            row["note"] = f"corner status={c.get('status')!r}"
            continue
        refs = {}
        for edge in ("rise", "fall"):
            t, why = _first_crossing(c, f"in_{edge}")
            if t is None:
                row["note"] = why
            else:
                refs[edge] = t
        for k in range(len(TAP_NODES)):
            tap = {"rise_ns": None, "fall_ns": None}
            row["taps"][k] = tap
            for edge in ("rise", "fall"):
                if edge not in refs:
                    continue
                t, why = _first_crossing(c, f"tap{k}_{edge}")
                if t is None:
                    row["note"] = why
                else:
                    tap[f"{edge}_ns"] = (t - refs[edge]) * 1e9  # s -> ns
        if row["note"]:
            continue
        rises = [t["rise_ns"] for t in row["taps"]]
        falls = [t["fall_ns"] for t in row["taps"]]
        row["monotonic_rise"] = all(
            rises[k + 1] > rises[k] for k in range(len(rises) - 1))
        row["monotonic_fall"] = all(
            falls[k + 1] > falls[k] for k in range(len(falls) - 1))

    ok_rows = [r for r in rows if not r["note"]]
    summary = []
    for k, cells in enumerate(TAP_CELLS):
        entry = {"tap": k, "cells": cells}
        for edge in ("rise", "fall"):
            vals = [r["taps"][k][f"{edge}_ns"] for r in ok_rows]
            entry[f"{edge}_min_ns"] = min(vals) if vals else None
            entry[f"{edge}_max_ns"] = max(vals) if vals else None
            entry[f"{edge}_minmax_ratio"] = (max(vals) / min(vals)) if vals else None
        summary.append(entry)

    return {
        "n_corners": len(corners),
        "rows": rows,
        "summary": summary,
        "n_failed": len(rows) - len(ok_rows),
        "monotonic_all": bool(ok_rows)
        and all(r["monotonic_rise"] and r["monotonic_fall"] for r in ok_rows),
    }


def _fmt(v, digits=4):
    return "" if v is None else f"{v:.{digits}f}"


def write_csvs(rec):
    REC.mkdir(parents=True, exist_ok=True)
    mono = lambda v: "" if v is None else ("yes" if v else "no")
    with TAPS_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["corner_id", "process", "temperature_c", "supply_v", "tap",
                    "cells", "rise_delay_ns", "fall_delay_ns",
                    "monotonic_rise", "monotonic_fall", "note"])
        for r in rec["rows"]:
            for k in range(len(TAP_NODES)):
                tap = r["taps"][k]
                w.writerow([r["corner_id"], r["process"], r["temperature_c"],
                            _fmt(r["supply_v"], 2), k, TAP_CELLS[k],
                            _fmt(tap["rise_ns"]), _fmt(tap["fall_ns"]),
                            mono(r["monotonic_rise"]), mono(r["monotonic_fall"]),
                            r["note"]])
    with SUMMARY_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tap", "cells", "rise_min_ns", "rise_max_ns", "rise_minmax_ratio",
                    "fall_min_ns", "fall_max_ns", "fall_minmax_ratio"])
        for s in rec["summary"]:
            w.writerow([s["tap"], s["cells"], _fmt(s["rise_min_ns"]),
                        _fmt(s["rise_max_ns"]), _fmt(s["rise_minmax_ratio"]),
                        _fmt(s["fall_min_ns"]), _fmt(s["fall_max_ns"]),
                        _fmt(s["fall_minmax_ratio"])])


def render_result(rec):
    lines = []
    if rec["monotonic_all"]:
        lines.append("**Monotonic at every simulated corner, rise and fall.**")
    else:
        lines.append("**NOT monotonic: at least one corner/edge failed the "
                     "delay(tap k+1) > delay(tap k) test. Per spec, a failing "
                     "record is superseded, not the margin relaxed.**")
    lines.append("")
    if rec["n_failed"]:
        bad = [r["corner_id"] for r in rec["rows"] if r["note"]]
        lines += [f"**{rec['n_failed']} corner(s) failed measurement**; their "
                  f"taps.csv rows carry empty delays: {bad[:8]}"
                  + (" ..." if len(bad) > 8 else ""), ""]
    lines += [
        "Per-tap delay across corners (min/max over corners with usable "
        "measurements; details in taps.csv):", "",
        "| tap | cells | rise min-max (ns) | rise max/min | fall min-max (ns) | fall max/min |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {s['tap']} | {s['cells']} "
        f"| {_fmt(s['rise_min_ns'])} - {_fmt(s['rise_max_ns'])} "
        f"| {_fmt(s['rise_minmax_ratio'])} "
        f"| {_fmt(s['fall_min_ns'])} - {_fmt(s['fall_max_ns'])} "
        f"| {_fmt(s['fall_minmax_ratio'])} |"
        for s in rec["summary"]
    ]
    n_mono = sum(1 for r in rec["rows"] if r["monotonic_rise"] and r["monotonic_fall"])
    lines += ["", f"Corners in report: {rec['n_corners']} (expected {N_CORNERS}); "
              f"monotonic (rise and fall): {n_mono}."]
    return "\n".join(lines)


def render_provenance(report):
    env = report.get("environment") or {}
    prov = report.get("provenance") or {}
    remote = env.get("remote") or {}
    if isinstance(remote, dict) and remote.get("fleet"):
        jobs = ", ".join(b.get("job_id", "?") for b in remote["fleet"])
        state = "/".join(sorted({b.get("state", "?") for b in remote["fleet"]}))
    else:
        jobs = remote.get("job_id", "n/a (local run)")
        state = remote.get("state", "-")
    build = env.get("engine_build") or {}
    banner = (build.get("version_banner") or "").replace("\n", " ")[:200] or "unavailable"
    ml = env.get("models_lib")
    ml = ml.get("scope", "?") if isinstance(ml, dict) else ml
    amb = (prov.get("pdk", {}).get("ambiguous_sources") or [])
    amb = f" (also installed via {', '.join(amb)}; client pinned $PDK_ROOT)" if amb else ""
    skew = ""
    if remote.get("runner_klt_version"):
        skew = (f"- runner/client klt skew (deliberate, runner_version_check=warn): "
                f"runner {remote.get('runner_klt_version')} vs client "
                f"{remote.get('client_klt_version', '?')} (the repo pin); the "
                f"runner is the newer side, so no request feature can be "
                f"silently dropped")
    return "\n".join([
        "## Provenance (from the run's own report)", "",
        f"- engine: ngspice {env.get('engine_version', '?')} "
        f"(engine_host: {env.get('engine_host', '?')}); build banner: {banner}",
        f"- batch job(s): {jobs} (state: {state})",
        skew,
        f"- klt: {prov.get('klt_version', '?')}",
        f"- PDK: {prov.get('pdk', {}).get('version', '?')}{amb}; "
        f"models_lib: {ml} (sha256 {env.get('models_lib_sha256', '?')})",
        "",
    ])


ASSUMPTIONS_MARKDOWN = "\n".join([
    "## Assumptions (stated, per AC1)", "",
    "- **Schematic-level figures.** The PDK cell subckts are eight MOSFETs and "
    "zero capacitors: this record carries no parasitics of any kind, including "
    "the chain's own layout RC. A post-layout number is `klt pex`, not this "
    "record.",
    "- Input: full-rail pulse, 0.15 ns rise/fall, one rising edge (~2 ns) and "
    "the matching falling edge (~22 ns). Amplitude follows the corner rail "
    "(`corners.supply_waveforms`), i.e. the on-chip condition after the pad "
    "seam; pad delay and swing are open question (a), out of scope.",
    "- Loads exactly as the committed netlist: an even tap node drives the next "
    "delay cell PLUS one mux4_2 A pin, an odd node only the next cell, dly16 "
    "only its mux; each mux feeds its clkbuf_1. Select held static "
    "(tap_sel = 0, S0 = S1 low) -- the design holds it for a whole burst, and "
    "the per-tap delay is read at the dly nodes, before the mux.",
    "- Delay = 50 % rail crossing at the tap minus the 50 % crossing at the "
    "input node (supply-relative trip point via `frac_of`), first rise and "
    "first fall in 0..60 ns -- the window spans the worst-corner delay, not "
    "the typ-only one the first submit used (10 slow corners' late-tap fall "
    "edges landed past 30 ns and came back empty). Transient `5p 60n 0 25p` "
    "(tmax bounds the solver step near the edges).",
    "- Monotonicity test (AC3): delay(tap k+1) > delay(tap k) for every k, for "
    "rise and for fall, at that corner. Tap k+1's chain strictly contains tap "
    "k's, so a failure would point at a measurement artifact before the "
    "circuit.",
    "- Simulated circuit: sim/delay-chain/dlychain.sp; request: "
    "flow/sim-delay-chain.json; raw response: sim.report.json (committed "
    "verbatim); declared matrix: corners.json, machine-checked with "
    "`klt corner-matrix check`.",
    "",
])


def write_markdown(rec, report):
    REC.mkdir(parents=True, exist_ok=True)
    head = [
        "# RWDS delay chain across PVT (spec open question (b))", "",
        render_result(rec), "",
        "Result of the `make delay-chain` campaign (decision 0004 ngspice corner "
        "set) over the 16-cell `g_rwds_dly` chain of "
        "rtl/hyperram_ctrl/hr_rd_capture.v. The second chain (`g_ck_dly`, "
        "hr_dq_out.v) is the same cell, length and tap arithmetic, so this "
        "record answers for it too; no row-14 claim is made here.", "",
    ]
    if report is not None:
        head += [render_provenance(report)]
    else:
        head += ["## Provenance", "",
                 "Re-derived locally from the committed sim.report.json; see that "
                 "file and the previous RECORD.md for the run's provenance.", ""]
    head += [ASSUMPTIONS_MARKDOWN]
    RECORD_MD.write_text("\n".join(head))
    print(f"wrote {TAPS_CSV.relative_to(REPO)}, {SUMMARY_CSV.relative_to(REPO)}, "
          f"{RECORD_MD.relative_to(REPO)}")


def sim():
    doc = klt_json("corner-matrix", "check", str(MATRIX), "--request", str(REQ),
                   env=_client_env())
    if not doc.get("complete"):
        sys.exit(f"FATAL: request does not cover the declared matrix: {doc}")
    print(f"request covers the declared matrix ({doc.get('matrix_size')} corners)")

    klt_json("sim", str(REQ), "--wait-for-capacity", "600",
             "--report-out", str(REPORT), env=_client_env())
    report = json.loads(REPORT.read_text())
    corners = report.get("corners") or []
    if len(corners) != N_CORNERS:
        sys.exit(f"FATAL: expected {N_CORNERS} corners in the report, got {len(corners)}")

    doc = klt_json("corner-matrix", "check", str(MATRIX), "--report", str(REPORT),
                   env=_client_env())
    if not doc.get("complete") or doc.get("not_simulated"):
        sys.exit(f"FATAL: report does not cover the declared matrix: "
                 f"complete={doc.get('complete')} not_simulated={doc.get('not_simulated')}")
    print(f"report covers the declared matrix ({doc.get('observed_count')} corners, all simulated)")

    rec = derive(report)
    write_csvs(rec)
    write_markdown(rec, report)
    if rec["n_failed"]:
        bad = [r["corner_id"] for r in rec["rows"] if r["note"]]
        sys.exit(f"FATAL: {rec['n_failed']} corner(s) failed measurement: {bad[:10]}")
    if rec["monotonic_all"]:
        print("RESULT: monotonic at every corner (rise and fall).")
    else:
        print("RESULT: NOT monotonic at every corner -- see RECORD.md; "
              "decision 0003 stays in force until a superseding record, and the "
              "PR says so.")


def derive_cmd():
    path = Path(sys.argv[2]) if len(sys.argv) > 2 else REPORT
    report = json.loads(path.read_text())
    rec = derive(report)
    write_csvs(rec)
    write_markdown(rec, None)
    if rec["n_failed"]:
        sys.exit(f"FATAL: {rec['n_failed']} corner(s) failed measurement")
    print(f"derived from {path}: {rec['n_corners']} corners, "
          f"monotonic_all={rec['monotonic_all']}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] in ("sim", "derive"):
        {"sim": sim, "derive": derive_cmd}[sys.argv[1]]()
    else:
        sys.exit(__doc__)
