#!/usr/bin/env python3
"""Structurally assert the shared tap delay's decode in the committed netlist.

Why this exists (PR #148 review). The controller benches
(`make -C verification/ctrl`, 43/43) cannot cover the tap arithmetic of
`rtl/hyperram_ctrl/hr_tap_delay.v`: the simulation stand-ins
(`rtl/hyperram_ctrl/sim/sky130_cells_behav.v`) map
`sky130_fd_sc_hd__dlygate4sd3_1` to a zero-delay pass-through, so every node
on the chain carries the same value and no tap decode or chain-length
mutation can change a bench result. Issue #101 step 4 originally claimed the
opposite; both a wrong-tap-decode and an off-by-one-length mutation of the
PR's own module were shown to leave the suite green. "No claim without a
testbench" (CLAUDE.md) applies to the refactor's own safety claim, so this
checker is the testbench for it.

What is asserted, on the committed gate-level netlist
(`sim/hyperram/records/hyperram_ctrl.netlist.v`, the same artifact the fleet
regeneration re-synthesizes byte-for-byte before place-and-route):

  1. `hr_tap_delay` contains exactly 16 `dlygate4sd3_1` cells forming one
     linear series from `in_sig` through `dly[1]` .. `dly[16]` (tap k selects
     2*(k+1) cells, decision 0001/0003 numbering -- the contract now carried
     in the RTL module header).
  2. The tap mux tree implements `taps[tap_sel]` with
     `taps = {dly[16], dly[14], ..., dly[2]}`: exactly two `mux4` cells and
     one `mux2` cell, the mux2 driving `out_sig`, and -- evaluated over all
     8 select values through the cells' actual select connectivity -- each
     selected node is `dly[2*(k+1)]`.

It is a pure read of a committed artifact: no yosys, no klt, no PDK, so it
runs on every PR from `scripts/check_ci.sh` (step 3c) and again inside
`scripts/fleet-regen-layout.sh` on the freshly synthesized netlist, before
that netlist is timed and placed.

  scripts/check_tap_decode.py               check the committed netlist (CI)
  scripts/check_tap_decode.py --self-test   check this checker, on fixtures

The self-test drives the same assertions over fixture netlists, including
the two mutations the benches miss -- the odd-index decode and the 15-cell
off-by-one -- plus a swapped mux select wiring and a forked chain node;
each broken fixture must FAIL the checker. That matters because this file
is the only thing standing between a broken decode and a green CI: "it
catches the hole" is a claim that needs its own testbench (the
check_bench_coverage.py precedent, issue #93).

Exit 0 when the netlist's decode is the ratified one, 1 otherwise.
"""

import contextlib
import io
import pathlib
import re
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
NETLIST = REPO / "sim" / "hyperram" / "records" / "hyperram_ctrl.netlist.v"
MODULE = "hr_tap_delay"
DEPTH = {k: 2 * (k + 1) for k in range(8)}  # tap k selects 2*(k+1) cells

# One instance statement: `cell_type name ( .PORT(node), ... );` -- the
# pinned yosys writes one port per line with the terminator `);` on its own
# line, so a non-greedy match to the first `);` is exactly one instance.
INST_RE = re.compile(r"(sky130_fd_sc_hd__\w+)\s+\S+\s*\((.*?)\);", re.S)
PORT_RE = re.compile(r"\.(\w+)\s*\(\s*([^)]*?)\s*\)")
SEL_BIT_RE = re.compile(r"tap_sel\[(\d+)\]")


def instances(module_body):
    """[(cell_type, {port: node}), ...] for every instance in `module_body`."""
    return [(cell, dict(PORT_RE.findall(ports))) for cell, ports in INST_RE.findall(module_body)]


