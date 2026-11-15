#!/usr/bin/env python3
"""Assert attest/item9.json declares every bench file on disk under verification/.

Why this exists (issue #93). `klt signoff --attest 9 --check` hashes the paths
the inventory lists, so a file the inventory *omits* is not drift -- it is
invisible. Before this check, a bench could be added anywhere under
verification/, be absent from the item-9 "Testbenches shipped" declaration,
never execute, and CI would still be green: a false positive inside append-only
evidence, which is the most expensive failure this repo has (CLAUDE.md: "no
claim without a testbench").

verification/ctrl/Makefile and verification/ctrl/test_all.py now derive their
module lists from this same directory, so neither can go stale.
attest/item9.json stays an explicit declaration -- deriving it would defeat its
purpose as the record of what was shipped -- so it is the one list that can
drift, and this is the check that stops it.

What is asserted: for verification/ itself and each of its immediate
subdirectories -- discovered from disk, so a bench directory added later is
covered without editing this file -- every top-level `*.py` and the `Makefile`
appears in attest/item9.json's `testbenches` array. The glob is deliberately
non-recursive and extension-scoped, so cocotb/Icarus build output
(`sim_build*/`, `__pycache__/`, `results.xml`) cannot reach it. The check is
one-way: a declared path with no file on disk, or one that is not a bench at
all (`flow/functional-verification-ctrl.json`, `verification/README.md`), is
never this check's failure -- the reverse direction is already caught by
`klt signoff --attest 9 --check`, and is not re-checked here.

  scripts/check_bench_coverage.py              check the repo (CI step 4c)
  scripts/check_bench_coverage.py --self-test   check this checker, on fixtures

The self-test is here because this file is now the only thing standing between
an undeclared bench and a green CI, so "it catches the hole" is a claim that
needs its own testbench. It drives the functions below over temporary
directories; it touches nothing in the repo and needs no klt, cocotb or PDK.

Exit 0 when the inventory covers every scanned directory, 1 otherwise. Needs
nothing but python3, so both modes run on the CI runner.
"""

import contextlib
import io
import json
import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
INVENTORY = REPO / "attest" / "item9.json"
SCAN_ROOT = REPO / "verification"
REGENERATE = (
    "scripts/klt.sh signoff --attest 9 --inventory attest/item9.json"
    " -o evidence/item9.json"
)


def bench_files(bench_dir, root):
    """Paths, relative to `root`, of every bench file in `bench_dir`.

    Every top-level `*.py` plus the `Makefile` -- deliberately wider than the
    `test_*.py`-minus-`test_all.py` rule that verification/ctrl/Makefile and
    verification/ctrl/test_all.py apply when selecting which modules to run,
    because an undeclared `hrbench.py` or an undeclared `Makefile` is unhashed
    just the same (self-test cases 3 and 4 pin this broad rule; do not narrow
    it to match the runners' module-selection rule). Non-recursive and
    extension-scoped on purpose -- see the module docstring.
    """
    found = set(bench_dir.glob("*.py"))
    makefile = bench_dir / "Makefile"
    if makefile.is_file():
        found.add(makefile)
    return sorted(str(p.relative_to(root)) for p in found)


def missing_declarations(present, declared):
    """Bench files that are on disk but not in the inventory, in `present` order."""
    return [path for path in present if path not in declared]


