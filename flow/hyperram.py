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
  hyperram.py sta-note
                      regenerate only sim/hyperram/records/STA.md from the
                      committed sta.json + synth-stat.json blackbox list via
                      the existing sta_note() (no klt, no OpenROAD, no PDK);
                      refuses missing inputs or a non-ok record before
                      touching the note
  hyperram.py sta-check [--self-test]
                      freshness gate for CI: the committed STA.md must equal
                      a fresh render of the committed record byte-for-byte,
                      exit 3 STALE otherwise; --self-test exercises the drift,
                      refusal and repair cases over temp fixture trees
                      (the suite lives in flow/hyperram_selftest.py)
  hyperram.py layout  run `klt place-and-route` on layout/place-and-route.json
                      (the netlist above, 50 MHz, PDN + tapcells) and commit
                      the routed outputs to layout/records/ plus the T1 item 2
                      envelope evidence/item2.json
  hyperram.py layout-check
                      verify the committed response against the request
                      (netlist and liberty hashes) and the item-2 envelope
                      against the committed GDS; no OpenROAD run
  hyperram.py sta-postroute
                      run `klt sta` in def+spef mode on the routed DEF/SPEF at
                      every shipped liberty corner with BOTH clocks declared
                      (`clk` primary, `hb_rwds_i` the RWDS strobe, 20 ns each,
                      propagated), twice: clocks left related, then in
                      asynchronous clock_groups; write the responses to
                      sim/hyperram/records/sta-postroute{,-async}.json and a
                      generated STA-postroute.md beside them (issue #172).
                      In-window negative slack is reported and linked to a
                      design-iteration issue, not gated: the clock
                      relationship is #2's to settle (C4), so both readings
                      are provisional by construction
  hyperram.py sta-postroute-note
                      regenerate only STA-postroute.md from the committed
                      responses (no OpenROAD run), after verifying the existing
                      input provenance marker and response bindings; refuses
                      missing or stale provenance so only `sta-postroute` can
                      record new request/DEF/SPEF hashes
  hyperram.py sta-postroute-check [--self-test]
                      freshness gate for CI: request/DEF/SPEF hashes vs the
                      committed records (no OpenROAD, no PDK); --self-test
                      checks that SPEF/request drift survives `sta-postroute-note`

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
# Post-route multi-corner STA (issue #172): def+spef mode over the routed
# geometry, both clocks declared (the RWDS strobe is the second one), two
# readings -- clocks left related (the committed sta-postroute.json) and in
# asynchronous clock_groups (sta-postroute-async.json) -- because the
# clk/hb_rwds_i relationship is spec ratification's to settle (#2, choice C4),
# not this runner's.
STAPR_REQ = REPO / "flow/sta-hyperram-postroute.json"
STAPR_AREQ = REPO / "flow/sta-hyperram-postroute-async.json"
STAPR_REC = REC / "sta-postroute.json"
STAPR_AREC = REC / "sta-postroute-async.json"
STAPR_NOTE = REC / "STA-postroute.md"
RDEF = LREC / "hyperram_ctrl.def"
RSPEF = LREC / "hyperram_ctrl.spef"
# The strobe-domain capture logic is the u_cap/ hierarchy (hr_rd_capture and
# its buffer); worst-path rows whose endpoint register sits under it are
# attributed to the hb_rwds_i clock, every other row to clk. Stated in the
# note whenever the per-clock split is printed.
STROBE_HIER = "u_cap/"

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


def rel(path, root=None):
    return str(Path(path).relative_to(REPO if root is None else root))


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
    req = json.loads(STA_REQ.read_text(encoding="utf-8"))
    prov = doc["provenance"]

    def rows(entries):
        return [f"| `{c['corner']}` | {corner_volts(c['corner']):.2f} | {c['worst_slack_ns']} "
                f"| {c['worst_hold_slack_ns']} | {c.get('setup_violation_count')} "
                f"| {c.get('total_negative_slack_ns')} | {c.get('hold_violation_count')} "
                f"| {c.get('total_negative_hold_slack_ns')} | {c['fmax_mhz']} "
                f"| {c['timing_status']} |"
                for c in entries]

    head = ["| corner | supply (V) | worst setup (ns) | worst hold (ns) | setup viol. endpoints"
            " | setup TNS (ns) | hold viol. endpoints | hold TNS (ns) | fmax (MHz) | status |",
            "|---|---|---|---|---|---|---|---|---|---|"]
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
        f" -- on both edges, and this request constrains exactly one clock port, so"
        f" OpenSTA sees no clock on them. **The read-capture path is unconstrained and"
        f" unreported in this record.**",
        f"- **{endpoints[0] if len(endpoints) == 1 else endpoints} unconstrained"
        f" endpoints** -- the design's output ports and `cfg_rdata`, since no output"
        f" delay or load is set (above).",
        "",
        "Neither is masked. `constraints.false_path_from` would have hidden the capture"
        f" path instead of recording the gap, and the pinned klt's"
        f" ({prov['klt_version']}) request schema can declare a second clock port and"
        " asynchronous clock groups (`constraints.clocks`/`constraints.clock_groups`,"
        " klayout-tools#4241) but still cannot express a generated clock on `rwds_d`"
        " -- an internal net, not a port -- so the capture domain stays unconstrained"
        " here. Constraining that domain is a modelling choice that belongs to the"
        " spec (#2); its real delays belong to the ngspice delay-chain campaign (#99)"
        " and its pad-facing half to #98.",
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

    Two things the design forces:

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
    # Canonical bytes, the form sta-note writes and sta-check compares: UTF-8,
    # LF, whatever the host locale or newline convention, and encoded before
    # the file is opened so an encode failure cannot truncate a record.
    STA_REC.write_bytes((json.dumps(doc, indent=2) + "\n").encode("utf-8"))
    STA_NOTE.write_bytes(sta_note(doc, cells).encode("utf-8"))

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


def sta_note_paths(root=None):
    root = Path(REPO if root is None else root)
    return (
        root / "sim/hyperram/records/sta.json",
        root / "sim/hyperram/records/STA.md",
        root / "sim/hyperram/records/synth-stat.json",
    )


def sta_note_render(root=None):
    """Read the committed pre-layout STA inputs and render the note text.

    The one read-and-render path shared by `sta-note` and `sta-check`, so both
    verbs and a live `sta` produce the same bytes: the committed sta.json plus
    the committed synth-stat.json blackbox list through the existing
    sta_note(). No klt, no OpenROAD, no PDK. Refuses, before any write, when
    either input is missing or the record's status is not ok -- a note minted
    from a broken record would be prose beside evidence that does not exist.
    """
    root = Path(REPO if root is None else root)
    rec_p, _, stat_p = sta_note_paths(root)
    if not rec_p.exists():
        sys.exit(f"FATAL: {rel(rec_p, root)} missing; run `make hyperram-sta`")
    if not stat_p.exists():
        sys.exit(f"FATAL: {rel(stat_p, root)} missing; run `make hyperram-synth`")
    doc = json.loads(rec_p.read_text(encoding="utf-8"))
    if doc.get("status") != "ok":
        sys.exit(f"FATAL: {rel(rec_p, root)} status is {doc.get('status')!r}, not 'ok';"
                 " run `make hyperram-sta`")
    cells = json.loads(stat_p.read_text(encoding="utf-8"))["blackbox_modules"]
    return sta_note(doc, cells)


def sta_note_bytes(root=None):
    """The canonical on-disk form of the note: UTF-8, LF endings, regardless
    of the host locale or platform newline convention. Both `sta-note` (write)
    and `sta-check` (compare) use exactly these bytes."""
    return sta_note_render(root).encode("utf-8")


def sta_note_cmd(root=None):
    """`sta-note`: regenerate only STA.md from the committed record.

    The pre-layout twin of sta-postroute-note: re-renders the prose from
    sim/hyperram/records/sta.json and the committed synth-stat.json blackbox
    list without a `klt sta` run, so the note can be re-minted where OpenROAD
    and PDK_ROOT are absent (CI, review worktrees). Whether sta.json itself
    still matches the netlist it was minted from is not this verb's question.
    """
    root = Path(REPO if root is None else root)
    _, note_p, _ = sta_note_paths(root)
    # Render (and encode) fully before the output is opened, and write bytes:
    # a render/encode failure must not truncate STA.md, and no host newline
    # translation may change what sta-check compares against.
    note_p.write_bytes(sta_note_bytes(root))
    print(f"sta-note: rewrote {rel(note_p, root)} from the committed record")


def sta_check(root=None):
    """`sta-check`: freshness gate for CI, the pre-layout twin of
    sta-postroute-check.

    Binds the committed note to the record beside it, byte-for-byte: STA.md
    must equal a fresh sta_note() render of the committed sta.json with the
    committed blackbox list. This checks only the note<->record binding --
    whether sta.json matches the netlist it came from is not answered here
    (that needs OpenROAD + PDK and stays local_only with `make hyperram-sta`).
    """
    root = Path(REPO if root is None else root)
    _, note_p, _ = sta_note_paths(root)
    want = sta_note_bytes(root)
    have = note_p.read_bytes() if note_p.exists() else None
    if have != want:
        how = "missing" if have is None else "differs from a fresh render of the committed record"
        print(f"STALE: {rel(note_p, root)} {how};"
              " run `python3 -I flow/hyperram.py sta-note`")
        sys.exit(3)
    print("pre-layout STA note is fresh")


# klayout-tools issues the post-route record links. Filled from the tracker;
# the note renders them, and a gap here is visible in the committed prose.
KLT_ISSUE_PER_CLOCK_IO_DELAY = 7399   # DQ-vs-RWDS input delay: per-clock I/O delays
KLT_ISSUE_SPEF_ESCAPE = 7401          # read_spef discards escaped bracket net names
KLT_ISSUE_SINK_COUNT = 7417          # clock_sinks reports its sample length
KLT_ISSUE_ENDPOINT_LIST = 7418       # sta reports worst-per-group only, no violating-endpoint list
KLT_ISSUE_SPEF_DANGLING = 7367        # name-correlation counts dangling tie cells / power nets
# Design findings from the first mint of this record (issue #172 step 7): one
# bounded design-iteration issue per distinct negative in-window worst-path
# row, keyed (side, startpoint, endpoint). sta_postroute() warns when the live
# negative set drifts from these keys, so a new finding cannot ship silently.


PR_FINDING_ISSUES = {
    ("setup", "u_cap/_828_/Q", "_519_/D"): 184,
    ("setup", "u_cap/_844_/Q", "_519_/D"): 184,
    ("hold", "hb_rwds_i", "u_fsm/_2214_/D"): 185,
}


def klt_issue(n):
    return f"klayout-tools#{n}" if n else "klayout-tools (issue not yet filed)"


def pr_issue(key):
    n = PR_FINDING_ISSUES.get(key)
    return f"#{n}" if n else "no design-iteration issue filed yet"


def sta_postroute_run(req_path):
    """Run one `klt sta` postroute request and validate its response shape.

    Structural only: status, corner coverage, the two clocks at 20 ns, the
    propagated-clock mode, the routed geometry identity, and -- the acceptance
    criterion the whole request exists for -- that no register is unclocked at
    any corner, so the `u_cap/` capture flops really are timed off the strobe.
    Nothing here grades slack (see sta_postroute for why not).
    """
    req = json.loads(Path(req_path).read_text())
    want = list(req["pdk"]["corners"])
    doc = klt_json("sta", str(req_path), env=pdk_env())
    if doc.get("status") != "ok":
        sys.exit(f"FATAL: klt sta {rel(req_path)} status is {doc.get('status')!r}, not 'ok'")
    if doc.get("geometry_source") != "routed":
        sys.exit(f"FATAL: {rel(req_path)}: geometry_source is {doc.get('geometry_source')!r},"
                 " expected 'routed' (def mode on the committed DEF)")
    if doc.get("clock_mode") != "propagated":
        sys.exit(f"FATAL: {rel(req_path)}: clock_mode is {doc.get('clock_mode')!r},"
                 " expected 'propagated'")
    got = [c.get("corner") for c in doc.get("corners") or []]
    if got != want:
        sys.exit(f"FATAL: {rel(req_path)}: the response does not answer the request's "
                 f"{len(want)} corners.\n  requested: {want}\n  answered:  {got}")
    ct = doc.get("clock_targets") or {}
    clocks = ct.get("clocks") or []
    if ([c.get("port") for c in clocks] != ["clk", "hb_rwds_i"]
            or any(c.get("period_ns") != 20.0 for c in clocks)):
        sys.exit(f"FATAL: {rel(req_path)}: clock_targets.clocks is {json.dumps(clocks)},"
                 " expected clk (primary) and hb_rwds_i, both at 20.0 ns")
    want_groups = req.get("constraints", {}).get("clock_groups") or []
    if (ct.get("clock_groups") or []) != want_groups:
        sys.exit(f"FATAL: {rel(req_path)}: clock_targets.clock_groups is"
                 f" {json.dumps(ct.get('clock_groups'))}, expected {json.dumps(want_groups)}")
    for key, path in (("def_path", RDEF), ("spef_path", RSPEF)):
        node = doc.get(key) or {}
        if node.get("scope") != "repo" or node.get("path") != rel(path):
            sys.exit(f"FATAL: {rel(req_path)}: {key} is {json.dumps(node)}, expected the"
                     f" repo-scoped {rel(path)}")
    for c in doc["corners"]:
        ur = ((c.get("constraint_completeness") or {}).get("unclocked_registers") or {})
        if ur.get("status") != "ok" or ur.get("count") != 0:
            sys.exit(f"FATAL: {rel(req_path)}: corner {c.get('corner')} reports"
                     f" {ur.get('count')} unclocked registers ({ur.get('sample')}); the"
                     " hb_rwds_i clock declaration must reach every u_cap/ capture flop")
    return doc


def pr_domain(row):
    """Which declared clock a worst_paths_by_group row belongs to, by capture
    register: an endpoint under u_cap/ is captured by the strobe-delayed
    rwds_d clock, every other endpoint by clk."""
    return "hb_rwds_i" if (row.get("endpoint") or "").startswith(STROBE_HIER) else "clk"


def pr_group_rows(corner):
    """(setup, hold) worst_paths_by_group rows of one corner entry."""
    wpg = corner.get("worst_paths_by_group") or {}
    return list(wpg.get("setup") or []), list(wpg.get("hold") or [])


def pr_domain_slack(corner, side):
    """{domain: worst row} for one side, by the pr_domain attribution rule."""
    rows = pr_group_rows(corner)[0 if side == "setup" else 1]
    out = {}
    for row in rows:
        out.setdefault(pr_domain(row), row)
    return out


def pr_findings(doc):
    """Distinct negative in-window worst-path rows, with the corners that
    reported them: [(side, startpoint, endpoint, slack, [(corner, slack), ...])]."""
    agg = {}
    for c in doc["corners"]:
        if not in_window(c["corner"]):
            continue
        for side, rows in zip(("setup", "hold"), pr_group_rows(c)):
            for row in rows:
                if (row.get("slack_ns") is not None and row["slack_ns"] < 0
                        and row.get("startpoint") is not None):
                    key = (side, row["startpoint"], row["endpoint"])
                    if key not in agg:
                        agg[key] = []
                    agg[key].append((c["corner"], row["slack_ns"]))
    return [(k[0], k[1], k[2], min(s for _, s in v), v) for k, v in sorted(agg.items())]


def sta_postroute_note(doc, adoc, req, *, marker):
    """The prose beside the records, in the form of STA.md, generated from the
    two responses and a verified provenance marker (never reading or hashing
    disk inputs itself) so note regeneration cannot mint provenance."""
    parsed = parse_sta_postroute_marker(marker)
    if parsed is None:
        sys.exit("FATAL: sta_postroute_note requires a valid sta-postroute-inputs marker")
    marker_line, (def_sha, spef_sha, _, _) = parsed
    prov = doc["provenance"]
    graded = [c for c in doc["corners"] if in_window(c["corner"])]
    ungraded = [c for c in doc["corners"] if not in_window(c["corner"])]
    sa = doc["corners"][0].get("spef_annotation") or {}
    missing = sa.get("design_nets_missing_sample") or []
    cp = doc["corners"][0].get("clock_propagation") or {}
    cc0 = doc["corners"][0].get("constraint_completeness") or {}
    ep_count = (cc0.get("unconstrained_endpoints") or {}).get("count")
    all_constrained = all(c.get("timing_status") == "constrained"
                          for c in doc["corners"] + adoc["corners"])

    def rows(d, names):
        return [f"| `{c['corner']}` | {corner_volts(c['corner']):.2f} | {c['worst_slack_ns']} "
                f"| {c['worst_hold_slack_ns']} | {c.get('setup_violation_count')} "
                f"| {c.get('total_negative_slack_ns')} | {c.get('hold_violation_count')} "
                f"| {c.get('total_negative_hold_slack_ns')} | {c['fmax_mhz']} "
                f"| {c['timing_status']} |"
                for c in d["corners"] if c["corner"] in names]


    head = ["| corner | supply (V) | worst setup (ns) | worst hold (ns) | setup viol. endpoints"
            " | setup TNS (ns) | hold viol. endpoints | hold TNS (ns) | fmax (MHz) | status |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    lines = [
        "# Post-route multi-corner STA of the routed DEF + SPEF, RWDS strobe clock declared (issue #172)",
        "",
        "`make hyperram-sta-postroute` -> [`sta-postroute.json`](sta-postroute.json) (clocks left"
        " **related**) and [`sta-postroute-async.json`](sta-postroute-async.json) (the same request"
        " with `clk` and `hb_rwds_i` in asynchronous `clock_groups`), the unmodified `klt sta`"
        " responses. Requests: [`flow/" + STAPR_REQ.name + "`](../../../flow/" + STAPR_REQ.name + ")"
        " and [`flow/" + STAPR_AREQ.name + "`](../../../flow/" + STAPR_AREQ.name + ") --"
        f" `def` + `spef` mode on `{rel(RDEF)}` and `{rel(RSPEF)}`, `constraints.propagated_clock:"
        " true`, and `constraints.clocks` declaring `clk` (primary; target-spec row 1) **and**"
        " `hb_rwds_i` at the same {p} ns, so the strobe propagates through the `hr_tap_delay`"
        " chain to the `u_cap/` capture flops; all {n} shipped `sky130_fd_sc_hd` corners in one"
        " round trip per reading.".format(p=req["constraints"]["clocks"][0]["period_ns"],
                                          n=len(doc["corners"])),
        "",
        f"- DEF: `{rel(RDEF)}`, {def_sha}.",
        f"- SPEF: `{rel(RSPEF)}`, {spef_sha}.",
        f"- Engine: {doc['engine']} {doc['engine_version']}; klt {prov['klt_version']};"
        f" PDK {prov['pdk']['version']}.",
        f"- `{doc['hdl_toplevel']}`, status `{doc['status']}`, `geometry_source:"
        f" {doc['geometry_source']}`, `clock_mode: {doc['clock_mode']}`, and"
        f" `timing_status: {doc['corners'][0]['timing_status']}` at every corner of both"
        " readings" + ("" if all_constrained else " (NOT so: see the status column below)")
        + ".",
        "",
        "## What was assumed",
        "",
        "Read out of the responses, not asserted here:",
        "",
        f"- **Propagated clock** (`clock_mode: {json.dumps(doc['clock_mode'])}`) on both declared"
        " clocks: hold/removal includes the clock-tree insertion delay and skew the DEF carries,"
        " and, for the strobe, the `hr_tap_delay` chain it propagates through. The latency"
        f" evidence block reports a worst network latency of {cp.get('max_network_latency_ns')} ns"
        f" and a `clock_sinks` field of {cp.get('clock_sinks')} -- which equals the length of"
        f" its own `clock_sinks_sample` ({', '.join(cp.get('clock_sinks_sample') or [])}), so it"
        " is the sample size, **not** the design's sink count (the routed DEF has hundreds of"
        f" flops), reported as {klt_issue(KLT_ISSUE_SINK_COUNT)}.",
        f"- **Routed geometry, real parasitics to the extent the SPEF annotated** (`def_path` and"
        f" `spef_path` name the committed `{rel(RDEF)}` / `{rel(RSPEF)}`). The SPEF session names"
        f" {sa.get('design_nets_annotated')} of {sa.get('design_nets_total')} design nets"
        f" (`annotation_complete: {json.dumps(sa.get('annotation_complete'))}`) -- the gaps are"
        " named below.",
        "- **Two clocks, relationship unsettled.** `clk` is primary; `hb_rwds_i` is declared as a"
        " second clock at the same period so the capture domain is timed rather than unclocked."
        " Whether the strobe domain is synchronous, asynchronous, or something phase-specific to"
        " the read burst is decision **C4 in #2**, not this record's: the two responses are the"
        " **related** reading (cross-domain paths timed as synchronous -- conservative) and the"
        " **asynchronous** reading (they are not timed at all). **Every number below is"
        " provisional on whichever of those two assumptions it sits beside, pending #2.**",
        "- **No I/O delays.** The draft spec states no setup/hold figure for any port relative to"
        " `clk` (its boundary figures -- tIS/tIH, tCSS, tCKD -- are HyperBus-pin-to-HyperBus-pin"
        " numbers, not core-clock numbers), so none is guessed: every input and output is left"
        " unconstrained and counted below. A scalar default is not an option either: the pinned"
        " klt applies I/O delays relative to the primary clock only, would land one on"
        " `hb_rwds_i` itself, and cannot express a DQ input delay relative to the strobe clock"
        f" at all ({klt_issue(KLT_ISSUE_PER_CLOCK_IO_DELAY)}).",
        "- **No false paths.** `constraints.false_path_from` is deliberately absent; hiding the"
        " capture path is what this record exists not to do.",
        "",
        "## Corners inside the ratified supply window (graded)",
        "",
        "Decision 0004 puts the core supply at 1.8 V +/- 10 %, i.e."
        f" {VMIN_V}-{VMAX_V} V. Unlike `make hyperram-sta`, this target does **not** fail on a"
        f" negative slack at these {len(graded)} corners: under an unsettled clock relationship a"
        " failing cross-domain path is a finding for the ratifier and a filed design-iteration"
        " issue, not a gate to relax the request against. Each negative below is linked. The"
        " `fmax (MHz)` column is OpenSTA's own extrapolation over the `clk` domain, reported as"
        " the response carries it and graded by nothing here.",
        "",
        "**Related-clocks reading** (cross-domain paths timed as synchronous):",
        "",
        *head, *rows(doc, {c["corner"] for c in graded}),
        "",
        "**Asynchronous-clock-groups reading** (cross-domain paths not timed):",
        "",
        *head, *rows(adoc, {c["corner"] for c in graded}),
        "",
        "### Per-clock worst paths (in-window corners)",
        "",
        "The response reports one worst row per path group without naming the group; the split"
        " below attributes each row by capture register -- an endpoint under `" + STROBE_HIER +
        "` is the strobe (`hb_rwds_i`) domain, every other endpoint the `clk` domain -- with the"
        " related reading's rows before the asynchronous reading's, setup before hold within"
        " each:",
        "",
        "| corner | clock | side | worst path | slack (ns) |",
        "|---|---|---|---|---|",
    ]
    for c in graded:
        for d, tag in ((doc, "related"), (adoc, "async")):
            entry = c if d is doc else next(x for x in adoc["corners"]
                                            if x["corner"] == c["corner"])
            for side in ("setup", "hold"):
                for domain, row in sorted(pr_domain_slack(entry, side).items()):
                    lines.append(f"| `{c['corner']}` | `{domain}` | {side} ({tag}) "
                                 f"| `{row['startpoint']}` -> `{row['endpoint']}` "
                                 f"| {row['slack_ns']} |")
    by_path = {}
    for tag, d in (("related", doc), ("async", adoc)):
        for side, sp, ep, slack, per_corner in pr_findings(d):
            by_path.setdefault((side, sp, ep), {}).setdefault(tag, []).extend(per_corner)
    lines += [
        "",
        "## Findings (negative in-window slack)",
        "",
    ]
    if by_path:
        for (side, sp, ep), readings in sorted(by_path.items()):
            worst_corner, worst_slack = min((row for rows in readings.values() for row in rows),
                                            key=lambda r: r[1])
            where = "; ".join(f"{tag} reading at {', '.join(f'`{c}` ({s})' for c, s in sorted(rows))}"
                              for tag, rows in sorted(readings.items()))
            lines.append(f"- **{side} {worst_slack} ns worst** (at `{worst_corner}`), `{sp}` ->"
                         f" `{ep}` -- {where}. Design-iteration issue:"
                         f" {pr_issue((side, sp, ep))}.")
        lines += [
            "",
            "**Width.** The bullets above name only the *worst row per path group*; the response's"
            " per-corner counts (the `viol. endpoints` / `TNS` columns of the tables above) show"
            " the setup side is much wider than the named paths. Under the related reading the"
            " nominal corners carry tens of violating setup endpoints, not two. **Which endpoints"
            " they are is not measured here**: `worst_paths_by_group` is worst-per-group only and"
            " the pinned klt emits no violating-endpoint list"
            f" ({klt_issue(KLT_ISSUE_ENDPOINT_LIST)}). That they are all cross-domain paths into"
            " one capture bus is a **hypothesis** (the count is of the order of a 32-bit"
            " register bus), not a result of this record.",
        ]
    else:
        lines.append("- None: no in-window corner reports a negative setup or hold slack in"
                     " either reading.")
    lines += [
        "",
        "## Corners outside it (reported, not graded)",
        "",
        "The PDK ships liberty at supplies decision 0004's window excludes. These"
        f" {len(ungraded)} corners are recorded and printed, and the target does not fail on"
        f" them, exactly as `make hyperram-sta` reports them.",
        "",
        "**Related-clocks reading:**",
        "",
        *head, *rows(doc, {c["corner"] for c in ungraded}),
        "",
        "**Asynchronous-clock-groups reading:**",
        "",
        *head, *rows(adoc, {c["corner"] for c in ungraded}),
        "",
        "## What was not timed",
        "",
        f"`constraint_completeness` is `{cc0.get('status')}` and the target does not gate on it."
        f" **Unclocked registers: 0 at every corner of both readings** -- declaring `hb_rwds_i`"
        " clocks the 143 registers the pre-layout record left unclocked (every flop under"
        f" `{STROBE_HIER}`, on `rwds_d`). {ep_count} endpoints remain unconstrained, all"
        " boundary-condition gaps, in three classes:",
        "",
        "- **Outputs without an output delay** -- `wb_ack`, `wb_stall`, `wb_dat_r[31:0]`,"
        " `cfg_rdata[15:0]`, `hb_ck`, `hb_cs_n`, `hb_reset_n`, `hb_dq_o[7:0]`, `hb_dq_oe`,"
        " `hb_rwds_o`, `hb_rwds_oe`: the spec states no `clk`-referenced output budget (above).",
        "- **The DQ capture inputs** -- `hb_dq_i[7:0]` and the `u_cap/` data pins they feed: the"
        " one constraint that matters for read capture is the DQ-to-RWDS relationship, which the"
        " pinned klt cannot express (I/O delays are primary-clock-only,"
        f" {klt_issue(KLT_ISSUE_PER_CLOCK_IO_DELAY)}). **The DQ-versus-RWDS capture check itself"
        " is therefore not in this record**; no local OpenSTA script or checker stands in for"
        " it. Its SPICE halves are the delay-chain campaign (#99) and the pad timing (#98, the"
        " I/O ring sibling).",
        "- **Inputs without an input delay** -- `rst_n` and the `wb_*`/`cfg_*` ports: same absence"
        " of a stated figure (the Wishbone rows are functional-only in the draft spec).",
        "",
        "### SPEF annotation gaps",
        "",
        f"The SPEF names {sa.get('design_nets_annotated')} of {sa.get('design_nets_total')}"
        f" design nets; `annotation_complete` is `{json.dumps(sa.get('annotation_complete'))}`."
        f" The response's `design_nets_missing_sample` names all"
        f" {len(missing)} uncorrelated nets: {', '.join(f'`{n}`' for n in missing)}."
        " Inspected against the committed DEF and routed netlist, the class is: `VDD` (a power"
        " net, which a signal SPEF does not extract) and"
        f" {len(missing) - (1 if 'VDD' in missing else 0)} nets that are each the output of a"
        " `sky130_fd_sc_hd__conb_1` constant tie cell driving **no other pin** (e.g."
        " `u_fsm/_0955_` is `u_fsm/_2216_`'s `HI` and nothing else) -- unrouted, unextracted,"
        " on no timed path. That they still force `annotation_complete: false` is"
        f" {klt_issue(KLT_ISSUE_SPEF_DANGLING)}. Separately, `read_spef` discarded"
        f" {sa.get('reader_warning_count')} records with STA-1650/1648 warnings: every"
        " backslash-escaped bus-bracket net name (`clknet_*dly[N]`, `u_cap/mem[N][M]`, ...) is"
        " rejected by the reader while klt's own correlation un-escapes it, so those nets'"
        " parasitics -- including the CK delay-chain clock nets -- are not in the timing:"
        f" {klt_issue(KLT_ISSUE_SPEF_ESCAPE)}. The slack numbers above are real-parasitics"
        " only to that extent; DEF/SPEF hashes in this note's header pin the inputs.",
        "",
        "## What this does not prove",
        "",
        "This is the **post-route, all-core, strobe-clocked** timing half of what T1 item 5 asks"
        " a ratified spec to cite -- prepared so item 5 is one manifest edit away once #2"
        " closes, and cited by **no** manifest item in this PR: which corners bind is the"
        " ratifier's (C4), and the tiers doc makes a verdict against a draft spec provisional."
        " **No spec row is called met here.** Not proven, each for the stated reason: read"
        " capture at the pins and its margin (rows 11-12 -- the DQ/RWDS relationship is not"
        " expressible here, above), the write path (row 14 -- needs the pads), timing at the"
        " pins (row 19 -- pads and the core-to-pad seam are the I/O ring sibling's, compared by"
        " name in the repo README). The manifest, `spec/` and decision 0004 are untouched by"
        " this target.",
        "",
        "Also not here: a settled strobe-domain modelling choice (#2, C4); the SDF-annotated"
        " bench run (#171); max-transition/max-capacitance repair (#173, open -- the DEF/SPEF"
        " may regenerate under it, and the freshness gate will catch that); any claim about"
        " 100 MHz.",
        "",
        marker_line,
    ]
    return "\n".join(lines) + "\n"


STAPR_MARKER_RE = re.compile(
    r"^<!-- sta-postroute-inputs"
    r" def=(sha256:[0-9a-f]{64})"
    r" spef=(sha256:[0-9a-f]{64})"
    r" request=(sha256:[0-9a-f]{64})"
    r" request-async=(sha256:[0-9a-f]{64}) -->$",
    re.M,
)


def sta_postroute_paths(root=None):
    root = Path(REPO if root is None else root)
    return (
        root / "sim/hyperram/records/sta-postroute.json",
        root / "sim/hyperram/records/sta-postroute-async.json",
        root / "sim/hyperram/records/STA-postroute.md",
        root / "flow/sta-hyperram-postroute.json",
        root / "flow/sta-hyperram-postroute-async.json",
        root / "layout/records/hyperram_ctrl.def",
        root / "layout/records/hyperram_ctrl.spef",
    )


def format_sta_postroute_marker(def_sha, spef_sha, req_sha, areq_sha):
    """Machine-readable input binding appended to the note by `sta_postroute`
    (the only operation allowed to mint new input hashes). Each response binds
    the DEF itself via provenance.input.content_hash; the marker binds the SPEF
    and the two request documents."""
    return (f"<!-- sta-postroute-inputs def={def_sha} spef={spef_sha}"
            f" request={req_sha} request-async={areq_sha} -->")


def parse_sta_postroute_marker(note_text):
    """Return (marker_line, (def_sha, spef_sha, req_sha, areq_sha)), or None if
    the note does not carry exactly one well-formed provenance marker."""
    matches = list(STAPR_MARKER_RE.finditer(note_text))
    if len(matches) != 1:
        return None
    m = matches[0]
    return m.group(0), m.groups()


def sta_postroute():
    """`klt sta` on the routed DEF + SPEF, both clocks declared, twice.

    Mirrors `sta`'s order-of-operations discipline: validate the response
    shape before anything is written, write the records and the note
    unconditionally, then report. The gate differs from `sta` on purpose:
    in-window negative slack is *not* a target failure here, because under an
    unsettled clock relationship (step 2 of issue #172) a failing cross-domain
    path is a finding for the ratifier -- filed as its own design-iteration
    issue and linked in the note -- and a hard gate would only push toward
    relaxing the period, the window or the corner list, which the issue
    forbids. A *new* negative (one not in PR_FINDING_ISSUES) is warned about
    loudly so it cannot ship silently.
    """
    for p in (RDEF, RSPEF, STAPR_REQ, STAPR_AREQ):
        if not p.exists():
            sys.exit(f"FATAL: {rel(p)} missing; run `make layout`")
    for req_file in (STAPR_REQ, STAPR_AREQ):
        req_chk = json.loads(req_file.read_text())
        for req_key, target in (("def", RDEF), ("spef", RSPEF)):
            raw = req_chk.get(req_key)
            resolved = (req_file.parent / raw).resolve() if isinstance(raw, str) and raw else None
            if resolved != target.resolve():
                sys.exit(f"FATAL: {rel(req_file)} {req_key}={raw!r} does not resolve to {rel(target)}")
    input_hashes = (sha256(RDEF), sha256(RSPEF), sha256(STAPR_REQ), sha256(STAPR_AREQ))
    req_doc = json.loads(STAPR_REQ.read_text())
    doc = sta_postroute_run(STAPR_REQ)
    adoc = sta_postroute_run(STAPR_AREQ)
    if (sha256(RDEF), sha256(RSPEF), sha256(STAPR_REQ), sha256(STAPR_AREQ)) != input_hashes:
        sys.exit("FATAL: request/DEF/SPEF changed while `klt sta` was running;"
                 " refusing to record mixed provenance")
    for req_file, d in ((STAPR_REQ, doc), (STAPR_AREQ, adoc)):
        got_def = (d.get("provenance") or {}).get("input", {}).get("content_hash")
        if got_def != input_hashes[0]:
            sys.exit(f"FATAL: {rel(req_file)} response provenance DEF hash {got_def!r}"
                     f" != {input_hashes[0]}")
    marker = format_sta_postroute_marker(*input_hashes)

    REC.mkdir(parents=True, exist_ok=True)
    STAPR_REC.write_bytes((json.dumps(doc, indent=2) + "\n").encode("utf-8"))
    STAPR_AREC.write_bytes((json.dumps(adoc, indent=2) + "\n").encode("utf-8"))
    STAPR_NOTE.write_bytes(sta_postroute_note(doc, adoc, req_doc, marker=marker).encode("utf-8"))

    print(f"sta-postroute: {len(doc['corners'])} corners x 2 readings -> "
          f"{rel(STAPR_REC)}, {rel(STAPR_AREC)}, {rel(STAPR_NOTE)}")
    for tag, d in (("related", doc), ("async   ", adoc)):
        for c in d["corners"]:
            setup, hold = c.get("worst_slack_ns"), c.get("worst_hold_slack_ns")
            graded = in_window(c["corner"])
            verdict = ("in " if graded else "out")
            if graded and (setup is None or hold is None
                          or setup < 0 or hold < 0
                          or c.get("timing_status") != "constrained"):
                verdict = "FINDING"
            print(f"  [{tag}] {c['corner']:<14} {corner_volts(c['corner']):.2f}V {verdict:<4} "
                  f"setup={setup:<10} hold={hold:<9} {c['timing_status']}")
    live = {f[:3] for f in pr_findings(doc)} | {f[:3] for f in pr_findings(adoc)}
    known = set(PR_FINDING_ISSUES)
    if live - known:
        print(f"WARNING: new in-window negative path(s) not in PR_FINDING_ISSUES -- file a "
              f"bounded design-iteration issue for each and add it to flow/hyperram.py:\n"
              f"  {sorted(live - known)}", file=sys.stderr)
    if known - live:
        print(f"WARNING: PR_FINDING_ISSUES names path(s) no longer negative in the fresh "
              f"response; prune them: {sorted(known - live)}", file=sys.stderr)


def sta_postroute_verify(root=None):
    """Verify the existing provenance marker in STA-postroute.md and the
    response bindings against `root`, without minting new input hashes.

    Returns (doc, adoc, req, marker_line) when fresh, or exits non-zero (3 on
    missing/stale provenance or drifted echoes, 1 on a missing artifact or a
    non-'ok' response). Shared by `sta-postroute-check` and
    `sta-postroute-note` so note regeneration cannot re-stamp stale responses.
    """
    rec_p, arec_p, note_p, req_p, areq_p, rdef_p, rspef_p = sta_postroute_paths(root)
    for p in (rec_p, arec_p, note_p, req_p, areq_p, rdef_p, rspef_p):
        if not p.exists():
            sys.exit(f"FATAL: {rel(p, root)} missing; run `make hyperram-sta-postroute`")
    note = note_p.read_text()
    parsed = parse_sta_postroute_marker(note)
    if parsed is None:
        print(f"STALE: {rel(note_p, root)} does not carry the input marker for the current"
              " request/DEF/SPEF (marker missing or malformed); run `make hyperram-sta-postroute`")
        sys.exit(3)
    marker_line, got_hashes = parsed
    want_hashes = (sha256(rdef_p), sha256(rspef_p), sha256(req_p), sha256(areq_p))
    if got_hashes != want_hashes:
        drifted = [rel(p, root) for p, g, w in zip((rdef_p, rspef_p, req_p, areq_p),
                                                   got_hashes, want_hashes) if g != w]
        print(f"STALE: {rel(note_p, root)} does not carry the input marker for the current"
              f" request/DEF/SPEF ({', '.join(drifted)} changed); run `make hyperram-sta-postroute`")
        sys.exit(3)
    docs = []
    reqs = []
    for rec, req_file in ((rec_p, req_p), (arec_p, areq_p)):
        doc = json.loads(rec.read_text())
        req = json.loads(req_file.read_text())
        if doc.get("status") != "ok":
            sys.exit(f"FATAL: {rel(rec, root)}: status is {doc.get('status')!r}")
        for req_key, doc_key, target in (("def", "def_path", rdef_p),
                                         ("spef", "spef_path", rspef_p)):
            raw = req.get(req_key)
            resolved = (req_file.parent / raw).resolve() if isinstance(raw, str) and raw else None
            if resolved != target.resolve():
                print(f"STALE: {rel(req_file, root)} {req_key}={raw!r} does not resolve to"
                      f" {rel(target, root)}; run `make hyperram-sta-postroute`")
                sys.exit(3)
            if doc.get(doc_key) != {"path": rel(target, root), "scope": "repo"}:
                print(f"STALE: {rel(rec, root)} {doc_key} is {json.dumps(doc.get(doc_key))},"
                      f" expected repo-scoped {rel(target, root)}; run `make hyperram-sta-postroute`")
                sys.exit(3)
        if doc.get("geometry_source") != "routed" or doc.get("hdl_toplevel") != req.get("hdl_toplevel"):
            print(f"STALE: {rel(rec, root)} geometry_source/hdl_toplevel does not match"
                  f" {rel(req_file, root)}; run `make hyperram-sta-postroute`")
            sys.exit(3)
        if want_hashes[0] != (doc.get("provenance") or {}).get("input", {}).get("content_hash"):
            print(f"STALE: {rel(rec, root)} was minted against a different {rel(rdef_p, root)};"
                  " run `make hyperram-sta-postroute`")
            sys.exit(3)
        if [c.get("corner") for c in doc.get("corners") or []] != list(req["pdk"]["corners"]):
            print(f"STALE: {rel(rec, root)} does not answer {rel(req_file, root)}'s corner list;"
                  " run `make hyperram-sta-postroute`")
            sys.exit(3)
        ct = doc.get("clock_targets") or {}
        if (ct.get("clocks") != req["constraints"]["clocks"]
                or (ct.get("clock_groups") or []) != req["constraints"].get("clock_groups", [])
                or doc.get("clock_mode") != ("propagated" if req["constraints"].get("propagated_clock")
                                             else "ideal")):
            print(f"STALE: {rel(rec, root)}'s clock echoes do not match {rel(req_file, root)};"
                  " run `make hyperram-sta-postroute`")
            sys.exit(3)
        docs.append(doc)
        reqs.append(req)
    return docs[0], docs[1], reqs[0], marker_line


def sta_postroute_note_cmd(root=None):
    """Regenerate only the note from the committed responses (no klt run).

    Verifies existing input provenance first and refuses missing or stale
    provenance; only `sta-postroute` can record new request/DEF/SPEF hashes.
    """
    _, _, note_p, *_ = sta_postroute_paths(root)
    doc, adoc, req, marker = sta_postroute_verify(root)
    note_p.write_bytes(sta_postroute_note(doc, adoc, req, marker=marker).encode("utf-8"))
    print(f"sta-postroute-note: rewrote {rel(note_p, root)} from the committed responses")


def sta_postroute_check(root=None):
    """Freshness gate for CI: no OpenROAD, no PDK, hashes and echoes only.

    Binds the committed responses to their inputs and to the note beside them:
    the DEF against klt's own `provenance.input.content_hash` in each response,
    the DEF/SPEF and both request documents against the marker line minted by
    `sta-postroute`, the path/corner/clock/clock-group echoes in each response
    against its request document, and the note body against a fresh render from
    the committed responses.
    """
    _, _, note_p, *_ = sta_postroute_paths(root)
    doc, adoc, req, marker = sta_postroute_verify(root)
    if note_p.read_text() != sta_postroute_note(doc, adoc, req, marker=marker):
        print(f"STALE: {rel(note_p, root)} differs from a fresh render of the committed"
              " responses; run `python3 -I flow/hyperram.py sta-postroute-note`")
        sys.exit(3)
    print("post-route STA record is fresh")


COMMANDS = {"synth": synth, "check": check, "sta": sta,
            "sta-note": sta_note_cmd, "sta-check": sta_check,
            "sta-postroute": sta_postroute, "sta-postroute-note": sta_postroute_note_cmd,
            "sta-postroute-check": sta_postroute_check,
            "layout": layout, "layout-check": layout_check}

if __name__ == "__main__":
    if sys.argv[1:] in (["sta-postroute-check", "--self-test"], ["sta-check", "--self-test"]):
        # The offline self-tests live in hyperram_selftest.py (issue #229).
        import hyperram_selftest
        hyperram_selftest.SELF_TESTS[sys.argv[1]]()
    elif len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    else:
        COMMANDS[sys.argv[1]]()