def chain_nodes(insts):
    """The linear series as [start, node_after_cell_1, ...], or None if the
    dlygate population is not exactly one chain: 16 cells, every node
    driving exactly one cell, no forks, no dangling cells."""
    gates = [p for c, p in insts if c == "sky130_fd_sc_hd__dlygate4sd3_1"]
    if len(gates) != 16:
        return None
    edges = {}
    for p in gates:
        src, dst = p["A"], p["X"]
        if src in edges:  # a node feeding two cells is not a linear series
            return None
        edges[src] = dst
    node, seen = "in_sig", []
    while node in edges:
        node = edges[node]
        seen.append(node)
    return ["in_sig"] + seen if len(seen) == 16 else None


def sel_bit(conn, sel):
    """Value of the tap_sel bit a mux select port is wired to, at `sel`."""
    m = SEL_BIT_RE.fullmatch(conn)
    if not m:
        raise ValueError(f"mux select port wired to {conn!r}, not a tap_sel bit")
    return (sel >> int(m.group(1))) & 1


def selected_depths(insts):
    """[node selected for tap_sel=k, k=0..7] through the mux tree's actual
    connectivity, or None if the tree is not exactly two mux4 + one mux2
    with the mux2 driving out_sig. May raise ValueError when a select port
    is wired to something other than a tap_sel bit."""
    m4 = [p for c, p in insts if re.fullmatch(r"sky130_fd_sc_hd__mux4_\w+", c)]
    m2 = [p for c, p in insts if re.fullmatch(r"sky130_fd_sc_hd__mux2_\w+", c)]
    if len(m4) != 2 or len(m2) != 1 or m2[0]["X"] != "out_sig":
        return None
    mux2 = m2[0]
    picks = []
    for sel in range(8):
        m4_outs = []
        for m in m4:
            # sky130_fd_sc_hd__mux4: X = A[{S1,S0}] (00->A0 .. 11->A3)
            idx = (sel_bit(m["S1"], sel) << 1) | sel_bit(m["S0"], sel)
            m4_outs.append(m[f"A{idx}"])
        # sky130_fd_sc_hd__mux2: X = S ? A1 : A0
        picks.append(m4_outs[1] if sel_bit(mux2["S"], sel) else m4_outs[0])
    return picks


def run_check(netlist_path):
    """Print the report; return the exit code."""
    try:
        rel = netlist_path.relative_to(REPO)
    except ValueError:  # fixture outside the repo: show the absolute path
        rel = netlist_path
    text = netlist_path.read_text()
    hit = re.search(rf"module\s+{MODULE}\s*\(.*?\);(.*?)endmodule", text, re.S)
    if not hit:
        print(f"::error file={rel}::no {MODULE} module in the netlist")
        return 1
    insts = instances(hit.group(1))

    ok = True
    chain = chain_nodes(insts)
    want_chain = ["in_sig"] + [f"dly[{k}]" for k in range(1, 17)]
    if chain != want_chain:
        ok = False
        n_gates = len([c for c, _ in insts if c == "sky130_fd_sc_hd__dlygate4sd3_1"])
        print(
            f"::error file={rel}::{MODULE}'s dlygate cells are not one linear"
            f" 16-cell series in_sig -> dly[16] ({n_gates} dlygate cell(s);"
            f" series: {chain})"
        )
    depths = None
    depth_err = None
    try:
        depths = selected_depths(insts)
    except ValueError as exc:
        depth_err = str(exc)
    want_depths = [f"dly[{DEPTH[k]}]" for k in range(8)]
    if depths != want_depths:
        ok = False
        found = depths
        if not depths:
            found = (
                f"broken select wiring ({depth_err})"
                if depth_err
                else "no two-mux4-plus-one-mux2 tree driving out_sig"
            )
        print(
            f"::error file={rel}::{MODULE}'s tap mux does not select"
            f" depths 2,4,..16 (taps[k] = dly[2*(k+1)]); found: {found}"
        )
    if ok:
        print(
            f"ok {rel}: {MODULE} is one linear 16-cell dlygate series,"
            " tap mux selects depths 2,4,..16 for tap_sel=0..7"
        )
        return 0
    print(
        "A changed decode here means hr_tap_delay.v (or its synthesis) drifted"
        " from the ratified tap contract: tap k selects 2*(k+1) cells. Fix the"
        " RTL and re-run the netlist regeneration (scripts/fleet-regen-layout.sh)"
        " -- do not edit the committed netlist by hand."
    )
    return 1