def run_check(repo_root, scan_root, inventory):
    """Run the check over `repo_root`; print the report; return the exit code.

    The directory set is discovered from disk -- `scan_root` itself plus each
    of its immediate subdirectories -- never from the inventory and never from
    a hardcoded list. Deriving it from the inventory would invert the check
    into a tautology in the one case that matters: drop a directory from
    attest/item9.json and its files would stop being scanned, invisible again.
    A hardcoded list would go stale on its own (issue #114 may remove
    verification/smoke/ entirely, which must be a no-op here).

    The check is one-way by design: it only ever asks "is this file on disk
    declared?", so an *extra* declaration is never a failure. That is why the
    declared-but-not-bench paths -- `flow/functional-verification-ctrl.json`
    and `verification/README.md` -- need no rule and get no scan: adding a
    `flow/*.json` glob would only sweep up non-bench files to special-case.
    A declared path with no file on disk stays step 4b's business
    (`klt signoff --attest 9 --check`).
    """
    declared = set(json.loads(inventory.read_text())["testbenches"])
    rel_inv = inventory.relative_to(repo_root)

    dirs = [scan_root]
    if scan_root.is_dir():
        dirs += sorted(p for p in scan_root.iterdir() if p.is_dir())
    per_dir = [(d.relative_to(repo_root), bench_files(d, repo_root)) for d in dirs]
    present = [f for _, files in per_dir for f in files]
    rel_scan = scan_root.relative_to(repo_root)
    ctrl_dir = scan_root / "ctrl"
    rel_ctrl = ctrl_dir.relative_to(repo_root)
    ctrl_files = next((files for rel, files in per_dir if rel == rel_ctrl), [])

    # Two loud-failure guards, so the check cannot start passing vacuously:
    # an empty scan means the benches moved or the scan root is wrong, and an
    # empty verification/ctrl/ specifically falsifies the item-9
    # controller-bench claim. An absent or empty sibling directory
    # (verification/smoke/, verification/hyperram_model/) is neither -- it
    # simply contributes no files.
    if not present:
        print(
            f"::error file={rel_scan}::no bench file found under {rel_scan}; the"
            " benches moved or this check is looking in the wrong place"
        )
        return 1
    if not ctrl_files:
        print(
            f"::error file={rel_ctrl}::no bench file found under {rel_ctrl}; the"
            " controller benches moved or were deleted, which the item-9"
            " declaration does not describe"
        )
        return 1

    missing = missing_declarations(present, declared)
    if missing:
        print(
            f"::error file={rel_inv}::{len(missing)} bench file(s) are not"
            f" declared in {rel_inv}, so they are unhashed, unattested, and"
            " would not show up as drift:"
        )
        for path in missing:
            print(f"  {path}")
        print(f'Add them to the "testbenches" array in {rel_inv}, then regenerate:')
        print(f"  {REGENERATE}")
        print("then the manifest hash and the signoff record (manifests/README.md).")
        return 1

    for rel, files in per_dir:
        print(f"ok {rel_inv} declares all {len(files)} file(s) under {rel}")
    return 0


def main():
    return run_check(REPO, SCAN_ROOT, INVENTORY)


# --- self-test ------------------------------------------------------------

failures = []


