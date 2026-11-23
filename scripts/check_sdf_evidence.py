#!/usr/bin/env python3
"""Offline freshness gate for the SDF-annotated post-layout evidence (item 7).

scripts/check_ci.sh runs this with no simulator, no PDK and no klt: it
recomputes the digests the make target recorded and refuses drift or a broken
cross-bind. What it checks, and why each check exists:

  1. every digest in sim/hyperram/records/functional-verification-ctrl-sdf.checksums.json
     (routed netlist, SDF, raw report) still matches the committed bytes -- the
     klt 0.9.2 report writer emits no design-input digests of its own, so the
     companion is the only thing binding the verdict to its exact inputs;
  2. the SDF digest equals the producing STA response's sdf.content_hash
     (layout/records/sta-sdf.response.json), that response's sdf.path names
     the committed SDF, and its provenance.input.content_hash still hashes
     the DEF at its def_path -- a hand-edited SDF, or a re-route whose SDF
     and STA response were not re-produced from the new DEF, fails here
     without a simulator. The SPEF is deliberately NOT bound: the response
     records no SPEF digest, so a re-generated SPEF is not caught here;
  3. the report's environment.sdf.annotated is literal true and the request's
     options.sdf.file resolves to the committed SDF and hashes to the same
     digest -- an unannotated report, or a request pointing elsewhere, is not
     the evidence the companion describes.

--self-test builds throwaway fixture trees carrying exactly the mutations the
gate exists to catch (netlist edit, SDF edit, report edit, STA digest alone,
DEF edit with the SDF and STA response left self-consistent, unannotated
report, remap broken) and asserts each one fails with the right file named,
because nothing else stands between a stale SDF run and a green CI.
"""

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKSUMS = REPO / "sim/hyperram/records/functional-verification-ctrl-sdf.checksums.json"
STA_REC = REPO / "layout/records/sta-sdf.response.json"
FV_REQ = REPO / "flow/functional-verification-ctrl-sdf.json"

SDF_NAME = "layout/records/hyperram_ctrl.tt_025C_1v80.sdf"


def digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fail(msg):
    print(f"::error::{msg}")
    sys.exit(1)


