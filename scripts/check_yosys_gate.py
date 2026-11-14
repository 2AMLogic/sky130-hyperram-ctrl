#!/usr/bin/env python3
"""Check flow/hyperram.py's pinned-yosys gate, without yosys, klt or the PDK.

`require_pinned_yosys()` is the only thing between a yosys that is not the
pinned build and a committed netlist or freshness result (issues #81, #89). The
synthesis it guards is `local_only` -- CI has no yosys and no PDK -- so the gate
itself is checked here instead, by calling it directly with fabricated klt
responses and a temporary $PATH. flow/klt_run.py and flow/hyperram.py do no work
at import and reach no tool until a function is called, so importing the runner
costs nothing.

What the $PATH fixtures are, stated plainly rather than implied. A fake
yowasp-yosys environment is a bin/ directory shaped exactly like the one
scripts/setup-env.sh builds -- a `yosys` relative symlink to a sibling
`yowasp-yosys` file -- next to a `python3` *stand-in*: a small script that runs
the gate's own hashing snippet with a fabricated `yowasp_yosys` package on
sys.path. So the snippet really executes and really hashes a real file on disk,
and the comparison is the real one. What these fixtures do NOT cover is a real
wheel install; that half is the pinned-path regression (`scripts/setup-env.sh`
then `make hyperram-check`), which needs yosys and the PDK and is recorded on
the PR instead of run here.

The last case is a mutation check, because every other case here would stay
green if the hash comparison were deleted *and replaced by something else that
happened to reject*. It neutralises that one comparison in a copy of the gate's
source and asserts the unpinned-0.68 case is then accepted -- so the rejections
above are pinned to that comparison, not to any incidental guard.
"""

import contextlib
import hashlib
import io
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FLOW = REPO / "flow"
GATE_SRC = FLOW / "hyperram.py"
sys.path.insert(0, str(FLOW))
import hyperram  # noqa: E402

# The real pins, read by the real code path. No second copy lives in this file.
WHEEL, ENGINE, PINNED_SHA = hyperram.pinned_yosys()

# The hash comparison this check exists to protect, and how to neutralise it.
MUTATE_FROM = "if got_sha != want_sha:"
MUTATE_TO = "if False:  # neutralised by scripts/check_yosys_gate.py"

# Stands in for a python interpreter that has yowasp_yosys installed. The gate
# runs `<env>/bin/python3 -I -B -c <snippet>`; this executes that snippet.
#
# sys.path is pinned to the stdlib plus the fixture's own site dir, because -I
# arrives as an argv string here, not as an interpreter flag, so without this
# the host's site-packages leak in -- and this dispatch host turns out to have
# the pinned yowasp-yosys installed user-wide, which silently made the
# "module will not import" case pass by importing a real pinned wheel instead.
# Absolute shebang on purpose: $PATH is replaced during these cases, so
# `env python3` would resolve back to this script.
PY_STANDIN = '''#!{python}
import sys, sysconfig
stdlib = {{sysconfig.get_paths()[k] for k in ("stdlib", "platstdlib")}}
sys.path[:] = [{site!r}] + [p for p in sys.path if p in stdlib or p.endswith(".zip")]
exec(compile(sys.argv[sys.argv.index("-c") + 1], "<standin>", "exec"),
     {{"__name__": "__main__"}})
'''

failures = []


def record(ok, name, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"\n       {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def fake_env(root, *, wasm=b"", with_python=True, with_module=True):
    """A bin/ shaped like scripts/setup-env.sh's; returns it, to put on $PATH."""
    bin_dir, site = root / "bin", root / "site"
    bin_dir.mkdir(parents=True)
    site.mkdir(parents=True)
    script = bin_dir / "yowasp-yosys"
    script.write_text("# console script; never executed here\n")
    script.chmod(0o755)  # pip's real console script is executable; which() needs it
    os.symlink("yowasp-yosys", bin_dir / "yosys")  # relative, as setup-env.sh:90
    if with_module:
        pkg = site / "yowasp_yosys"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "yosys.wasm").write_bytes(wasm)
    if with_python:
        py = bin_dir / "python3"
        py.write_text(PY_STANDIN.format(python=sys.executable, site=str(site)))
        py.chmod(0o755)
    return bin_dir


def call_gate(path, *, engine="yosys", engine_version=None, gate=None):
    """-> (exit status, or None if the run was accepted; what it wrote to stderr)."""
    gate = gate or hyperram.require_pinned_yosys
    doc = {"engine": engine, "engine_version": ENGINE if engine_version is None else engine_version}
    saved = os.environ.get("PATH", "")
    os.environ["PATH"] = str(path)
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            gate(doc)
        return None, err.getvalue()
    except SystemExit as exc:
        return exc.code, err.getvalue()
    finally:
        os.environ["PATH"] = saved


def mutated_gate():
    """The gate with its hash comparison neutralised, or None if it has drifted."""
    src = GATE_SRC.read_text()
    if src.count(MUTATE_FROM) != 1:
        return None
    ns = {"__name__": "check_yosys_gate.mutant", "__file__": str(GATE_SRC)}
    exec(compile(src.replace(MUTATE_FROM, MUTATE_TO), str(GATE_SRC), "exec"), ns)
    return ns["require_pinned_yosys"]


