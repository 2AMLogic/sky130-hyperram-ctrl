#!/usr/bin/env python3
"""Synthesis runner for the controller RTL (rtl/hyperram_ctrl/).

  hyperram.py synth   run `klt synthesize` on flow/synthesize-hyperram.json and
                      write the netlist + stat report to sim/hyperram/records/
  hyperram.py check   re-synthesize into a temp dir and compare byte-for-byte
                      with the committed netlist; exit 3 if stale (T1 item 1
                      freshness check, see attest/item1.json)
  hyperram.py sta     run `klt sta` on that netlist (clk at 20 ns, ideal clock, no
                      wire load, no pads) at every sky130_fd_sc_hd liberty corner
                      the pinned PDK ships, write the response to
                      sim/hyperram/records/sta.json and a note beside it, and fail
                      on negative slack only inside decision 0004's supply window
  hyperram.py layout  run `klt place-and-route` on layout/place-and-route.json
                      (the netlist above, 50 MHz, PDN + tapcells) and commit
                      the routed outputs to layout/records/ plus the T1 item 2
                      envelope evidence/item2.json
  hyperram.py layout-check
                      verify the committed response against the request
                      (netlist and liberty hashes) and the item-2 envelope
                      against the committed GDS; no OpenROAD run

klt runs through scripts/klt.sh (the pin and the resolution rule), so it does
not depend on $PATH; yosys and the PDK still do (scripts/setup-env.sh).

`synth` and `check` both refuse to answer unless the yosys that actually ran is
the pinned one (exit 4, distinct from 3/STALE): klt resolves yosys from $PATH,
so without .venv/bin first it silently synthesizes with the host yosys, and a
netlist or freshness result minted that way does not reproduce (issue #81).
Both halves of the pin are checked, because the version string is not an
identity on its own -- any yosys reporting 0.68 used to pass, a native build
with a different ABC included (issue #89). The second half is the yosys.wasm
sha256 of the yowasp-yosys wheel the $PATH `yosys` belongs to: the build
identity `yosys -V` does not report, already pinned in scripts/setup-env.sh.
scripts/check_yosys_gate.py exercises the reject paths in CI, where there is
no yosys to run.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# flow/klt_run.py is the only way this runner reaches klt; `python3 -I` (how
# attest/item1.json runs the freshness check) keeps flow/ off sys.path, so put
# it there from __file__ before importing.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from klt_run import REPO, klt, klt_json  # noqa: E402

SETUP_ENV = REPO / "scripts/setup-env.sh"
# Exit status for "the wrong yosys answered". Deliberately not 3: 3 means the
# committed netlist was compared and differs, and here it was never compared.
WRONG_YOSYS_EXIT = 4

REC = REPO / "sim/hyperram/records"
NETLIST = REC / "hyperram_ctrl.netlist.v"
STAT = REC / "synth-stat.json"
REQ = REPO / "flow/synthesize-hyperram.json"
STA_REQ = REPO / "flow/sta-hyperram.json"
STA_REC = REC / "sta.json"
STA_NOTE = REC / "STA.md"
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
# Decision 0004's core supply: 1.8 V +/- 10 %. The PDK ships liberty below
# 1.62 V as well, and the same decision's "all liberty corners" line does not
# reconcile the two -- settling that is #2's, not this runner's. So `sta` grades
# only the corners inside the ratified window and reports the rest ungraded,
# the way layout/README.md already reports the stale place-and-route numbers.
# Both 1.60 V corners miss the floor by 20 mV and are therefore ungraded; that
# is the window's arithmetic, not a judgement about them.
VMIN_V, VMAX_V = 1.62, 1.98
# Corner names are <model>_<temp>_<supply>, e.g. ss_n40C_1v76 -> 1.76 V. The
# suffix is the only copy of a corner's voltage: the list of corner names lives
# in flow/sta-hyperram.json and nowhere else, so classification parses the name
# rather than keeping a second in/out-of-window list here to fall out of date.
CORNER_V_RE = re.compile(r"_(\d)v(\d{2})$")
KEYS = ("engine", "engine_version", "hdl_toplevel", "instance_count", "area_um2", "sequential_area_um2",
        "instance_counts_by_type", "leakage_power_nw", "blackbox_modules", "structural")


def pinned_yosys():
    """(wheel version, engine version, yosys.wasm sha256) of the pinned yosys.

    scripts/setup-env.sh is the only place this repo writes the yosys pin -- it
    installs that wheel and verifies its yosys.wasm sha256 -- so read it from
    there instead of keeping a second copy here. Three strings, because no one
    of them identifies the build on its own:

      * the *wheel* version (`0.68.0.0.post1208`), what the pin installs;
      * the *engine* version the binary itself prints (`0.68`), which is what
        `klt synthesize` reports back. YoWASP numbers its wheels
        `<upstream yosys version>.<build>.<n>.post<n>`, so the upstream version
        is the leading two components. If YoWASP ever renumbers, this stops the
        flow with a mismatch instead of letting an unverified yosys through;
      * the sha256 of the wheel's yosys.wasm, the Yosys/ABC build identity that
        `yosys -V` does not report (scripts/setup-env.sh says so in its header,
        and verifies it once at install time). A different yosys reporting the
        same `0.68` has a different wasm, which is the whole point of pinning it.
    """
    text = SETUP_ENV.read_text()
    m = re.search(r'^YOWASP_YOSYS_VERSION="([^"]+)"$', text, re.M)
    if not m:
        sys.exit(f"FATAL: no YOWASP_YOSYS_VERSION= pin in {rel(SETUP_ENV)}; "
                 "cannot tell which yosys is the pinned one")
    wheel = m.group(1)
    parts = wheel.split(".")
    if len(parts) < 2 or not all(p.isdigit() for p in parts[:2]):
        sys.exit(f"FATAL: cannot read an engine version out of the yosys pin "
                 f"{wheel!r} in {rel(SETUP_ENV)}")
    h = re.search(r'^YOWASP_YOSYS_WASM_SHA256="([0-9a-f]{64})"$', text, re.M)
    if not h:
        sys.exit(f"FATAL: no YOWASP_YOSYS_WASM_SHA256= pin in {rel(SETUP_ENV)}; "
                 "cannot tell which yosys *build* is the pinned one, and the "
                 "version string alone does not say")
    return wheel, ".".join(parts[:2]), h.group(1)


# The four lines scripts/setup-env.sh:81-84 pipes to the venv python to verify
# the pin at install time. Kept identical on purpose: this is the same question
# asked of the same wheel, just at mint time instead of install time.
WASM_HASH_SNIPPET = (
    "import hashlib, os\n"
    "import yowasp_yosys\n"
    'p = os.path.join(os.path.dirname(yowasp_yosys.__file__), "yosys.wasm")\n'
    'print(hashlib.sha256(open(p, "rb").read()).hexdigest())\n'
)


def path_yosys_build():
    """(what `yosys` on $PATH resolves to, the yosys.wasm sha256 of its wheel).

    The sha256 is None when the resolved yosys is not a yowasp-yosys console
    script: a native binary, or a wheel whose module will not import. A caller
    must read None as "not the pinned build" and stop, never as "nothing to
    check" -- a yosys whose build cannot be identified is precisely the case
    issue #89 is about, so it has to fail closed.

    Resolution deliberately mirrors klt's own. `shutil.which("yosys")` is the
    same bare name off the same $PATH that `klt synthesize` resolves (verified
    in the pinned klayout-tools wheel: it runs `subprocess.run(["yosys", ...])`
    and exposes no binary override), and flow/klt_run.py passes no `env=`, so
    klt inherits this process's environment.

    scripts/setup-env.sh:90 makes .venv/bin/yosys a relative symlink to the
    sibling `yowasp-yosys` console script, so realpath's parent is that
    environment's bin/ -- and that bin/'s own python3 is the interpreter which
    imports the wheel the $PATH yosys actually belongs to. Using it, rather than
    importing yowasp_yosys here, is the point: attest/item1.json runs this file
    as `python3 -I`, which need not be the venv's python at all.
    """
    found = shutil.which("yosys")
    if found is None:
        return None, None
    found = os.path.realpath(found)
    py = Path(found).parent / "python3"
    if not py.exists():
        return found, None
    proc = subprocess.run([str(py), "-I", "-B", "-c", WASM_HASH_SNIPPET],
                          capture_output=True, text=True)
    got = proc.stdout.strip()
    if proc.returncode != 0 or not re.fullmatch(r"[0-9a-f]{64}", got):
        return found, None
    return found, got


def require_pinned_yosys(doc):
    """Stop unless the yosys that answered this run is the pinned one.

    klt takes yosys from $PATH and reports which one answered only afterwards,
    in the response, so this is the first point at which the identity is
    knowable -- and the last before the result is committed or compared.
    Without it, a run whose $PATH lacks .venv/bin synthesizes with the host
    yosys and the result looks ordinary; that is how a 0.67+post netlist was
    committed and recorded as a passing freshness check (issue #81).

    Both halves of the pin are checked, because each answers a question the
    other cannot:

      * `engine`/`engine_version` from the response is the only *post-hoc*
        signal -- the only one that speaks for the process that actually
        answered. It is also all klt gives: the response carries no git sha1 and
        no full version line (see sim/hyperram/records/synth-stat.json).
      * the yosys.wasm sha256 of the $PATH yosys is the only *build* identity.
        The version string is not one: until issue #89 any yosys reporting
        `0.68` passed, a natively built 0.68 with a different ABC included, and
        such a run would have minted a netlist here with no warning.

    Known limit, stated rather than solved: the build half is not atomic with
    klt's own resolution. It inspects what $PATH resolves `yosys` to in this
    process, after klt resolved the identical bare name in its own subprocess
    off this same environment. The two agree in any ordinary run; a $PATH
    mutated mid-run would defeat it, and nothing in the response would show it.
    """
    wheel, want, want_sha = pinned_yosys()
    engine, got = doc.get("engine"), doc.get("engine_version")
    if engine != "yosys" or got != want:
        print(f"WRONG TOOL: this synthesis ran {engine} {got}, but the pin is "
              f"yowasp-yosys {wheel} (reports {want}); a netlist or freshness "
              f"result from {engine} {got} does not reproduce under the pin.\n"
              f"  Put .venv/bin first on $PATH (the Makefiles do) or re-run "
              f"{rel(SETUP_ENV)}.", file=sys.stderr)
        sys.exit(WRONG_YOSYS_EXIT)
    found, got_sha = path_yosys_build()
    if got_sha != want_sha:
        if found is None:
            actual = "no `yosys` on $PATH at all"
        elif got_sha is None:
            actual = (f"{found}, which is not a yowasp-yosys wheel entry point "
                      f"(no importable yowasp_yosys/yosys.wasm beside it to hash)")
        else:
            actual = f"{found}, whose yosys.wasm is sha256:{got_sha}"
        print(f"WRONG TOOL: this synthesis reported yosys {want}, but the "
              f"`yosys` on $PATH is not the pinned build.\n"
              f"  expected: the yowasp-yosys {wheel} wheel, "
              f"yosys.wasm sha256:{want_sha}\n"
              f"  actual:   {actual}\n"
              f"  The reported version does not identify the build -- a "
              f"natively built yosys {want} reports the same {want} and is a "
              f"different Yosys/ABC (issue #89). The pin is in "
              f"{rel(SETUP_ENV)}: put .venv/bin first on $PATH (the Makefiles "
              f"do) or re-run it.", file=sys.stderr)
        sys.exit(WRONG_YOSYS_EXIT)


def run_synth():
    doc = klt_json("synthesize", str(REQ))
    netlist = (REPO / doc["netlist_path"]["path"]).read_bytes()
    shutil.rmtree(REPO / "flow/.klt", ignore_errors=True)
    require_pinned_yosys(doc)
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


def pdk_env():
    """The layout commands need PDK set; default it the way the Makefile does."""
    return dict(os.environ, PDK=os.environ.get("PDK", "sky130A"))


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
    doc = klt_json("place-and-route", str(LREQ), env=pdk_env())
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
    proc = klt("place-and-route", str(LREQ), "--check", str(RESPONSE), env=pdk_env())
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        print(f"STALE: {rel(RESPONSE)} no longer matches the request inputs; run `make layout`")
        sys.exit(3)
    bound = json.loads(ITEM2.read_text())["provenance"]["input"]["content_hash"]
    if bound != sha256(LREC / "hyperram_ctrl.gds"):
        print(f"STALE: {rel(ITEM2)} binds a different GDS than {rel(LREC)}/hyperram_ctrl.gds; run `make layout`")
        sys.exit(3)
    print("layout record is fresh")


def corner_volts(name):
    """The supply voltage a corner name encodes, e.g. ss_n40C_1v76 -> 1.76."""
    m = CORNER_V_RE.search(name or "")
    if not m:
        sys.exit(f"FATAL: cannot read a supply voltage out of corner name {name!r}; "
                 f"`sta` classifies corners in/out of {VMIN_V}-{VMAX_V} V by their "
                 f"_<n>v<nn> suffix, so a corner it cannot parse cannot be graded")
    return float(f"{m.group(1)}.{m.group(2)}")


def in_window(name):
    """Is this corner's supply inside decision 0004's ratified window?"""
    return VMIN_V <= corner_volts(name) <= VMAX_V


def liberty_read_by(entry):
    """The liberty file klt's own OpenSTA script read for this corner.

    Taken from the generated .tcl rather than re-derived: scripts/klt.sh holds
    the klt pin and klt holds the PDK resolution rule (`find_pdk()`/`libs_ref`),
    so a second discovery rule here could name a different file than the one
    that actually answered -- which is precisely the question being asked.
    The script lives in the untracked scratch dir flow/.klt/, so this is only
    answerable in the run that produced the response, not afterwards.
    """
    corner = entry.get("corner")
    sp = ((entry.get("engine_log") or {}).get("script_path") or {}).get("path")
    if not sp:
        sys.exit(f"FATAL: corner {corner}: the response names no repo-scoped OpenSTA "
                 f"script, so the liberty klt actually read cannot be named and the "
                 f"blackboxed cells cannot be checked against it")
    script = REPO / sp
    if not script.exists():
        sys.exit(f"FATAL: corner {corner}: {rel(script)} is gone; the scratch dir is "
                 f"untracked, so re-run `make hyperram-sta` rather than grading a "
                 f"response whose liberty cannot be inspected")
    libs = re.findall(r"^read_liberty\s+(\S+)\s*$", script.read_text(), re.M)
    if len(libs) != 1:
        sys.exit(f"FATAL: corner {corner}: expected exactly one read_liberty line in "
                 f"{rel(script)}, found {len(libs)}")
    return Path(libs[0])


def check_blackboxes_resolved(doc, cells):
    """Stop unless every cell yosys left as a blackbox is timed from real liberty.

    `klt synthesize` reports three sky130 cells as blackbox_modules -- the gated
    clock buffer, the delay-chain cell and the mux instantiated by name in the
    RTL. Yosys does not time them; OpenSTA is the first tool that does, and
    there are two ways it can fail to, neither of which shows up in a slack
    number:

      * no LEF master -- klt stops the whole run with `[ERROR ORD-2013]
        instance ... LEF master ... not found.` and flow/klt_run.py's klt_json
        turns that into a FATAL before this is reached. Confirmed by running
        this netlist with the delay cell renamed to a cell the PDK does not
        ship: klt exits 1 with that error and writes no record.
      * a LEF master but no liberty entry -- OpenSTA links the instance with no
        timing arcs, the delay chain contributes zero delay, and the response
        carries no field that says so. Nothing but the liberty answers this, so
        the liberty each corner actually read is inspected here.

    The cell list comes from the committed synth-stat.json, so it tracks the
    netlist being timed instead of being a third hardcoded copy.
    """
    for entry in doc["corners"]:
        lib = liberty_read_by(entry)
        if not lib.exists():
            sys.exit(f"FATAL: corner {entry.get('corner')}: liberty {lib} named by klt's "
                     f"own OpenSTA script is not readable")
        text = lib.read_text()
        missing = [c for c in cells if f'cell ("{c}")' not in text]
        if missing:
            sys.exit(f"FATAL: corner {entry.get('corner')}: {lib.name} defines no "
                     f"{', '.join(missing)}; those cells are blackboxes in the netlist "
                     f"({rel(STAT)} blackbox_modules), so OpenSTA timed them with no "
                     f"arcs and the delay chain is zero delay in this record")
    print(f"  blackboxed cells resolved against liberty at all {len(doc['corners'])} "
          f"corners: {', '.join(cells)}")


def sta_note(doc, cells):
    """The prose beside the record: the in/out-of-window split, what was
    assumed, what was not timed, and what the record does not prove.

    Generated from the response rather than hand-written, so no number in it
    can drift from the record it sits next to. Every sentence that is a claim
    about the run reads its own value out of `doc`.
    """
    graded = [c for c in doc["corners"] if in_window(c["corner"])]
    ungraded = [c for c in doc["corners"] if not in_window(c["corner"])]
    cc = [c["constraint_completeness"] for c in doc["corners"]]
    unclocked = sorted({c["unclocked_registers"]["count"] for c in cc})
    endpoints = sorted({c["unconstrained_endpoints"]["count"] for c in cc})
    req = json.loads(STA_REQ.read_text())
    prov = doc["provenance"]

    def rows(entries):
        return [f"| `{c['corner']}` | {corner_volts(c['corner']):.2f} | {c['worst_slack_ns']} "
                f"| {c['worst_hold_slack_ns']} | {c['fmax_mhz']} | {c['timing_status']} |"
                for c in entries]

    head = ["| corner | supply (V) | setup slack (ns) | hold slack (ns) | fmax (MHz) | status |",
            "|---|---|---|---|---|---|"]
    lines = [
        "# Pre-layout STA of the controller netlist (all shipped liberty corners)",
        "",
        "`make hyperram-sta` -> [`sta.json`](sta.json), the unmodified `klt sta` response.",
        f"Request: [`flow/{STA_REQ.name}`](../../../flow/{STA_REQ.name}) --"
        f" `{req['constraints']['clock_port']}` at {req['constraints']['clock_period_ns']} ns"
        f" (50 MHz, spec/target-spec.md row 1's target, not the 100 MHz stretch),"
        f" {len(doc['corners'])} corners in one round trip.",
        "",
        f"- Netlist: `{doc['verilog_path']['path']}`, {prov['input']['content_hash']}.",
        f"- Engine: {doc['engine']} {doc['engine_version']}; klt {prov['klt_version']};"
        f" PDK {prov['pdk']['version']}.",
        f"- `{doc['hdl_toplevel']}`, status `{doc['status']}`,"
        f" `geometry_source: {doc['geometry_source']}`.",
        "",
        "## What was assumed",
        "",
        "Read out of the response, not asserted here:",
        "",
        f"- **Ideal clock** (`clock_mode: {json.dumps(doc['clock_mode'])}`) -- no CTS, no"
        " clock-tree insertion delay, no propagated-clock latency. The reported"
        " `clock_skew_ns` is OpenSTA's ideal-network estimate.",
        f"- **No wire load** (`wire_load_model: {json.dumps(doc['wire_load_model'])}`,"
        f" `wire_load_mode: {json.dumps(doc['wire_load_mode'])}`) and **no placement or"
        f" routing** (`def_path: {json.dumps(doc['def_path'])}`,"
        f" `spef_path: {json.dumps(doc['spef_path'])}`): interconnect is OpenSTA's own"
        " estimate from the netlist. These are pre-layout numbers, not post-route ones.",
        "- **No pads.** Only `sky130_fd_sc_hd` is loaded; no `sky130_fd_io` cell, no pad"
        " delay, no bond/package model, no core-to-pad seam.",
        "- **No I/O constraints.** The request sets only the clock port and period: no"
        " input/output delay, no driving cell, no input transition, no output load. The"
        " design's ports are therefore unconstrained (below).",
        "",
        "## Corners inside the ratified supply window (graded)",
        "",
        "Decision 0004 puts the core supply at 1.8 V +/- 10 %, i.e."
        f" {VMIN_V}-{VMAX_V} V. `make hyperram-sta` fails on a negative setup or hold"
        f" slack at any of these {len(graded)} corners.",
        "",
        *head, *rows(graded),
        "",
        "## Corners outside it (reported, not graded)",
        "",
        "The PDK ships liberty at supplies decision 0004's window excludes. These"
        f" {len(ungraded)} corners are recorded and printed, and the target does not fail"
        f" on them. `ss_100C_1v60` and `ss_n40C_1v60` miss the {VMIN_V} V floor by 20 mV;"
        f" that is the window's arithmetic, not a judgement about those corners. The same"
        f" decision's \"all liberty corners\" line does not reconcile with the window --"
        f" left as found, and #2 owns settling it.",
        "",
        *head, *rows(ungraded),
        "",
        "## What was not timed",
        "",
        f"`constraint_completeness` is `{cc[0]['status']}` at every corner and the target"
        f" does not gate on it. The counts are identical across all"
        f" {len(doc['corners'])} corners:",
        "",
        f"- **{unclocked[0] if len(unclocked) == 1 else unclocked} unclocked registers.**"
        f" Every sampled pin is under `u_cap/`, the `hr_rd_capture` instance. That module"
        f" clocks its capture flops off `rwds_d` -- the input strobe after the delay chain"
        f" -- on both edges, and a `klt sta` request names exactly one `clock_port`, so"
        f" OpenSTA sees no clock on them. **The read-capture path is unconstrained and"
        f" unreported in this record.**",
        f"- **{endpoints[0] if len(endpoints) == 1 else endpoints} unconstrained"
        f" endpoints** -- the design's output ports and `cfg_rdata`, since no output"
        f" delay or load is set (above).",
        "",
        "Neither is masked. `constraints.false_path_from` would have hidden the capture"
        " path instead of recording the gap, and the request schema cannot express a"
        " second or generated clock for `rwds_d` at the pinned klt. Constraining that"
        " domain is a modelling choice that belongs to the spec (#2); its real delays"
        " belong to the ngspice delay-chain campaign (#99) and its pad-facing half to"
        " #98.",
        "",
        f"All {len(cells)} cells yosys left as blackboxes"
        f" ({', '.join('`' + c + '`' for c in cells)}) are defined in the liberty every"
        f" corner read, so the delay chain is timed with real cell delays rather than as"
        f" zero delay. `make hyperram-sta` fails if that is ever untrue.",
        "",
        "## What this does not prove",
        "",
        "This is the **STA, all core** half of `spec/target-spec.md` row 1's proof"
        " (\"STA + SPICE pad timing\", corners \"all core + all ngspice\") and nothing"
        " more. It is **not** a proof of row 11 (read capture), row 12 (read-capture"
        " margin), row 14 (write path) or row 19 (timing at the pins): each of those"
        " needs the pads, SPICE, or the strobe domain, none of which are in this record."
        " **No spec row is called met here** -- the rows and their proof status are"
        " `spec/`'s to state (#2, #100), and the manifests and signoff record are"
        " untouched by this target.",
        "",
        "Also not here: place-and-route, wire load, SPEF, DRC/LVS (`layout/`, #52), and"
        " any claim about 100 MHz -- the `fmax_mhz` column is OpenSTA's ideal-clock,"
        " no-wire-load estimate for the `clk` domain alone, reported, not graded.",
    ]
    return "\n".join(lines) + "\n"


def sta():
    """`klt sta` on the committed netlist at every shipped liberty corner.

    Mirrors flow/smoke.py's `sta` verb, with two differences the design (rather
    than the smoke counter) forces:

      * the gate is asymmetric -- graded inside decision 0004's supply window,
        reported outside it (see VMIN_V/VMAX_V);
      * the response is checked for things a slack number cannot show: the
        corner set actually answered, and that the blackboxed cells were timed
        from liberty (AC 8 of issue #97).

    Order matters. The response's shape is validated *before* anything is
    written, so a structurally broken run cannot overwrite good evidence; the
    record and the note are then written unconditionally, and the slack gate
    runs last. A timing failure at an in-window corner must still leave the
    evidence on disk -- it is reported, not tuned away.
    """
    if not NETLIST.exists():
        sys.exit(f"FATAL: {rel(NETLIST)} missing; run `make hyperram-synth`")
    if not STAT.exists():
        sys.exit(f"FATAL: {rel(STAT)} missing; run `make hyperram-synth`")
    cells = json.loads(STAT.read_text())["blackbox_modules"]
    want = list(json.loads(STA_REQ.read_text())["pdk"]["corners"])

    doc = klt_json("sta", str(STA_REQ), env=pdk_env())
    if doc.get("status") != "ok":
        sys.exit(f"FATAL: klt sta status is {doc.get('status')!r}, not 'ok'")
    got = [c.get("corner") for c in doc.get("corners") or []]
    if got != want:
        sys.exit(f"FATAL: the response does not answer the request's {len(want)} corners.\n"
                 f"  requested: {want}\n  answered:  {got}")
    check_blackboxes_resolved(doc, cells)

    REC.mkdir(parents=True, exist_ok=True)
    STA_REC.write_text(json.dumps(doc, indent=2) + "\n")
    STA_NOTE.write_text(sta_note(doc, cells))

    bad = 0
    for c in doc["corners"]:
        setup, hold = c.get("worst_slack_ns"), c.get("worst_hold_slack_ns")
        graded = in_window(c["corner"])
        ok = c.get("timing_status") == "constrained" and setup is not None \
            and hold is not None and setup >= 0 and hold >= 0
        bad += graded and not ok
        verdict = ("PASS" if ok else "FAIL") if graded else "not graded"
        print(f"  {c['corner']:<14} {corner_volts(c['corner']):.2f}V "
              f"{'in ' if graded else 'out'} setup={setup:<10} hold={hold:<9} {verdict}")
    print(f"sta: {len(doc['corners'])} corners -> {rel(STA_REC)}, {rel(STA_NOTE)}")
    if bad:
        sys.exit(f"FATAL: {bad} corner(s) inside {VMIN_V}-{VMAX_V} V failed; the record "
                 f"is written -- report it, do not relax the request")


COMMANDS = {"synth": synth, "check": check, "sta": sta,
            "layout": layout, "layout-check": layout_check}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]]()