def run(root):
    """The gate, against an explicit root so --self-test can point it at a
    fixture tree. Returns normally or exits 1 with an ::error line."""
    root = Path(root)
    book = json.loads((root / CHECKSUMS.relative_to(REPO)).read_text())
    sta = json.loads((root / STA_REC.relative_to(REPO)).read_text())

    # 1 -- the three recorded digests against the committed bytes
    recorded = {e["path"]: e["sha256"] for e in book["inputs"]}
    recorded[book["report"]["path"]] = book["report"]["sha256"]
    for path, want in sorted(recorded.items()):
        f = root / path
        if not f.exists():
            fail(f"{path} is named by {CHECKSUMS.relative_to(REPO).as_posix()} but missing")
        got = digest(f)
        if got != want:
            fail(f"{path} drifted: checksums record {want}, checkout has {got}; "
                 "re-run `make -C verification/ctrl sdf` and commit the fresh "
                 "report, checksums and (if the layout changed) SDF + STA response")

    # 2 -- the SDF is the bytes the STA response produced
    envelope = sta.get("sdf")
    if not (isinstance(envelope, dict) and isinstance(envelope.get("content_hash"), str)):
        fail(f"{STA_REC.relative_to(REPO).as_posix()} carries no sdf.content_hash envelope")
    sdf_path = root / SDF_NAME
    if digest(sdf_path) != envelope["content_hash"]:
        fail(f"{SDF_NAME} does not hash to the producing STA response's "
             f"content_hash {envelope['content_hash']}")
    if envelope.get("path") != SDF_NAME or envelope.get("scope") != "repo":
        fail(f"{STA_REC.relative_to(REPO).as_posix()} sdf.path is "
             f"{envelope.get('path')!r} (scope {envelope.get('scope')!r}), not the "
             f"committed {SDF_NAME} -- the response no longer names the file beside it")
    if book["sta"]["sdf_content_hash"] != envelope["content_hash"]:
        fail("the checksums' sta.sdf_content_hash disagrees with the STA response's "
             "sdf.content_hash")
    # ... and the response itself is still bound to the DEF it was produced
    # from: a re-route that did not re-run STA leaves a byte-fresh SDF bound
    # to the old layout's DEF, which is exactly the stale evidence this gate
    # exists to refuse.
    prov = (sta.get("provenance") or {}).get("input") or {}
    def_env = sta.get("def_path")
    prov_hash = prov.get("content_hash") if isinstance(prov, dict) else None
    def_name = def_env.get("path") if isinstance(def_env, dict) else None
    if not (isinstance(prov_hash, str) and prov_hash.startswith("sha256:")
            and isinstance(def_name, str)):
        fail(f"{STA_REC.relative_to(REPO).as_posix()} carries no def_path / "
             "provenance.input.content_hash pair to bind the SDF to its layout")
    def_path = root / def_name
    if not def_path.exists():
        fail(f"{def_name} is named by def_path but missing")
    if digest(def_path) != prov_hash:
        fail(f"{def_name} drifted: the STA response's provenance.input.content_hash "
             f"{prov_hash} was produced from a different DEF; a re-route must "
             "re-run `make post-route-sdf` so the SDF and its response are re-produced "
             "from the new layout")

    # 3 -- the report is an annotated run of exactly that SDF
    report_path = root / book["report"]["path"]
    report = json.loads(report_path.read_text())
    sdf_env = (report.get("environment") or {}).get("sdf")
    if not (isinstance(sdf_env, dict) and sdf_env.get("annotated") is True):
        fail(f"{book['report']['path']} is not SDF-annotated evidence: "
             "environment.sdf.annotated is not literal true")
    req_path = root / FV_REQ.relative_to(REPO)
    req = json.loads(req_path.read_text())
    req_sdf = (req.get("options") or {}).get("sdf", {}).get("file")
    req_target = (req_path.parent / req_sdf).resolve() if req_sdf else None
    if req_target is None or not req_target.exists():
        fail(f"{FV_REQ.relative_to(REPO).as_posix()} names no readable options.sdf.file")
    if digest(req_target) != envelope["content_hash"]:
        fail(f"{FV_REQ.relative_to(REPO).as_posix()} options.sdf.file does not hash to "
             "the SDF the STA response produced")
    print("post-route SDF evidence is fresh: netlist, SDF and report digests match; "
          "SDF bound to its STA response; report annotated")


def fixture(tmp, mutate=None):
    """A minimal self-consistent tree carrying the real shapes the gate reads."""
    root = Path(tmp)
    net = b"module routed(); endmodule\n"
    dfn = b"VERSION 5.8 ; DIVIDERCHAR \"/\" ; BUSBITS \"[\" ;\n"
    sdf = b"(DELAYFILE (SDFVERSION \"3.0\") (CELL (CELLTYPE \"hyperram_ctrl\") (INSTANCE) ))\n"
    req = {"options": {"sdf": {"file": "../layout/records/hyperram_ctrl.tt_025C_1v80.sdf"}}}
    report = {"environment": {"sdf": {"annotated": True}}, "status": "pass"}
    sta = {
        "def_path": {"path": "layout/records/hyperram_ctrl.def", "scope": "repo"},
        "provenance": {"input": {"content_hash": digest_bytes(dfn), "role": "layout"}},
        "sdf": {"path": SDF_NAME, "scope": "repo", "content_hash": digest_bytes(sdf)},
    }
    book = {
        "note": "fixture",
        "request": "flow/functional-verification-ctrl-sdf.json",
        "sta": {"request": "flow/sta-sdf-hyperram.json",
                "response": "layout/records/sta-sdf.response.json",
                "sdf_content_hash": sta["sdf"]["content_hash"]},
        "inputs": [
            {"path": "layout/records/hyperram_ctrl.routed.v", "sha256": digest_bytes(net)},
            {"path": SDF_NAME, "sha256": sta["sdf"]["content_hash"]},
        ],
        "report": {"path": "sim/hyperram/records/f.report.json",
                   "sha256": digest_bytes(json.dumps(report).encode())},
    }
    (root / "layout/records").mkdir(parents=True)
    (root / "sim/hyperram/records").mkdir(parents=True)
    (root / "flow").mkdir(parents=True)
    (root / "layout/records/hyperram_ctrl.routed.v").write_bytes(net)
    (root / "layout/records/hyperram_ctrl.def").write_bytes(dfn)
    (root / SDF_NAME).write_bytes(sdf)
    (root / "flow/functional-verification-ctrl-sdf.json").write_text(json.dumps(req))
    (root / "sim/hyperram/records/f.report.json").write_text(json.dumps(report))
    (root / "layout/records/sta-sdf.response.json").write_text(json.dumps(sta))
    (root / CHECKSUMS.relative_to(REPO)).write_text(json.dumps(book))
    if mutate:
        mutate(root)
    return root