# --- self-test -------------------------------------------------------------

failures = []


def record(ok, name, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"\n       {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def fixture_netlist(n_cells=16, depths=None, swap_selects=False):
    """A netlist-shaped hr_tap_delay module, yosys-formatted like the
    committed artifact. `depths` lists the 8 mux data inputs in the order
    (mux4_a A0..A3, mux4_b A0..A3); the committed decode is
    [2, 10, 6, 14, 4, 12, 8, 16]."""
    if depths is None:
        depths = [2, 10, 6, 14, 4, 12, 8, 16]
    lines = [f"module {MODULE}(in_sig, tap_sel, out_sig);"]
    lines += ["  wire [16:0] dly;", "  wire [7:0] taps;"]
    a, b = depths[:4], depths[4:]
    s0, s1 = ("tap_sel[1]", "tap_sel[2]") if swap_selects else ("tap_sel[2]", "tap_sel[1]")
    for tag, ports, x in (("_2_", a, "_0_"), ("_3_", b, "_1_")):
        lines += [
            f"  sky130_fd_sc_hd__mux4_1 {tag} (",
            *[f"    .A{i}(dly[{d}])," for i, d in enumerate(ports)],
            f"    .S0({s0}),",
            f"    .S1({s1}),",
            f"    .X({x})",
            "  );",
        ]
    lines += [
        "  sky130_fd_sc_hd__mux2_2 _4_ (",
        "    .A0(_0_),",
        "    .A1(_1_),",
        "    .S(tap_sel[0]),",
        "    .X(out_sig)",
        "  );",
    ]
    for k in range(n_cells):
        src = "in_sig" if k == 0 else f"dly[{k}]"
        lines += [
            f"  sky130_fd_sc_hd__dlygate4sd3_1 \\g_dly[{k}].u_dly (",
            f"    .A({src}),",
            f"    .X(dly[{k + 1}])",
            "  );",
        ]
    lines += ["  assign dly[0] = in_sig;", "endmodule", ""]
    return "\n".join(lines)


def check_fixture(name, text, expect_ok):
    """Run the checker over a fixture netlist; the fixture must pass exactly
    when `expect_ok`. Returns (behaved_as_required, checker output)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "net.v"
        path.write_text(text)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = run_check(path)
        return rc == (0 if expect_ok else 1), buf.getvalue().strip()


def self_test():
    good = fixture_netlist()
    record(
        check_fixture("correct decode passes", good, True)[0],
        "fixture: ratified 16-cell / 2,4,..16 decode passes",
    )
    ok, _ = check_fixture(
        "odd decode", fixture_netlist(depths=[1, 9, 5, 13, 3, 11, 7, 15]), False
    )
    record(ok, "fixture: odd-index decode (the bench-invisible mutation) fails")
    ok, _ = check_fixture("short chain", fixture_netlist(n_cells=15), False)
    record(ok, "fixture: 15-cell off-by-one chain length fails")
    ok, _ = check_fixture("swapped selects", fixture_netlist(swap_selects=True), False)
    record(ok, "fixture: S0/S1 select wiring swap fails")
    # Fork, not count: still exactly 16 cells, but dly[3] feeds two of them.
    forked = good.replace(
        "  sky130_fd_sc_hd__dlygate4sd3_1 \\g_dly[5].u_dly (\n    .A(dly[5]),",
        "  sky130_fd_sc_hd__dlygate4sd3_1 \\g_dly[5].u_dly (\n    .A(dly[3]),",
    )
    ok, out = check_fixture("forked node", forked, False)
    record(ok, "fixture: one node feeding two cells fails", out if not ok else "")
    if failures:
        print(f"\n{len(failures)} self-test case(s) failed: {failures}")
        return 1
    print("\ntap-decode checker self-test: all fixtures behave as required")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    return run_check(NETLIST)


if __name__ == "__main__":
    sys.exit(main())
