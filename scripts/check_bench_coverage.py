#!/usr/bin/env python3
"""Assert attest/item9.json declares every controller bench file on disk.

Why this exists (issue #93). `klt signoff --attest 9 --check` hashes the paths
the inventory lists, so a file the inventory *omits* is not drift -- it is
invisible. Before this check, a bench could be added under verification/ctrl/,
be absent from the item-9 "Testbenches shipped" declaration, never execute, and
CI would still be green: a false positive inside append-only evidence, which is
the most expensive failure this repo has (CLAUDE.md: "no claim without a
testbench").

verification/ctrl/Makefile and verification/ctrl/test_all.py now derive their
module lists from this same directory, so neither can go stale.
attest/item9.json stays an explicit declaration -- deriving it would defeat its
purpose as the record of what was shipped -- so it is the one list that can
drift, and this is the check that stops it.

What is asserted: every top-level `*.py` and the `Makefile` under
verification/ctrl/ appears in attest/item9.json's `testbenches` array. The glob
is deliberately non-recursive and extension-scoped, so cocotb/Icarus build
output (`sim_build*/`, `__pycache__/`, `results.xml`) cannot reach it. The
reverse direction -- a listed path that does not exist -- is already caught by
`klt signoff --attest 9 --check`, and is not re-checked here.

  scripts/check_bench_coverage.py              check the repo (CI step 4c)
  scripts/check_bench_coverage.py --self-test   check this checker, on fixtures

The self-test is here because this file is now the only thing standing between
an undeclared bench and a green CI, so "it catches the hole" is a claim that
needs its own testbench. It drives the two functions below over temporary
directories; it touches nothing in the repo and needs no klt, cocotb or PDK.

Exit 0 when the inventory covers the directory, 1 otherwise. Needs nothing but
python3, so both modes run on the CI runner.
"""

import json
import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
INVENTORY = REPO / "attest" / "item9.json"
BENCH_DIR = REPO / "verification" / "ctrl"
REGENERATE = (
    "scripts/klt.sh signoff --attest 9 --inventory attest/item9.json"
    " -o evidence/item9.json"
)


def bench_files(bench_dir, root):
    """Paths, relative to `root`, of every controller bench file in `bench_dir`.

    The one controller-bench rule, the same one verification/ctrl/Makefile and
    verification/ctrl/test_all.py apply: top-level `*.py` plus the `Makefile`.
    Non-recursive and extension-scoped on purpose -- see the module docstring.
    """
    found = set(bench_dir.glob("*.py"))
    makefile = bench_dir / "Makefile"
    if makefile.is_file():
        found.add(makefile)
    return sorted(str(p.relative_to(root)) for p in found)


def missing_declarations(present, declared):
    """Bench files that are on disk but not in the inventory, in `present` order."""
    return [path for path in present if path not in declared]


def main():
    declared = set(json.loads(INVENTORY.read_text())["testbenches"])
    present = bench_files(BENCH_DIR, REPO)
    rel_inv = INVENTORY.relative_to(REPO)
    rel_dir = BENCH_DIR.relative_to(REPO)

    if not present:
        print(
            f"::error file={rel_dir}::no bench file found; the benches moved or"
            " this check is looking in the wrong place"
        )
        return 1

    missing = missing_declarations(present, declared)
    if missing:
        print(
            f"::error file={rel_inv}::{len(missing)} controller bench file(s) are"
            f" not declared in {rel_inv}, so they are unhashed, unattested, and"
            " would not show up as drift:"
        )
        for path in missing:
            print(f"  {path}")
        print(f'Add them to the "testbenches" array in {rel_inv}, then regenerate:')
        print(f"  {REGENERATE}")
        print("then the manifest hash and the signoff record (manifests/README.md).")
        return 1

    print(f"ok {rel_inv} declares all {len(present)} file(s) under {rel_dir}")
    return 0


# --- self-test ------------------------------------------------------------

failures = []


def record(ok, name, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"\n       {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def fixture(root, files):
    """A verification/ctrl-shaped directory containing `files`; returns it."""
    bench_dir = root / "verification" / "ctrl"
    bench_dir.mkdir(parents=True)
    for rel in files:
        path = bench_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    return bench_dir


#: What verification/ctrl looks like when every file is declared.
IN_SYNC = ["Makefile", "hrbench.py", "test_all.py", "test_row03_x.py"]


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)

        def check(case, files, declared_rel, *, expect):
            """Build a fixture, run the check over it, and return
            (reported, expected, files the rule saw)."""
            root = tmp / case
            bench_dir = fixture(root, files)
            declared = {f"verification/ctrl/{r}" for r in declared_rel}
            seen = bench_files(bench_dir, root)
            got = missing_declarations(seen, declared)
            want = [f"verification/ctrl/{r}" for r in expect]
            return got, want, seen

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
               "an empty bench directory yields no files (main() errors on it)")

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
