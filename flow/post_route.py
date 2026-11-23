#!/usr/bin/env python3
"""Post-route SDF flow for the controller (T1 item 7, issue #171).

  post_route.py sdf     `klt sta` in def mode on the committed DEF + SPEF with
                        `sdf: true` (flow/sta-sdf-hyperram.json, corner
                        tt_025C_1v80 -- the corner the layout was routed at),
                        copy the SDF to layout/records/ and commit the
                        response beside it as layout/records/sta-sdf.response.json.
                        Never re-routes: the geometry handed in is the one
                        analysed, so no fresh place-and-route is implied or
                        allowed here.
  post_route.py verify  `klt functional-verification` with `options.sdf` on the
                        routed netlist (flow/functional-verification-ctrl-sdf.json:
                        PDK timing models, no FUNCTIONAL define, no UNIT_DELAY
                        override -- klt rejects options.sdf with a global
                        FUNCTIONAL), the same unmodified test_all bench, and
                        write the report UNMODIFIED to
                        sim/hyperram/records/functional-verification-ctrl-sdf.report.json
                        plus the input-digest companion
                        sim/hyperram/records/functional-verification-ctrl-sdf.checksums.json.
                        Recorded results are append-only: the run a re-run
                        replaces is kept verbatim under
                        sim/hyperram/records/functional-verification-ctrl-sdf.runs/
                        (issue #205), so the canonical path carries the latest
                        run without losing the one it supersedes.
  post_route.py check   the no-simulator freshness gate scripts/check_sdf_evidence.py
                        runs in CI; same assertions, run by hand from here.

klt runs through scripts/klt.sh (the pin), like every runner in flow/. The sta
half needs the PDK (`PDK_ROOT`, default ~/.ciel per scripts/setup-env.sh) and
an openroad; the verify half needs Icarus >= 13 (`-ginterconnect`) and cocotb
-- put .venv/bin first (the Makefiles do; this file does it itself when the
venv exists).

The two exits are deliberately distinct: `sdf` fails if the STA response is
not a clean annotated answer (status, sdf envelope, hash match of the copied
file); `verify` writes its evidence even when the SUITE fails -- a failing
annotated run is the finding, not something to tune away -- and exits 1 only
after the report and checksums are on disk, naming the failing count. Which
tests fail and why is the report's own content; see docs/ROADMAP.md item 7.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from klt_run import REPO, klt  # noqa: E402

STA_REQ = REPO / "flow/sta-sdf-hyperram.json"
FV_REQ = REPO / "flow/functional-verification-ctrl-sdf.json"
LREC = REPO / "layout/records"
STA_REC = LREC / "sta-sdf.response.json"
SDF = LREC / "hyperram_ctrl.tt_025C_1v80.sdf"
ROUTED = LREC / "hyperram_ctrl.routed.v"
SPEF = LREC / "hyperram_ctrl.spef"
SCRATCH_SDF = REPO / "flow/.klt/sta/hyperram_ctrl.tt_025C_1v80.sdf"
REC = REPO / "sim/hyperram/records"
REPORT = REC / "functional-verification-ctrl-sdf.report.json"
CHECKSUMS = REC / "functional-verification-ctrl-sdf.checksums.json"
RUNS = REC / "functional-verification-ctrl-sdf.runs"
# Icarus gained -ginterconnect (mandatory for a post-route SDF's INTERCONNECT
# population) in 13.0; scripts/setup-env.sh pins only major >= 12 for the other
# targets, so this gate is local to the SDF leg rather than a silent floor rise.
ICARUS_MIN_MAJOR = 13


def rel(path):
    return str(Path(path).relative_to(REPO))


def sha256(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pdk_env():
    """The sta half resolves liberty through the PDK; default the root the way
    scripts/setup-env.sh and the Makefiles do."""
    env = dict(os.environ)
    env.setdefault("PDK", "sky130A")
    if "PDK_ROOT" not in env and (Path.home() / ".ciel/sky130A").exists():
        env["PDK_ROOT"] = str(Path.home() / ".ciel")
    return env


def venv_env():
    """Prefer the repo venv's klt/cocotb when present (scripts/setup-env.sh's
    layout; the top-level Makefile does the same export)."""
    venv = REPO / ".venv/bin"
    if venv.is_dir():
        env = dict(os.environ)
        env["PATH"] = f"{venv}:{env.get('PATH', '')}"
        return env
    return dict(os.environ)


def require_icarus():
    """Fail clearly on an Icarus older than the SDF leg needs (issue #171:
    setup-env's major >= 12 floor stays; only this target demands 13)."""
    try:
        out = subprocess.run(["iverilog", "-V"], capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit("FATAL: no iverilog on $PATH; the SDF-annotated run needs Icarus "
                 f">= {ICARUS_MIN_MAJOR}.0 (-ginterconnect)")
    m = re.search(r"version\s+(\d+)", out.stdout + out.stderr)
    if not m:
        sys.exit("FATAL: cannot read a version out of `iverilog -V`; the "
                 f"SDF-annotated run needs Icarus >= {ICARUS_MIN_MAJOR}.0")
    if int(m.group(1)) < ICARUS_MIN_MAJOR:
        sys.exit(f"FATAL: Icarus {m.group(1)} is too old for the SDF-annotated run: "
                 f"-ginterconnect (a post-route SDF is all INTERCONNECT entries) "
                 f"exists only from 13.0; found {out.stdout.splitlines()[0] if out.stdout else m.group(1)}. "
                 "scripts/setup-env.sh's major >= 12 floor is unchanged -- this "
                 "requirement is the SDF target's alone")


def sdf():
    if not (LREC / "hyperram_ctrl.def").exists() or not SPEF.exists() or not ROUTED.exists():
        sys.exit(f"FATAL: {rel(LREC)} is missing its DEF/SPEF/routed netlist; "
                 "run `make layout` first (a re-route is what this flow avoids, "
                 "so the records must already be there)")
    proc = klt("sta", str(STA_REQ), "--format", "json", env=pdk_env())
    try:
        doc = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"FATAL: klt sta gave no JSON (rc={proc.returncode}): {proc.stderr.strip()[:500]}")
    if proc.returncode != 0 or "error" in doc:
        sys.exit(f"FATAL: klt sta failed: {json.dumps(doc.get('error', doc))[:800]}")
    if doc.get("status") != "ok" or doc.get("geometry_source") != "routed":
        sys.exit(f"FATAL: response is not a routed-geometry STA answer: status "
                 f"{doc.get('status')!r}, geometry_source {doc.get('geometry_source')!r}")
    envelope = doc.get("sdf")
    if not (isinstance(envelope, dict) and envelope.get("content_hash", "").startswith("sha256:")):
        sys.exit("FATAL: the response carries no per-corner sdf {path, scope, content_hash} "
                 "envelope; the request's sdf: true did not take effect")
    if not SCRATCH_SDF.exists():
        sys.exit(f"FATAL: the response names an SDF but {rel(SCRATCH_SDF)} is gone")
    shutil.copyfile(SCRATCH_SDF, SDF)
    if sha256(SDF) != envelope["content_hash"]:
        sys.exit(f"FATAL: the committed {rel(SDF)} does not hash to the response's "
                 f"content_hash {envelope['content_hash']}")
    # Point the envelope at the committed copy (the scratch dir is untracked);
    # the content_hash -- the bytes -- is untouched, and CI re-checks it. The
    # engine_log scratch paths are left exactly as klt wrote them: unlike
    # place-and-route publish() (flow/hyperram.py), which drops them from its
    # engine_logs list, a klt sta response carries a single engine_log dict,
    # and flow/hyperram.py reads engine_log.script_path back off it.
    doc["sdf"] = {**envelope, "path": rel(SDF), "scope": "repo"}
    STA_REC.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"sdf ok: {rel(SDF)} ({Path(SDF).stat().st_size} bytes, "
          f"{envelope['content_hash'][:19]}...) -> {rel(STA_REC)}")
    print(f"  corner {json.loads(STA_REQ.read_text())['pdk']['corner']}: "
          f"setup slack {doc.get('worst_slack_ns')} ns, hold {doc.get('worst_hold_slack_ns')} ns")


