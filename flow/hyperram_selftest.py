#!/usr/bin/env python3
"""Offline self-tests for the hyperram flow's committed-record gates.

Split out of flow/hyperram.py (issue #229) so the production runner (synth,
sta, layout, publish) is not interleaved with fixture-building harnesses.
Behaviour is unchanged; the tests exercise flow/hyperram.py by copying it
(and klt_run.py) into a temp root.

  hyperram_selftest.py sta-check            # the sta-note / sta-check suite (#208, #215)
  hyperram_selftest.py sta-postroute-check  # the sta-postroute-note / -check suite (#215)

`hyperram.py sta-check --self-test` and `hyperram.py sta-postroute-check
--self-test` dispatch here, so both spellings run the same code.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hyperram import (  # noqa: E402
    format_sta_postroute_marker, parse_sta_postroute_marker, sha256, sta_check,
    STA_REQ, STAPR_MARKER_RE, sta_note, sta_note_cmd, sta_note_paths, sta_postroute_check,
    sta_postroute_note, sta_postroute_note_cmd, sta_postroute_paths,
)

FLOW = Path(__file__).resolve().parent


def copy_runner(root):
    """Copy the runner under test (flow/hyperram.py) and its klt_run.py
    dependency into a fixture root's flow/ directory."""
    shutil.copyfile(FLOW / "hyperram.py", root / "flow/hyperram.py")
    shutil.copyfile(FLOW / "klt_run.py", root / "flow/klt_run.py")


def c_locale_env():
    """A subprocess environment whose preferred encoding is genuinely ASCII:
    the C locale with PEP 538 locale coercion and PEP 540 UTF-8 mode both
    switched off. Only meaningful without `-I`: it implies -E and would
    ignore PYTHONUTF8 / PYTHONCOERCECLOCALE, letting PEP 538 coerce the C
    locale back to UTF-8 and leaving a text-mode write failure unexercised."""
    env = dict(os.environ, LC_ALL="C", LANG="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")
    env.pop("PYTHONIOENCODING", None)
    return env


def install_fake_klt(root, responses):
    """Stand klt in for a producer self-test: a scripts/klt.sh that prints the
    canned response filed under its request's file stem, so `sta` /
    `sta-postroute` run their real write path with no OpenROAD and no PDK.
    `responses` maps a request stem (e.g. "sta-hyperram") to the JSON klt
    returns for it."""
    canned = root / "scripts/fake-klt"
    canned.mkdir(parents=True, exist_ok=True)
    for stem, doc in responses.items():
        (canned / f"{stem}.json").write_bytes((json.dumps(doc) + "\n").encode("utf-8"))
    klt_sh = root / "scripts/klt.sh"
    klt_sh.write_bytes(b'#!/bin/sh\n'
                       b'exec cat "$(dirname "$0")/fake-klt/$(basename "$2" .json).json"\n')
    klt_sh.chmod(0o755)


