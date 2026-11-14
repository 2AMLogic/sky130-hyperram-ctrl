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


COMMANDS = {"synth": synth, "check": check, "layout": layout, "layout-check": layout_check}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]]()