def record(ok, name, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"\n       {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def fixture(root, files):
    """A verification/ tree containing `files` (paths relative to `root`);
    returns the scan root. Only directories that hold a listed file are
    created, so a fixture without smoke/-shaped files is genuinely the
    #114 option-(a) shape: the directory does not exist at all."""
    scan_root = root / "verification"
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    return scan_root


#: What verification/ctrl looks like when every file is declared.
IN_SYNC = ["Makefile", "hrbench.py", "test_all.py", "test_row03_x.py"]


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)

        def check(case, files, declared_rel, *, expect):
            """Build a verification/ctrl-shaped fixture, run the two rule
            functions over it, and return (reported, expected, files the rule
            saw)."""
            root = tmp / case
            fixture(root, [f"verification/ctrl/{r}" for r in files])
            bench_dir = root / "verification" / "ctrl"
            declared = {f"verification/ctrl/{r}" for r in declared_rel}
            seen = bench_files(bench_dir, root)
            got = missing_declarations(seen, declared)
            want = [f"verification/ctrl/{r}" for r in expect]
            return got, want, seen

        def run_full(case, files, declared):
            """Build a multi-directory fixture, write an inventory declaring
            `declared`, run the whole check over it, and return (exit code,
            stdout)."""
            root = tmp / case
            scan_root = fixture(root, files)
            inv = root / "attest" / "item9.json"
            inv.parent.mkdir(parents=True)
            inv.write_text(json.dumps({"testbenches": sorted(declared)}))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = run_check(root, scan_root, inv)
            return code, buf.getvalue()

        # 1. The no-op case: everything on disk is declared.
        got, want, _ = check("in-sync", IN_SYNC, IN_SYNC, expect=[])
        record(got == want, "an inventory that declares every file reports nothing",
               f"got {got}")

        # 2. The hole this check exists to close (the issue #93 probe): a bench
        #    on disk that no list mentions.
        got, want, _ = check("undeclared-bench", IN_SYNC + ["test_probe_never_runs.py"],
                             IN_SYNC, expect=["test_probe_never_runs.py"])
        record(got == want, "an undeclared bench file is reported", f"got {got}")

        # 2b. Pins case 2 to the declared-set comparison rather than to anything
        #     incidental: the same directory passes once the probe is declared.
        got, want, _ = check("declared-bench", IN_SYNC + ["test_probe_never_runs.py"],
                             IN_SYNC + ["test_probe_never_runs.py"], expect=[])
        record(got == want,
               "...and the same directory passes once that bench is declared",
               f"got {got}")

        # 3. Not only test_*.py: an undeclared helper is unhashed just the same.
        got, want, _ = check("undeclared-helper", IN_SYNC + ["hrbench_extra.py"],
                             IN_SYNC, expect=["hrbench_extra.py"])
        record(got == want, "an undeclared non-test .py helper is reported",
               f"got {got}")

        # 4. An undeclared Makefile -- the file that selects which modules run.
        got, want, _ = check("undeclared-makefile", IN_SYNC,
                             [f for f in IN_SYNC if f != "Makefile"],
                             expect=["Makefile"])
        record(got == want, "an undeclared Makefile is reported", f"got {got}")

        # 5. Build output must neither trip the check nor be able to hide in it.
        artifacts = ["results.xml", "sim_build/sim.vvp", "sim_build_gl/sim.vvp",
                     "__pycache__/test_all.cpython-312.pyc"]
        got, want, seen = check("artifacts", IN_SYNC + artifacts, IN_SYNC, expect=[])
        record(got == want and all("sim_build" not in p and "__pycache__" not in p
                                   and not p.endswith(".xml") for p in seen),
               "cocotb/Icarus build output is ignored, not reported",
               f"saw {seen}, reported {got}")

        # 6. The reverse direction belongs to `klt signoff --attest 9 --check`,
        #    not here: a declared path with no file is not this check's failure.
        got, want, _ = check("declared-but-absent", IN_SYNC,
                             IN_SYNC + ["test_row99_deleted.py"], expect=[])
        record(got == want,
               "a declared path with no file on disk is left to step 4b",
               f"got {got}")

        # 7. A glob that matches nothing must fail loudly rather than vacuously
        #    pass -- otherwise moving the benches would disable this check.
        empty_root = tmp / "empty"
        empty_dir = fixture(empty_root, [])
        record(bench_files(empty_dir, empty_root) == [],
               "an empty bench directory yields no files (run_check errors on it)")

        # --- the multi-directory scan (issue #106) ---

        # 8. The same hole, one directory over: an undeclared bench under a
        #    smoke/-shaped directory now fails the whole check, by name.
        ctrl_decl = [f"verification/ctrl/{r}" for r in IN_SYNC]
        code, out = run_full(
            "smoke-undeclared",
            [f"verification/ctrl/{r}" for r in IN_SYNC]
            + ["verification/smoke/Makefile",
               "verification/smoke/test_probe_never_runs.py"],
            ctrl_decl + ["verification/smoke/Makefile"])
        record(code == 1 and "verification/smoke/test_probe_never_runs.py" in out,
               "an undeclared bench under verification/smoke/ fails the check and is named",
               f"exit {code}, out: {out.strip()}")

        # 9. Same hole under a hyperram_model/-shaped directory.
        code, out = run_full(
            "model-undeclared",
            [f"verification/ctrl/{r}" for r in IN_SYNC]
            + ["verification/hyperram_model/model.py",
               "verification/hyperram_model/test_probe_never_runs.py"],
            ctrl_decl + ["verification/hyperram_model/model.py"])
        record(code == 1 and "verification/hyperram_model/test_probe_never_runs.py" in out,
               "an undeclared bench under verification/hyperram_model/ fails the check and is named",
               f"exit {code}, out: {out.strip()}")

        # 10. A verification subdirectory that does not exist today is covered
        #     too, with no edit to the checker: the directory set comes from
        #     disk, not from a list.
        code, out = run_full(
            "new-subdir",
            [f"verification/ctrl/{r}" for r in IN_SYNC]
            + ["verification/pads/test_probe_never_runs.py"],
            ctrl_decl)
        record(code == 1 and "verification/pads/test_probe_never_runs.py" in out,
               "an undeclared bench in a brand-new subdirectory is caught with no checker edit",
               f"exit {code}, out: {out.strip()}")

        # 11. The #114 option-(a) shape: verification/smoke/ deleted outright.
        #     The scan simply stops finding it, which is not an error.
        code, out = run_full("smoke-absent",
                             [f"verification/ctrl/{r}" for r in IN_SYNC], ctrl_decl)
        record(code == 0 and "verification/smoke" not in out,
               "an absent verification/smoke/ is not an error (the #114 option-(a) shape)",
               f"exit {code}, out: {out.strip()}")

        # 12. Nor is an empty verification/smoke/.
        root = tmp / "smoke-empty"
        scan_root = fixture(root, [f"verification/ctrl/{r}" for r in IN_SYNC])
        (scan_root / "smoke").mkdir()
        inv = root / "attest" / "item9.json"
        inv.parent.mkdir(parents=True)
        inv.write_text(json.dumps({"testbenches": sorted(ctrl_decl)}))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = run_check(root, scan_root, inv)
        record(code == 0, "an empty verification/smoke/ is not an error",
               f"exit {code}, out: {buf.getvalue().strip()}")

        # 13. The full in-sync tree: success output names each scanned
        #     directory with its file count, and the declared-but-not-bench
        #     paths (verification/README.md, flow/functional-verification-ctrl.json)
        #     plus a declared path with no file on disk trip nothing -- the
        #     check is one-way.
        all_files = (
            ["verification/Makefile"]
            + [f"verification/ctrl/{r}" for r in IN_SYNC]
            + ["verification/hyperram_model/model.py",
               "verification/hyperram_model/test_model.py",
               "verification/smoke/Makefile",
               "verification/smoke/test_smoke_counter.py"]
        )
        all_declared = all_files + [
            "verification/README.md",
            "flow/functional-verification-ctrl.json",
            "verification/ctrl/test_row99_deleted.py",
        ]
        code, out = run_full("full-tree", all_files, all_declared)
        ok_lines = [l for l in out.splitlines() if l.startswith("ok ")]
        dirs_named = sorted(l.rsplit(" under ", 1)[1] for l in ok_lines)
        record(code == 0 and dirs_named == sorted(
                   ["verification", "verification/ctrl",
                    "verification/hyperram_model", "verification/smoke"]),
               "success names each scanned directory and its count; extra declarations trip nothing",
               f"exit {code}, ok lines: {ok_lines}")

        # 14. Build output stays invisible in every scanned directory, not
        #     just ctrl/ (case 5, one directory over).
        code, out = run_full(
            "artifacts-smoke",
            [f"verification/ctrl/{r}" for r in IN_SYNC]
            + ["verification/smoke/Makefile",
               "verification/smoke/results.xml",
               "verification/smoke/sim_build/sim.vvp",
               "verification/smoke/__pycache__/test_smoke_counter.cpython-312.pyc"],
            ctrl_decl + ["verification/smoke/Makefile"])
        record(code == 0 and "sim_build" not in out and "__pycache__" not in out
               and ".xml" not in out,
               "build output in a non-ctrl directory is ignored, not reported",
               f"exit {code}, out: {out.strip()}")

        # 15. Loud failure preserved, per directory: an emptied
        #     verification/ctrl/ fails even when a sibling has files.
        root = tmp / "ctrl-empty"
        scan_root = fixture(
            root,
            ["verification/smoke/Makefile", "verification/smoke/test_smoke_counter.py"])
        (scan_root / "ctrl").mkdir()
        inv = root / "attest" / "item9.json"
        inv.parent.mkdir(parents=True)
        inv.write_text(json.dumps({"testbenches": sorted([
            "verification/smoke/Makefile", "verification/smoke/test_smoke_counter.py"])}))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = run_check(root, scan_root, inv)
        record(code == 1 and "verification/ctrl" in buf.getvalue(),
               "an empty verification/ctrl/ fails loudly even with sibling benches",
               f"exit {code}, out: {buf.getvalue().strip()}")

        # 16. ...and a verification/ctrl/ that does not exist at all fails
        #     the same way.
        code, out = run_full(
            "ctrl-absent",
            ["verification/smoke/Makefile", "verification/smoke/test_smoke_counter.py"],
            ["verification/smoke/Makefile", "verification/smoke/test_smoke_counter.py"])
        record(code == 1 and "verification/ctrl" in out,
               "a missing verification/ctrl/ fails loudly",
               f"exit {code}, out: {out.strip()}")

        # 17. A scan that finds no files anywhere fails rather than passing
        #     vacuously (case 7's intent, at the full-check level).
        code, out = run_full("scan-empty", [], [])
        record(code == 1 and "no bench file found" in out,
               "a scan finding no files anywhere fails loudly",
               f"exit {code}, out: {out.strip()}")

    if failures:
        print(f"\n::error::{len(failures)} bench-coverage self-test(s) failed: "
              + "; ".join(failures))
        return 1
    print("\nbench-coverage check reports every undeclared bench checked here")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    if sys.argv[1:]:
        print(f"usage: {sys.argv[0]} [--self-test]", file=sys.stderr)
        sys.exit(2)
    sys.exit(main())