def sta_check_self_test():
    """Offline regression suite for `sta-note` + `sta-check` (issue #208).

    Verifies that a clean fixture passes, that a one-byte edit to STA.md (or a
    CRLF rewrite -- the comparison is byte-for-byte, not line-by-line) or a
    mutated sta.json without regenerating the note fails with exit 3, that
    `sta-note` refuses missing inputs or a non-ok record without touching the
    note, and that it repairs the drifted-note case -- including an end-to-end
    CLI subprocess run of the exact repair path CI relies on. Last, that a
    live `sta` run (klt stood in) under a non-UTF-8 locale mints exactly the
    bytes the gate binds (issue #215).
    """
    corners = ["ss_100C_1v60", "tt_025C_1v80"]  # one outside, one inside the window
    cells = ["sky130_fd_sc_hd__clkdlybuf4s50", "sky130_fd_sc_hd__dlygate4sd3_1"]

    def make_fixture(tmp, *, with_runner=False):
        root = Path(tmp)
        rec_p, note_p, stat_p = sta_note_paths(root)
        req_p = root / "flow/sta-hyperram.json"
        for p in (rec_p, req_p):
            p.parent.mkdir(parents=True, exist_ok=True)
        if with_runner:
            copy_runner(root)
        # sta_note() reads its own request; the fixture carries the committed
        # one so in-process and CLI renders agree byte-for-byte.
        req_p.write_bytes(STA_REQ.read_bytes())
        stat_p.write_bytes((json.dumps({"blackbox_modules": cells}, indent=2) + "\n").encode("utf-8"))
        doc = {
            "engine": "openroad",
            "engine_version": "test",
            "hdl_toplevel": "hyperram_ctrl",
            "status": "ok",
            "verilog_path": {"path": "sim/hyperram/records/hyperram_ctrl.netlist.v",
                             "scope": "repo"},
            "geometry_source": "netlist_estimate",
            "clock_mode": "ideal",
            "wire_load_model": None,
            "wire_load_mode": None,
            "def_path": None,
            "spef_path": None,
            "provenance": {
                "klt_version": "0.9.2",
                "pdk": {"version": "open_pdks test"},
                "input": {"content_hash": "sha256:" + "0" * 64, "role": "netlist"},
            },
            "corners": [
                {
                    "corner": name,
                    "worst_slack_ns": 1.25,
                    "worst_hold_slack_ns": 0.25,
                    "setup_violation_count": 0,
                    "total_negative_slack_ns": 0.0,
                    "hold_violation_count": 0,
                    "total_negative_hold_slack_ns": 0.0,
                    "fmax_mhz": 53.3,
                    "timing_status": "constrained",
                    "constraint_completeness": {
                        "status": "incomplete",
                        "unclocked_registers": {"status": "ok", "count": 143},
                        "unconstrained_endpoints": {"count": 341},
                    },
                }
                for name in corners
            ],
        }
        rec_p.write_bytes((json.dumps(doc, indent=2) + "\n").encode("utf-8"))
        note_p.write_bytes(sta_note(doc, cells).encode("utf-8"))
        return root

    def call_quiet(fn, root):
        out_buf, err_buf = io.StringIO(), io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out_buf, err_buf
        try:
            fn(root)
            return 0, out_buf.getvalue() + err_buf.getvalue()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            msg = exc.code if isinstance(exc.code, str) else ""
            return code, out_buf.getvalue() + err_buf.getvalue() + msg
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    passed = 0

    # 1. Clean copy passes; a one-byte note edit fails with exit 3 and the
    #    remedy message; `sta-note` restores the exact rendered bytes.
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(tmp)
        _, note_p, _ = sta_note_paths(root)
        rc, out = call_quiet(sta_check, root)
        assert rc == 0, f"clean fixture failed check (rc={rc}): {out}"
        orig = note_p.read_bytes()
        note_p.write_bytes(orig + b" ")
        rc, out = call_quiet(sta_check, root)
        assert rc == 3 and "differs from a fresh render" in out, \
            f"one-byte note edit missed (rc={rc}): {out}"
        assert "python3 -I flow/hyperram.py sta-note" in out, f"remedy missing: {out}"
        rc, out = call_quiet(sta_note_cmd, root)
        assert rc == 0, f"note regen failed (rc={rc}): {out}"
        assert note_p.read_bytes() == orig, "sta-note did not restore the exact rendered bytes"
        rc, out = call_quiet(sta_check, root)
        assert rc == 0, f"check after note regen failed (rc={rc}): {out}"
        passed += 1

    # 2. A CRLF rewrite counts as stale: the binding is byte-for-byte, so a
    #    line-ending change must not slip through a text-mode comparison.
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(tmp)
        note_p = sta_note_paths(root)[1]
        note_p.write_bytes(note_p.read_bytes().replace(b"\n", b"\r\n"))
        rc, out = call_quiet(sta_check, root)
        assert rc == 3 and "differs from a fresh render" in out, \
            f"CRLF rewrite missed (rc={rc}): {out}"
        passed += 1

    # 3. Mutating sta.json without regenerating the note fails the check; after
    #    `sta-note` the note follows the committed record (the record<->netlist
    #    binding is local_only, not this gate's to answer).
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(tmp)
        rec_p = sta_note_paths(root)[0]
        doc = json.loads(rec_p.read_text(encoding="utf-8"))
        doc["corners"][1]["worst_slack_ns"] = 0.75
        rec_p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        rc, out = call_quiet(sta_check, root)
        assert rc == 3 and "differs from a fresh render" in out, \
            f"record drift missed (rc={rc}): {out}"
        rc, out = call_quiet(sta_note_cmd, root)
        assert rc == 0, f"note regen after record drift failed (rc={rc}): {out}"
        rc, out = call_quiet(sta_check, root)
        assert rc == 0, f"check after note regen failed (rc={rc}): {out}"
        passed += 1

    # 4..6. Missing synth-stat.json, missing sta.json, non-ok record: sta-note
    #        refuses (exit 1, FATAL:) with the note untouched; sta-check
    #        refuses the same way instead of minting a verdict.
    def expect_refused(name, mutate, needle):
        nonlocal passed
        with tempfile.TemporaryDirectory() as tmp:
            root = make_fixture(tmp)
            note_p = sta_note_paths(root)[1]
            mutate(root)
            note_before = note_p.read_bytes()
            rc_n, out_n = call_quiet(sta_note_cmd, root)
            assert rc_n == 1, f"{name}: sta-note exited {rc_n}, expected 1: {out_n}"
            assert "FATAL:" in out_n and needle in out_n, \
                f"{name}: sta-note missed {needle!r}: {out_n}"
            assert note_p.read_bytes() == note_before, f"{name}: sta-note modified STA.md"
            rc_c, out_c = call_quiet(sta_check, root)
            assert rc_c == 1, f"{name}: sta-check exited {rc_c}, expected 1: {out_c}"
            assert "FATAL:" in out_c and needle in out_c, \
                f"{name}: sta-check missed {needle!r}: {out_c}"
            passed += 1

    def drop_stat(root):
        sta_note_paths(root)[2].unlink()

    def drop_rec(root):
        sta_note_paths(root)[0].unlink()

    def break_status(root):
        rec_p = sta_note_paths(root)[0]
        doc = json.loads(rec_p.read_text(encoding="utf-8"))
        doc["status"] = "error"
        rec_p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    expect_refused("missing-synth-stat", drop_stat, "synth-stat.json missing")
    expect_refused("missing-sta-json", drop_rec, "sta.json missing")
    expect_refused("non-ok-record", break_status, "not 'ok'")

    # 7. End-to-end CLI: the exact CI repair path as a subprocess -- check
    #    exits 3 on a one-byte edit, sta-note repairs it, check exits 0.
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(tmp, with_runner=True)
        note_p = sta_note_paths(root)[1]
        orig = note_p.read_bytes()
        note_p.write_bytes(orig + b" ")
        runner = str(root / "flow/hyperram.py")
        c1 = subprocess.run([sys.executable, "-I", runner, "sta-check"],
                            capture_output=True, text=True)
        assert c1.returncode == 3 and "differs from a fresh render" in c1.stdout, \
            f"cli: pre-note check exited {c1.returncode}: {c1.stdout}{c1.stderr}"
        n1 = subprocess.run([sys.executable, "-I", runner, "sta-note"],
                            capture_output=True, text=True)
        assert n1.returncode == 0, \
            f"cli: sta-note exited {n1.returncode}: {n1.stdout}{n1.stderr}"
        assert note_p.read_bytes() == orig, "cli: sta-note did not restore the exact bytes"
        c2 = subprocess.run([sys.executable, "-I", runner, "sta-check"],
                            capture_output=True, text=True)
        assert c2.returncode == 0, \
            f"cli: post-note check exited {c2.returncode}: {c2.stdout}{c2.stderr}"
        passed += 1

    # 8. Non-ASCII field under a non-UTF-8 locale: the repair command must
    #    write the same UTF-8/LF bytes `sta-check` expects, and a failure must
    #    never truncate the note. (The JSON record escapes the character; the
    #    rendered note carries it raw.)
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(tmp, with_runner=True)
        rec_p, note_p, _ = sta_note_paths(root)
        doc = json.loads(rec_p.read_text(encoding="utf-8"))
        doc["engine_version"] = "test \u00b1 1.0"
        rec_p.write_bytes((json.dumps(doc, indent=2) + "\n").encode("utf-8"))
        runner = str(root / "flow/hyperram.py")
        env = c_locale_env()
        n1 = subprocess.run([sys.executable, runner, "sta-note"],
                            capture_output=True, env=env)
        assert n1.returncode == 0, \
            f"cli/C-locale: sta-note exited {n1.returncode}: {n1.stdout!r}{n1.stderr!r}"
        got = note_p.read_bytes()
        assert got, "cli/C-locale: sta-note left a zero-byte STA.md"
        assert b"\r" not in got, "cli/C-locale: sta-note wrote CR bytes"
        assert "\u00b1".encode("utf-8") in got, "cli/C-locale: non-ASCII field not written as UTF-8"
        c1 = subprocess.run([sys.executable, runner, "sta-check"],
                            capture_output=True, env=env)
        assert c1.returncode == 0, \
            f"cli/C-locale: sta-check exited {c1.returncode}: {c1.stdout!r}{c1.stderr!r}"
        passed += 1

    # 9. The `sta` producer under the same locale (issue #215): a live run must
    #    mint the canonical bytes itself, so the gate never reports STALE
    #    against a legitimate regeneration. scripts/klt.sh is stood in by a
    #    replay of the fixture record with a non-ASCII engine_version, and the
    #    blackbox liberty check by a stand-in OpenSTA script and liberty.
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(tmp, with_runner=True)
        rec_p, note_p, _ = sta_note_paths(root)
        req_p = root / "flow/sta-hyperram.json"
        doc = json.loads(rec_p.read_text(encoding="utf-8"))
        doc["engine_version"] = "test \u00b1 1.0"
        tcl, lib = root / "flow/.klt/sta/fake.tcl", root / "flow/.klt/fake.lib"
        tcl.parent.mkdir(parents=True)
        tcl.write_bytes(f"read_liberty {lib}\n".encode("utf-8"))
        lib.write_bytes("".join(f'cell ("{c}") {{}}\n' for c in cells).encode("utf-8"))
        for c in doc["corners"]:
            c["engine_log"] = {"script_path": {"path": "flow/.klt/sta/fake.tcl", "scope": "repo"}}
        # sta() requires the response to answer the request's corner list.
        req = json.loads(req_p.read_text(encoding="utf-8"))
        req["pdk"]["corners"] = corners
        req_p.write_bytes((json.dumps(req, indent=2) + "\n").encode("utf-8"))
        (rec_p.parent / "hyperram_ctrl.netlist.v").write_bytes(b"")
        install_fake_klt(root, {req_p.stem: doc})
        runner = str(root / "flow/hyperram.py")
        env = c_locale_env()
        s1 = subprocess.run([sys.executable, runner, "sta"], capture_output=True, env=env)
        assert s1.returncode == 0, \
            f"cli/C-locale: sta exited {s1.returncode}: {s1.stdout!r}{s1.stderr!r}"
        assert rec_p.read_bytes() == (json.dumps(doc, indent=2) + "\n").encode("utf-8"), \
            "cli/C-locale: sta did not write sta.json as UTF-8/LF bytes"
        got = note_p.read_bytes()
        assert got, "cli/C-locale: sta left a zero-byte STA.md"
        assert b"\r" not in got, "cli/C-locale: sta wrote CR bytes"
        assert "\u00b1".encode("utf-8") in got, "cli/C-locale: non-ASCII field not written as UTF-8"
        c1 = subprocess.run([sys.executable, runner, "sta-check"],
                            capture_output=True, env=env)
        assert c1.returncode == 0, \
            f"cli/C-locale: sta-check rejected the note sta just minted: " \
            f"{c1.returncode}: {c1.stdout!r}{c1.stderr!r}"
        passed += 1

    print(f"sta-check self-test: {passed}/{passed} cases passed")