def _keep_superseded_run(new_report: str):
    """Copy the run a fresh verify replaces, verbatim, under
    functional-verification-ctrl-sdf.runs/<that report's sha256 prefix>/.

    The canonical report/checksums pair carries the latest run; the pair it
    replaces is the recorded result of the bench state that produced it, so
    it is appended under a name bound to its own report digest instead of
    being overwritten. The directory is history, not verdict evidence: the
    gates read only the canonical pair, and an archived checksums file keeps
    naming the canonical report path (its bytes are the run's own)."""
    if not (REPORT.exists() and CHECKSUMS.exists()):
        return
    if REPORT.read_text() == new_report:
        return
    old = json.loads(CHECKSUMS.read_text())
    digest = ((old.get("report") or {}).get("sha256") or sha256(REPORT)).removeprefix("sha256:")
    keep = RUNS / digest[:12]
    keep.mkdir(parents=True, exist_ok=True)
    for path in (REPORT, CHECKSUMS):
        shutil.copyfile(path, keep / path.name)
    print(f"  superseded run kept verbatim -> {rel(keep)}/")


def verify():
    require_icarus()
    for p in (STA_REC, SDF, ROUTED):
        if not p.exists():
            sys.exit(f"FATAL: {rel(p)} missing; run `post_route.py sdf` (or "
                     "`make post-route-sdf`) first")
    proc = klt("functional-verification", str(FV_REQ), "--format", "json", env=venv_env())
    try:
        doc = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"FATAL: klt functional-verification gave no JSON (rc={proc.returncode}): "
                 f"{proc.stderr.strip()[:500]}")
    # rc 3 is a completed run whose suite failed -- the finding this flow
    # exists to record; only a tool-level error (non-zero "error" doc, or any
    # other rc) never wrote evidence worth committing.
    if "error" in doc or proc.returncode not in (0, 3):
        sys.exit(f"FATAL: klt functional-verification failed: "
                 f"{json.dumps(doc.get('error', doc))[:800]}")
    sdf_env = (doc.get("environment") or {}).get("sdf")
    if not (isinstance(sdf_env, dict) and sdf_env.get("annotated") is True):
        sys.exit("FATAL: the report's environment.sdf.annotated is not literal true; "
                 "the run was not an SDF-annotated one and is not item-7 evidence")
    REC.mkdir(parents=True, exist_ok=True)
    report_bytes = json.dumps(doc, indent=2) + "\n"
    _keep_superseded_run(report_bytes)
    REPORT.write_text(report_bytes)
    response = json.loads(STA_REC.read_text())
    CHECKSUMS.write_text(json.dumps({
        "note": "committer-written companion: klt 0.9.2's functional-verification "
                "report writer emits the annotation status, corner and SDF path but "
                "no design-input digests, so the run's exact inputs are bound here "
                "instead. scripts/check_sdf_evidence.py recomputes every digest from "
                "checkout-relative paths and cross-checks the SDF against the "
                "producing STA response; no simulator is needed.",
        "request": rel(FV_REQ),
        "sta": {
            "request": rel(STA_REQ),
            "response": rel(STA_REC),
            "sdf_content_hash": response["sdf"]["content_hash"],
        },
        "inputs": [
            {"path": rel(ROUTED), "sha256": sha256(ROUTED)},
            {"path": rel(SDF), "sha256": sha256(SDF)},
        ],
        "report": {"path": rel(REPORT), "sha256": sha256(REPORT)},
    }, indent=2) + "\n")
    partial = sdf_env.get("partial")
    dropped = sorted((sdf_env.get("dropped") or {}).keys())
    print(f"verify: status {doc['status']}, {doc['passed_count']}/{doc['test_count']} "
          f"passed; sdf annotated (corner {sdf_env.get('corner')}, entries "
          f"{sdf_env.get('entries')}, partial {partial}, dropped: {', '.join(dropped) or 'none'})")
    print(f"  -> {rel(REPORT)} (unmodified) + {rel(CHECKSUMS)}")
    if doc["status"] != "pass":
        failing = [t["name"] for t in doc["tests"] if t["status"] != "passed"]
        print(f"  failing ({len(failing)}): {', '.join(failing[:8])}"
              + (" ..." if len(failing) > 8 else ""))
        sys.exit(f"FATAL: the SDF-annotated suite failed {doc['failed_count']} of "
                 f"{doc['test_count']} tests; the evidence is written -- report it, "
                 "do not relax the bench, the model or the spec")


def check():
    proc = subprocess.run([sys.executable, "-I", str(REPO / "scripts/check_sdf_evidence.py")],
                          capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    sys.exit(proc.returncode)


COMMANDS = {"sdf": sdf, "verify": verify, "check": check}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]]()
