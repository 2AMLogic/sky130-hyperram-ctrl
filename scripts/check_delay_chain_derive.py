#!/usr/bin/env python3
"""Check flow/delay_chain.py's derivation, without ngspice, klt or the fleet.

The campaign itself needs a PDK and the batch fleet (and is local_only); the
derivation that turns its report into the committed record is pure, so it is
checked here against small fixed report fixtures. Covers what the issue's
test plan calls out:

- the monotonic verdict and the per-tap min/max ratios come out right;
- a deliberately NON-monotonic fixture is reported as a failure, not
  smoothed over;
- a corner whose measurement returns a non-pass status (or an empty series)
  appears in the record as a failure with empty delays, and the runner-level
  failure count sees it;
- a report missing expected corners raises (a partial collection must fail
  loudly, never ratio over what happened to come back);
- the derive subcommand refuses a report that is not the full 45-corner
  collection -- too few or too many corners, or wrong corner ids -- before
  anything is written.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "flow"))
import delay_chain  # noqa: E402


def corner(cid, process, temp, vdd, times_by_name, status="pass"):
    """One report corner whose crossings times are given verbatim."""
    meas = []
    for name, t in times_by_name.items():
        entry = {"name": name, "status": "pass", "value": 1}
        if t is None:
            entry["status"] = "error"
            entry["value"] = None
        else:
            entry["crossings"] = {"times": [t], "edges": [name.rsplit("_", 1)[1]],
                                  "truncated": False}
        meas.append(entry)
    return {
        "corner_id": cid,
        "process": process,
        "temperature_c": temp,
        "supply_v": {"vdd": vdd, "vrwds": vdd},
        "status": status,
        "measurements": meas,
    }


def chain_times(t_in, delays_ns, edge):
    """Input crossing + per-tap absolute crossing times (s) for one edge."""
    return [t_in] + [t_in + d * 1e-9 for d in delays_ns]


def full_corner(cid, process, temp, vdd, rise_delays, fall_delays,
                t_rise=2.075e-9, t_fall=22.075e-9):
    names = {}
    for edge, delays in (("rise", rise_delays), ("fall", fall_delays)):
        times = chain_times(t_rise if edge == "rise" else t_fall, delays, edge)
        names[f"in_{edge}"] = times[0]
        for k, t in enumerate(times[1:]):
            names[f"tap{k}_{edge}"] = t
    return corner(cid, process, temp, vdd, names)


RISE = [0.75, 1.50, 2.25, 3.00, 3.75, 4.50, 5.25, 5.95]
FALL = [0.77, 1.51, 2.26, 3.01, 3.75, 4.50, 5.25, 5.98]

failures = []


def check(name, got, want):
    if got != want:
        failures.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"ok {name}")


# 1. Monotonic two-corner fixture: verdict true, ratios exact.
report = {"corners": [
    full_corner("tt/vdd=1.800V/27C", "tt", 27, 1.80, RISE, FALL),
    full_corner("ss/vdd=1.620V/125C", "ss", 125, 1.62,
                [d * 1.4 for d in RISE], [d * 1.4 for d in FALL]),
]}
rec = delay_chain.derive(report)
check("monotonic_all", rec["monotonic_all"], True)
check("n_failed", rec["n_failed"], 0)
check("ratio tap7 rise", round(rec["summary"][7]["rise_minmax_ratio"], 6), 1.4)
check("ratio tap0 fall min", round(rec["summary"][0]["fall_min_ns"], 4), 0.77)
check("ratio tap0 fall max", round(rec["summary"][0]["fall_max_ns"], 4), round(0.77 * 1.4, 4))

# 2. Deliberately non-monotonic (tap2 falls below tap1 at one corner, rise
#    only): must be reported as a failure, never smoothed over.
bad_rise = list(RISE)
bad_rise[2] = bad_rise[1] - 0.01
report2 = {"corners": [
    full_corner("tt/vdd=1.800V/27C", "tt", 27, 1.80, RISE, FALL),
    full_corner("ff/vdd=1.980V/-40C", "ff", -40, 1.98, bad_rise, FALL),
]}
rec2 = delay_chain.derive(report2)
check("non-monotonic monotonic_all", rec2["monotonic_all"], False)
ff = next(r for r in rec2["rows"] if r["process"] == "ff")
check("non-monotonic corner flag", ff["monotonic_rise"], False)
check("non-monotonic fall still ok", ff["monotonic_fall"], True)

# 3. A measurement error appears in the record as a failure.
broken = full_corner("tt/vdd=1.800V/27C", "tt", 27, 1.80, RISE, FALL)
for m in broken["measurements"]:
    if m["name"] == "tap5_fall":
        m["status"] = "error"
        m["value"] = None
        del m["crossings"]
rec3 = delay_chain.derive({"corners": [broken]})
check("error corner counted failed", rec3["n_failed"], 1)
row3 = rec3["rows"][0]
check("error note recorded", "tap5_fall" in row3["note"], True)
check("error monotonic is None", row3["monotonic_fall"], None)

# 3b. An empty crossing series (level never reached) is the same failure.
hollow = full_corner("tt/vdd=1.800V/27C", "tt", 27, 1.80, RISE, FALL)
for m in hollow["measurements"]:
    if m["name"] == "tap7_rise":
        m["crossings"]["times"] = []
rec3b = delay_chain.derive({"corners": [hollow]})
check("empty-series corner counted failed", rec3b["n_failed"], 1)
check("empty-series note", "empty crossing series" in rec3b["rows"][0]["note"], True)

# 3c. A corner-level error status is a failure too.
rec3c = delay_chain.derive({"corners": [
    corner("ss/vdd=1.620V/125C", "ss", 125, 1.62, {}, status="error")]})
check("error corner status", rec3c["n_failed"], 1)

# 4. A report missing expected corners raises -- no ratio over a subset.
try:
    delay_chain.derive(report, expected_ids=["tt/vdd=1.800V/27C", "ss/vdd=1.620V/125C",
                                             "sf/vdd=1.800V/27C"])
    failures.append("missing corners: DeriveError was not raised")
    print("FAIL missing corners: no raise")
except delay_chain.DeriveError as e:
    check("missing corners raises with count", "1 of 3" in str(e), True)

# 5. The derive SUBCOMMAND refuses a report that is not the full 45-corner
#    collection before writing anything (the sim path asserts the same count;
#    `delay_chain.py derive <partial report>` must not ratio over a subset
#    either), and a non-default report is also checked by corner id against
#    the committed collection. The committed record files must be untouched.
REC_BEFORE = {f: f.read_bytes() for f in
              (delay_chain.RECORD_MD, delay_chain.TAPS_CSV, delay_chain.SUMMARY_CSV)}


def derive_cmd_exit_code(report_path):
    """Run delay_chain.derive_cmd as if invoked on report_path; return its
    exit value (None if it returned instead of exiting)."""
    old_argv = sys.argv
    sys.argv = ["delay_chain.py", "derive", str(report_path)]
    try:
        delay_chain.derive_cmd()
        return None
    except SystemExit as e:
        return e.code
    finally:
        sys.argv = old_argv


try:
    with tempfile.TemporaryDirectory() as td:
        # 5a. Too few corners: refused with the expected count in the message.
        p = Path(td) / "partial.report.json"
        p.write_text(json.dumps(report))
        code = derive_cmd_exit_code(p)
        check("partial derive_cmd refuses", isinstance(code, str)
              and "expected 45 corners" in code, True)

        # 5b. Too many corners: the count is exact, not a lower bound.
        p = Path(td) / "oversized.report.json"
        p.write_text(json.dumps({"corners": [
            full_corner(f"tt{i}/vdd=1.800V/27C", "tt", 27, 1.80, RISE, FALL)
            for i in range(46)]}))
        code = derive_cmd_exit_code(p)
        check("oversized derive_cmd refuses", isinstance(code, str)
              and "expected 45 corners" in code, True)

        # 5c. Full count but wrong ids: a non-default report is checked BY NAME
        #     against the committed collection's corner ids (the only in-repo
        #     source of real klt-format ids), so this is refused and named.
        p = Path(td) / "wrongids.report.json"
        wrong = json.loads(delay_chain.REPORT.read_text())
        wrong["corners"][0]["corner_id"] = "not-a-real-klt-id"
        p.write_text(json.dumps(wrong))
        code = derive_cmd_exit_code(p)
        check("wrong-ids derive_cmd refuses by name", isinstance(code, str)
              and "missing 1 of 45" in str(code), True)

    check("derive_cmd partial collection wrote nothing",
          {f: f.read_bytes() for f in REC_BEFORE} == REC_BEFORE, True)
finally:
    # A regressed guard writes the committed records; the check reports that
    # (above) and must not also leave the checkout dirty. Compare before
    # restoring: the assertion above must see the drift to detect it.
    for f, before in REC_BEFORE.items():
        if f.read_bytes() != before:
            f.write_bytes(before)

# 6. render_provenance: runner/client klt version compare has THREE outcomes;
#    equal versions must not claim a skew (append-only record, no false line).
def _prov_skew_line(runner_v, client_v):
    rep = json.loads(delay_chain.REPORT.read_text())
    remote = rep["environment"]["remote"]
    remote["runner_klt_version"] = runner_v
    remote["client_klt_version"] = client_v
    return [ln for ln in delay_chain.render_provenance(rep).split("\n")
            if ln.startswith("- runner/client klt")][0]


eq = _prov_skew_line("0.9.2", "0.9.2")
check("provenance equal versions: no skew claimed",
      ("no skew" in eq, "deliberate" in eq, "newer side" in eq),
      (True, False, False))
check("provenance runner older: client newer",
      "the client is the newer side" in _prov_skew_line("0.9.0", "0.9.2"), True)
check("provenance runner newer: runner newer",
      "the runner is the newer side" in _prov_skew_line("0.9.3", "0.9.2"), True)
check("provenance unparseable: unknown",
      "could not be determined" in _prov_skew_line("dev", "0.9.2"), True)

if failures:
    print()
    for f in failures:
        print(f"FAIL {f}")
    sys.exit(1)
print()
print("check_delay_chain_derive: all cases pass")