def main():
    print(f"pin: yowasp-yosys {WHEEL} reports {ENGINE}, yosys.wasm sha256:{PINNED_SHA}")
    with tempfile.TemporaryDirectory(prefix="check-yosys-gate-") as tmp:
        tmp = Path(tmp)
        empty = tmp / "empty"
        empty.mkdir()

        # A wheel whose wasm is NOT the pinned build. Its hash cannot be the
        # pin (that would need a sha256 preimage), which is what makes it the
        # defect case: the right version string, the wrong build.
        impostor_wasm = b"not the pinned Yosys/ABC build\n"
        impostor_sha = hashlib.sha256(impostor_wasm).hexdigest()
        impostor = fake_env(tmp / "impostor", wasm=impostor_wasm)
        native = tmp / "native" / "bin"
        native.mkdir(parents=True)
        (native / "yosys").write_text("#!/bin/sh\necho 'Yosys 0.68 (native)'\n")
        (native / "yosys").chmod(0o755)
        no_module = fake_env(tmp / "no-module", with_module=False)

        # --- the defect this closes (issue #89) ---------------------------
        code, err = call_gate(impostor)
        record(code == hyperram.WRONG_YOSYS_EXIT,
               f"a yosys reporting the pinned {ENGINE} that is not the pinned wheel "
               f"exits {hyperram.WRONG_YOSYS_EXIT}", f"got exit {code!r}")
        record(PINNED_SHA in err and impostor_sha in err,
               "and its message names both the expected and the actual build identity",
               f"stderr: {err.strip()[:300]!r}")

        # --- the version-string half still works (issue #81) --------------
        code, _ = call_gate(impostor, engine_version="0.67+post")
        record(code == hyperram.WRONG_YOSYS_EXIT,
               f"a yosys reporting 0.67+post exits {hyperram.WRONG_YOSYS_EXIT} "
               f"(the pre-existing check is intact)", f"got exit {code!r}")
        code, _ = call_gate(impostor, engine="nextpnr", engine_version=ENGINE)
        record(code == hyperram.WRONG_YOSYS_EXIT,
               f"a response from an engine other than yosys exits "
               f"{hyperram.WRONG_YOSYS_EXIT}", f"got exit {code!r}")

        # --- the unidentifiable cases must fail closed, never pass --------
        for label, path in (("no `yosys` on $PATH at all", empty),
                            ("a native yosys with no sibling python3", native),
                            ("a yowasp-yosys layout whose module will not import", no_module)):
            code, err = call_gate(path)
            record(code == hyperram.WRONG_YOSYS_EXIT,
                   f"{label} fails closed with exit {hyperram.WRONG_YOSYS_EXIT}",
                   f"got exit {code!r}; stderr: {err.strip()[:200]!r}")

        # --- the accept path, so this is not a blanket reject -------------
        # The fixture's wasm cannot hash to the real pin, so the *expected*
        # hash is swapped for the fixture's own: same comparison, both sides
        # fabricated, which is all the accept path can be checked with offline.
        genuine_wasm = b"stands in for the pinned yosys.wasm\n"
        genuine = fake_env(tmp / "genuine", wasm=genuine_wasm)
        genuine_sha = hashlib.sha256(genuine_wasm).hexdigest()
        real_pinned_yosys = hyperram.pinned_yosys
        hyperram.pinned_yosys = lambda: (WHEEL, ENGINE, genuine_sha)
        try:
            code, err = call_gate(genuine)
        finally:
            hyperram.pinned_yosys = real_pinned_yosys
        record(code is None,
               "a yosys whose yosys.wasm matches the expected hash is accepted",
               f"got exit {code!r}; stderr: {err.strip()[:200]!r}")

        # --- the hash comparison is load-bearing --------------------------
        mutant = mutated_gate()
        if mutant is None:
            record(False, "the gate still contains the hash comparison this check mutates",
                   f"no unique {MUTATE_FROM!r} in {GATE_SRC.relative_to(REPO)}")
        else:
            code, _ = call_gate(impostor, gate=mutant)
            record(code is None,
                   "neutralising the hash comparison makes the unpinned-"
                   f"{ENGINE} case pass (so the rejections above are that "
                   "comparison, not an incidental guard)",
                   f"got exit {code!r} from the mutated gate")

        # --- a missing pin is FATAL, like the missing-version case ---------
        for missing, keep in (("YOWASP_YOSYS_WASM_SHA256", "YOWASP_YOSYS_VERSION"),
                              ("YOWASP_YOSYS_VERSION", "YOWASP_YOSYS_WASM_SHA256")):
            fake_repo = tmp / f"pin-without-{missing}"
            (fake_repo / "scripts").mkdir(parents=True)
            text = "\n".join(line for line in GATE_PIN_SOURCE.splitlines()
                             if not line.startswith(f"{missing}="))
            (fake_repo / "scripts/setup-env.sh").write_text(text + "\n")
            saved = (hyperram.REPO, hyperram.SETUP_ENV)
            hyperram.REPO = fake_repo
            hyperram.SETUP_ENV = fake_repo / "scripts/setup-env.sh"
            try:
                code, _ = call_gate(impostor)
            finally:
                hyperram.REPO, hyperram.SETUP_ENV = saved
            record(isinstance(code, str) and code.startswith("FATAL:") and missing in code,
                   f"a scripts/setup-env.sh with no {missing}= pin is FATAL",
                   f"got exit {code!r}")

    if failures:
        print(f"\n::error::{len(failures)} pinned-yosys gate check(s) failed: "
              + "; ".join(failures))
        return 1
    print("\npinned-yosys gate rejects every unpinned build checked here")
    return 0


GATE_PIN_SOURCE = (REPO / "scripts/setup-env.sh").read_text()

if __name__ == "__main__":
    sys.exit(main())
