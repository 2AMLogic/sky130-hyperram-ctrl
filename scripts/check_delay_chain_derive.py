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
  loudly, never ratio over what happened to come back).
"""

import sys
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

if failures:
    print()
    for f in failures:
        print(f"FAIL {f}")
    sys.exit(1)
print()
print("check_delay_chain_derive: all cases pass")