def sta_postroute_self_test():
    """Offline regression suite for `sta-postroute-note` + `sta-postroute-check`.

    Verifies that editing the SPEF, either request, the DEF, or stripping/forging
    the note's provenance marker causes `sta-postroute-note` to refuse without
    touching the note and leaves `sta-postroute-check` failing with exit 3 --
    including end-to-end CLI subprocess runs for SPEF drift and a request whose
    `spef` field points to a missing file. Next, that the `sta-postroute` /
    `sta-postroute-note` producers (klt stood in) under a non-UTF-8 locale
    write a note carrying a non-ASCII field as UTF-8/LF bytes, and that the
    gate accepts what they mint (issue #215). Last, the read side of the same
    contract (issue #221): response records saved with literal non-ASCII UTF-8
    and a note carrying the same character raw pass `sta-postroute-check` and
    regenerate exactly under the C locale, and a CRLF-only rewrite of a fresh
    note is STALE -- the note binding is byte-for-byte, not line-by-line.
    """
    corners = ["ss_n40C_1v28", "tt_025C_1v80"]
    clocks = [{"port": "clk", "period_ns": 20.0}, {"port": "hb_rwds_i", "period_ns": 20.0}]

    def make_fixture(tmp, *, with_runner=False):
        root = Path(tmp)
        rec_p, arec_p, note_p, req_p, areq_p, rdef_p, rspef_p = sta_postroute_paths(root)
        for p in (rec_p, req_p, rdef_p):
            p.parent.mkdir(parents=True, exist_ok=True)
        if with_runner:
            copy_runner(root)
        rdef_p.write_text("VERSION 5.8 ;\nDESIGN hyperram_ctrl ;\nEND DESIGN\n")
        rspef_p.write_text("*SPEF \"IEEE 1481-1998\"\n*D_NET *1 0.1200\n*CAP\n1 *1:1 0.1200\n*END\n")
        base_req = {
            "schema": "klt.sta.request/1",
            "def": "../layout/records/hyperram_ctrl.def",
            "spef": "../layout/records/hyperram_ctrl.spef",
            "hdl_toplevel": "hyperram_ctrl",
            "pdk": {"cell_library": "sky130_fd_sc_hd", "corners": corners},
            "constraints": {"clocks": clocks, "propagated_clock": True},
        }
        async_req = {
            **base_req,
            "constraints": {**base_req["constraints"], "clock_groups": [["clk"], ["hb_rwds_i"]]},
        }
        req_p.write_text(json.dumps(base_req, indent=2) + "\n")
        areq_p.write_text(json.dumps(async_req, indent=2) + "\n")
        def_sha = sha256(rdef_p)

        def make_resp(groups):
            return {
                "schema_version": 2,
                "engine": "openroad",
                "engine_version": "test",
                "hdl_toplevel": "hyperram_ctrl",
                "status": "ok",
                "def_path": {"path": "layout/records/hyperram_ctrl.def", "scope": "repo"},
                "spef_path": {"path": "layout/records/hyperram_ctrl.spef", "scope": "repo"},
                "geometry_source": "routed",
                "clock_mode": "propagated",
                "clock_targets": {"clocks": clocks, "clock_groups": groups},
                "provenance": {
                    "klt_version": "0.9.2",
                    "pdk": {"version": "open_pdks test"},
                    "input": {"content_hash": def_sha, "role": "layout"},
                },
                "corners": [
                    {
                        "corner": name,
                        "worst_slack_ns": 1.25,
                        "worst_hold_slack_ns": 0.25,
                        "setup_violation_count": 0,
                        "total_negative_slack_ns": 0.0,
                        "hold_violation_count": 0,
                        "total_negative_hold_slack_ns": 0.0,
                        "fmax_mhz": 53.3,
                        "timing_status": "constrained",
                        "spef_annotation": {
                            "design_nets_annotated": 10,
                            "design_nets_total": 10,
                            "annotation_complete": True,
                            "design_nets_missing_sample": [],
                            "reader_warning_count": 0,
                        },
                        "clock_propagation": {
                            "max_network_latency_ns": 0.5,
                            "clock_sinks": 1,
                            "clock_sinks_sample": ["u_fsm/q"],
                        },
                        "constraint_completeness": {
                            "status": "ok",
                            "unclocked_registers": {"status": "ok", "count": 0},
                            "unconstrained_endpoints": {"count": 0},
                        },
                        "worst_paths_by_group": {"setup": [], "hold": []},
                    }
                    for name in corners
                ],
            }

        doc = make_resp([])
        adoc = make_resp([["clk"], ["hb_rwds_i"]])
        rec_p.write_text(json.dumps(doc, indent=2) + "\n")
        arec_p.write_text(json.dumps(adoc, indent=2) + "\n")
        marker = format_sta_postroute_marker(def_sha, sha256(rspef_p), sha256(req_p), sha256(areq_p))
        note_p.write_text(sta_postroute_note(doc, adoc, base_req, marker=marker))
        return root

    def call_quiet(fn, root):
        out_buf, err_buf = io.StringIO(), io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out_buf, err_buf
        try:
            fn(root)
            return 0, out_buf.getvalue() + err_buf.getvalue()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            msg = exc.code if isinstance(exc.code, str) else ""
            return code, out_buf.getvalue() + err_buf.getvalue() + msg
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    passed = 0

    # 1. Clean baseline passes check, and prose-only drift repairs cleanly via
    #    sta-postroute-note while preserving the input provenance marker.
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(tmp)
        rc, out = call_quiet(sta_postroute_check, root)
        assert rc == 0, f"clean fixture failed check (rc={rc}): {out}"
        note_p = sta_postroute_paths(root)[2]
        orig = note_p.read_text()
        orig_marker = parse_sta_postroute_marker(orig)[0]
        note_p.write_text("# stale prose heading\n\n" + orig_marker + "\n")
        rc, out = call_quiet(sta_postroute_check, root)
        assert rc == 3 and "differs from a fresh render" in out, f"prose drift missed (rc={rc}): {out}"
        rc, out = call_quiet(sta_postroute_note_cmd, root)
        assert rc == 0, f"note regen on fresh provenance failed (rc={rc}): {out}"
        assert note_p.read_text() == orig, "regenerated note did not restore exact rendered text + marker"
        rc, out = call_quiet(sta_postroute_check, root)
        assert rc == 0, f"check after valid note regen failed (rc={rc}): {out}"
        passed += 1

    # 2 & 3. End-to-end CLI subprocess checks for the two exact regressions from
    #        review: (a) SPEF capacitance increased by 100 fF, and (b) request
    #        `spef` pointed at a missing file. In both cases: check exits 3 ->
    #        sta-postroute-note exits 3 without modifying STA-postroute.md ->
    #        check still exits 3 and response hashes are untouched.
    def expect_cli_regression(name, mutate, needle):
        nonlocal passed
        with tempfile.TemporaryDirectory() as tmp:
            root = make_fixture(tmp, with_runner=True)
            rec_p, arec_p, note_p, *_ = sta_postroute_paths(root)
            mutate(root)
            note_before = note_p.read_bytes()
            rec_before = (sha256(rec_p), sha256(arec_p))
            runner = str(root / "flow/hyperram.py")
            c1 = subprocess.run([sys.executable, "-I", runner, "sta-postroute-check"],
                                capture_output=True, text=True)
            assert c1.returncode == 3, f"{name}: pre-note check exited {c1.returncode}: {c1.stdout}{c1.stderr}"
            assert needle in c1.stdout, f"{name}: pre-note check missed {needle!r}: {c1.stdout}"
            n1 = subprocess.run([sys.executable, "-I", runner, "sta-postroute-note"],
                                capture_output=True, text=True)
            assert n1.returncode == 3, f"{name}: sta-postroute-note exited {n1.returncode}: {n1.stdout}{n1.stderr}"
            assert needle in n1.stdout, f"{name}: sta-postroute-note missed {needle!r}: {n1.stdout}"
            assert note_p.read_bytes() == note_before, f"{name}: sta-postroute-note rewrote STA-postroute.md"
            c2 = subprocess.run([sys.executable, "-I", runner, "sta-postroute-check"],
                                capture_output=True, text=True)
            assert c2.returncode == 3, f"{name}: post-note check exited {c2.returncode}: {c2.stdout}{c2.stderr}"
            assert (sha256(rec_p), sha256(arec_p)) == rec_before, f"{name}: responses changed"
            passed += 1

    def bump_spef_cap(root):
        rspef_p = sta_postroute_paths(root)[6]
        rspef_p.write_text(rspef_p.read_text().replace("0.1200", "0.2200"))

    def break_req_spef(root):
        req_p = sta_postroute_paths(root)[3]
        doc = json.loads(req_p.read_text())
        doc["spef"] = "../layout/records/missing.spef"
        req_p.write_text(json.dumps(doc, indent=2) + "\n")

    expect_cli_regression("spef-cap-bump", bump_spef_cap, "layout/records/hyperram_ctrl.spef")
    expect_cli_regression("req-missing-spef", break_req_spef, "flow/sta-hyperram-postroute.json")

    # 4..9. In-process checks covering async-request drift, DEF drift, stripped
    #       marker, zeroed marker, missing STA-postroute.md, and a forged marker
    #       whose request `spef` points at a different file.
    def expect_refused(name, mutate, want_rc, needle):
        nonlocal passed
        with tempfile.TemporaryDirectory() as tmp:
            root = make_fixture(tmp)
            note_p = sta_postroute_paths(root)[2]
            mutate(root)
            existed_before = note_p.exists()
            note_before = note_p.read_bytes() if existed_before else None
            rc_n, out_n = call_quiet(sta_postroute_note_cmd, root)
            assert rc_n == want_rc, f"{name}: note_cmd exited {rc_n}, expected {want_rc}: {out_n}"
            assert needle in out_n, f"{name}: note_cmd missed {needle!r}: {out_n}"
            if existed_before:
                assert note_p.read_bytes() == note_before, f"{name}: note_cmd modified STA-postroute.md"
            else:
                assert not note_p.exists(), f"{name}: note_cmd minted a missing STA-postroute.md"
            rc_c, out_c = call_quiet(sta_postroute_check, root)
            assert rc_c == want_rc, f"{name}: check after note_cmd exited {rc_c}, expected {want_rc}: {out_c}"
            assert needle in out_c, f"{name}: check missed {needle!r}: {out_c}"
            passed += 1

    def edit_async_req(root):
        areq_p = sta_postroute_paths(root)[4]
        doc = json.loads(areq_p.read_text())
        doc["constraints"]["clocks"][0]["period_ns"] = 40.0
        areq_p.write_text(json.dumps(doc, indent=2) + "\n")

    def edit_def(root):
        rdef_p = sta_postroute_paths(root)[5]
        rdef_p.write_text(rdef_p.read_text() + "# drifted\n")

    def strip_marker(root):
        note_p = sta_postroute_paths(root)[2]
        note_p.write_text(STAPR_MARKER_RE.sub("", note_p.read_text()))

    def zero_marker(root):
        note_p = sta_postroute_paths(root)[2]
        z = "sha256:" + "0" * 64
        forged = format_sta_postroute_marker(z, z, z, z)
        note_p.write_text(STAPR_MARKER_RE.sub(forged, note_p.read_text()))

    def delete_note(root):
        sta_postroute_paths(root)[2].unlink()

    def forge_redirected_spef(root):
        _, _, note_p, req_p, areq_p, rdef_p, rspef_p = sta_postroute_paths(root)
        other = rspef_p.parent / "other.spef"
        other.write_text(rspef_p.read_text())
        req_doc = json.loads(req_p.read_text())
        req_doc["spef"] = "../layout/records/other.spef"
        req_p.write_text(json.dumps(req_doc, indent=2) + "\n")
        forged = format_sta_postroute_marker(sha256(rdef_p), sha256(rspef_p),
                                             sha256(req_p), sha256(areq_p))
        note_p.write_text(STAPR_MARKER_RE.sub(forged, note_p.read_text()))

    expect_refused("async-req-drift", edit_async_req, 3, "flow/sta-hyperram-postroute-async.json")
    expect_refused("def-drift", edit_def, 3, "layout/records/hyperram_ctrl.def")
    expect_refused("missing-marker", strip_marker, 3, "marker missing or malformed")
    expect_refused("zeroed-marker", zero_marker, 3, "does not carry the input marker")
    expect_refused("missing-note-file", delete_note, 1, "STA-postroute.md missing")
    expect_refused("forged-marker-redirected-spef", forge_redirected_spef, 3, "does not resolve to")

    # 10. The `sta-postroute` and `sta-postroute-note` producers under a
    #     non-UTF-8 locale (issue #215): with scripts/klt.sh stood in by a
    #     replay of each request's committed response carrying a non-ASCII
    #     engine_version, both must write the note as UTF-8/LF bytes -- neither
    #     raise UnicodeEncodeError nor truncate it -- and what they mint must
    #     pass sta-postroute-check.
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(tmp, with_runner=True)
        rec_p, arec_p, note_p, req_p, areq_p, rdef_p, rspef_p = sta_postroute_paths(root)
        canned = {}
        for req_file, rec_file in ((req_p, rec_p), (areq_p, arec_p)):
            d = json.loads(rec_file.read_text(encoding="utf-8"))
            d["engine_version"] = "test \u00b1 1.0"
            canned[req_file.stem] = d
        doc, adoc = canned[req_p.stem], canned[areq_p.stem]
        install_fake_klt(root, canned)
        marker = format_sta_postroute_marker(sha256(rdef_p), sha256(rspef_p),
                                             sha256(req_p), sha256(areq_p))
        req = json.loads(req_p.read_text(encoding="utf-8"))
        want = [(rec_p, (json.dumps(doc, indent=2) + "\n").encode("utf-8")),
                (arec_p, (json.dumps(adoc, indent=2) + "\n").encode("utf-8")),
                (note_p, sta_postroute_note(doc, adoc, req, marker=marker).encode("utf-8"))]
        runner = str(root / "flow/hyperram.py")
        env = c_locale_env()
        s1 = subprocess.run([sys.executable, runner, "sta-postroute"],
                            capture_output=True, env=env)
        assert s1.returncode == 0, \
            f"cli/C-locale: sta-postroute exited {s1.returncode}: {s1.stdout!r}{s1.stderr!r}"
        for p, want_bytes in want:
            assert p.read_bytes() == want_bytes, \
                f"cli/C-locale: sta-postroute did not write {p.name} as UTF-8/LF bytes"
        minted = note_p.read_bytes()
        assert minted and b"\r" not in minted and "\u00b1".encode("utf-8") in minted, \
            "cli/C-locale: the minted STA-postroute.md is empty, CRLF, or not UTF-8"
        # Prose drift only: sta-postroute-note re-stamps nothing, so it refuses
        # a note without its provenance marker rather than repairing that.
        note_p.write_bytes(f"# stale prose heading\n\n{marker}\n".encode("utf-8"))
        n1 = subprocess.run([sys.executable, runner, "sta-postroute-note"],
                            capture_output=True, env=env)
        assert n1.returncode == 0, \
            f"cli/C-locale: sta-postroute-note exited {n1.returncode}: {n1.stdout!r}{n1.stderr!r}"
        assert note_p.read_bytes() == minted, \
            "cli/C-locale: sta-postroute-note did not restore the exact UTF-8/LF bytes"
        c1 = subprocess.run([sys.executable, runner, "sta-postroute-check"],
                            capture_output=True, env=env)
        assert c1.returncode == 0, \
            f"cli/C-locale: sta-postroute-check rejected the minted record: " \
            f"{c1.returncode}: {c1.stdout!r}{c1.stderr!r}"
        passed += 1

    # 11. The read side under the same locale (issue #221): response records
    #     saved with literal non-ASCII UTF-8 (ensure_ascii=False) and a note
    #     carrying the same character raw must pass `sta-postroute-check` and
    #     regenerate exactly under the C locale -- no read on this path may go
    #     through the host locale's preferred encoding.
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(tmp, with_runner=True)
        rec_p, arec_p, note_p, req_p, areq_p, rdef_p, rspef_p = sta_postroute_paths(root)
        docs = []
        for rec_file in (rec_p, arec_p):
            d = json.loads(rec_file.read_text(encoding="utf-8"))
            d["engine_version"] = "test \u00b1 1.0"
            rec_file.write_bytes((json.dumps(d, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
            docs.append(d)
        req = json.loads(req_p.read_text(encoding="utf-8"))
        marker = format_sta_postroute_marker(sha256(rdef_p), sha256(rspef_p),
                                             sha256(req_p), sha256(areq_p))
        want = sta_postroute_note(docs[0], docs[1], req, marker=marker).encode("utf-8")
        assert "\u00b1".encode("utf-8") in want, "fixture note carries no non-ASCII prose"
        note_p.write_bytes(want)
        runner = str(root / "flow/hyperram.py")
        env = c_locale_env()
        c1 = subprocess.run([sys.executable, runner, "sta-postroute-check"],
                            capture_output=True, env=env)
        assert c1.returncode == 0, \
            f"cli/C-locale: check rejected literal-UTF-8 records: " \
            f"{c1.returncode}: {c1.stdout!r}{c1.stderr!r}"
        note_p.write_bytes(f"# stale prose heading\n\n{marker}\n".encode("utf-8"))
        c2 = subprocess.run([sys.executable, runner, "sta-postroute-check"],
                            capture_output=True, env=env)
        assert c2.returncode == 3 and b"differs from a fresh render" in c2.stdout, \
            f"cli/C-locale: prose drift missed (rc={c2.returncode}): {c2.stdout!r}{c2.stderr!r}"
        n1 = subprocess.run([sys.executable, runner, "sta-postroute-note"],
                            capture_output=True, env=env)
        assert n1.returncode == 0, \
            f"cli/C-locale: note regen exited {n1.returncode}: {n1.stdout!r}{n1.stderr!r}"
        assert note_p.read_bytes() == want, \
            "cli/C-locale: note regen did not restore the exact UTF-8/LF bytes"
        passed += 1

    # 12. A CRLF-only rewrite of a fresh note is STALE, not a pass (issue #221):
    #     the note binding is byte-for-byte, so a line-ending change must not
    #     slip through a text-mode comparison. The marker survives the rewrite
    #     for `sta-postroute-note`, which restores the exact original bytes.
    with tempfile.TemporaryDirectory() as tmp:
        root = make_fixture(tmp)
        note_p = sta_postroute_paths(root)[2]
        orig = note_p.read_bytes()
        note_p.write_bytes(orig.replace(b"\n", b"\r\n"))
        rc, out = call_quiet(sta_postroute_check, root)
        assert rc == 3 and "differs from a fresh render" in out, \
            f"CRLF rewrite missed (rc={rc}): {out}"
        rc, out = call_quiet(sta_postroute_note_cmd, root)
        assert rc == 0, f"note regen after CRLF rewrite failed (rc={rc}): {out}"
        assert note_p.read_bytes() == orig, "note regen did not restore the exact LF bytes"
        rc, out = call_quiet(sta_postroute_check, root)
        assert rc == 0, f"check after CRLF repair failed (rc={rc}): {out}"
        passed += 1

    print(f"sta-postroute-check self-test: {passed}/{passed} cases passed")


SELF_TESTS = {"sta-check": sta_check_self_test,
              "sta-postroute-check": sta_postroute_self_test}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in SELF_TESTS:
        sys.exit(__doc__)
    SELF_TESTS[sys.argv[1]]()