def digest_bytes(b):
    return "sha256:" + hashlib.sha256(b).hexdigest()


def self_test():
    ok = 0

    def expect_fail(name, mutate, needle):
        nonlocal ok
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, mutate)
            # a fresh buffer per case -- case N's needle can never be
            # satisfied by case N-1's output -- read only on failure, so a
            # passing self-test emits no ::error:: lines to real stdout
            buf = io.StringIO()
            old, sys.stdout = sys.stdout, buf
            try:
                run(root)
            except SystemExit as exc:
                out = buf.getvalue()
                assert exc.code == 1, f"{name}: exited {exc.code}, not 1"
                assert needle in out, f"{name}: error did not name {needle!r}: {out.strip()}"
                ok += 1
                return
            finally:
                sys.stdout = old
            raise AssertionError(f"{name}: the gate passed a mutated fixture")

    def flip_netlist(root):
        p = root / "layout/records/hyperram_ctrl.routed.v"
        p.write_bytes(p.read_bytes() + b"// drifted\n")

    def flip_sdf(root):
        p = root / SDF_NAME
        p.write_bytes(p.read_bytes() + b";\n")

    def flip_report(root):
        p = root / "sim/hyperram/records/f.report.json"
        doc = json.loads(p.read_text())
        doc["status"] = "drifted"
        p.write_text(json.dumps(doc))

    def flip_def(root):
        p = root / "layout/records/hyperram_ctrl.def"
        p.write_bytes(p.read_bytes() + b"# re-routed\n")

    def flip_sta_digest(root):
        p = root / "layout/records/sta-sdf.response.json"
        doc = json.loads(p.read_text())
        doc["sdf"]["content_hash"] = "sha256:" + "0" * 64
        p.write_text(json.dumps(doc))

    def unannotate(root):
        p = root / "sim/hyperram/records/f.report.json"
        doc = json.loads(p.read_text())
        doc["environment"]["sdf"]["annotated"] = "true"
        p.write_text(json.dumps(doc))
        # keep the companion's digest consistent so the annotated-check is
        # what fires, not the drift check
        b = root / CHECKSUMS.relative_to(REPO)
        book = json.loads(b.read_text())
        book["report"]["sha256"] = digest(p)
        b.write_text(json.dumps(book))

    def break_remap(root):
        p = root / "layout/records/sta-sdf.response.json"
        doc = json.loads(p.read_text())
        doc["sdf"]["path"] = "flow/.klt/sta/hyperram_ctrl.tt_025C_1v80.sdf"
        p.write_text(json.dumps(doc))

    with tempfile.TemporaryDirectory() as tmp:
        buf = io.StringIO()
        old, sys.stdout = sys.stdout, buf
        try:
            run(fixture(tmp))  # must not raise
        finally:
            sys.stdout = old
        assert "::error::" not in buf.getvalue(), \
            f"clean fixture errored: {buf.getvalue().strip()}"
        ok += 1
    expect_fail("routed-netlist drift", flip_netlist, "hyperram_ctrl.routed.v drifted")
    expect_fail("sdf drift", flip_sdf, "tt_025C_1v80.sdf drifted")
    expect_fail("report drift", flip_report, "f.report.json drifted")
    expect_fail("sta digest alone", flip_sta_digest, "does not hash to the producing STA")
    expect_fail("def drift, SDF/STA self-consistent", flip_def,
                "was produced from a different DEF")
    expect_fail("string \"true\" annotation", unannotate, "not SDF-annotated")
    expect_fail("scratch-path remap lost", break_remap, "sdf.path is")
    print(f"check_sdf_evidence.py self-test: {ok}/8 cases behaved")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
        sys.exit(0)
    run(REPO)
