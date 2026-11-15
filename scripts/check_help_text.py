#!/usr/bin/env python3
"""Assert the --help output of the shell driver scripts is comment text only.

Why this exists (issue #124). sim/pad-sta/run-opensta.sh and
scripts/setup-env.sh print their leading comment block as --help through a
`sed` range whose upper bound was a hardcoded line number: the number of the
script's own `esac`, not of the header's end. Every edit above that line --
adding a flag arm, re-flowing a comment -- silently shifted what --help
printed, and twice it did: run-opensta.sh's bound has to be hand-bumped on
every arg-loop change (PR #123), and setup-env.sh's had drifted so far it
ended on a dangling `#` while silently dropping the pin-maintenance note the
header carries (the one line a reader running --help before provisioning most
needs). Both bounds are now pattern-anchored (`sed '1d;/^[^#]/,$d'`), so the
fix cannot reintroduce the coupling it removes -- but nothing stopped a
hardcoded range from coming back, silently, in either script.

What is asserted, per script: `--help` exits 0, prints at least one line
ending in a `# Usage:` line, and prints NO executable shell -- every output
line is blank or a comment. That is the invariant, not a snapshot: it is
stable across header edits, yet fails closed the moment any hardcoded bound
overshoots into the `set -`, the arg loop or the `case` scaffolding again,
because those are non-comment lines.

  scripts/check_help_text.py --self-test
      check this checker, on fixtures (run first, in CI, before the real scan)
  scripts/check_help_text.py <script.sh> [<script.sh> ...]
      check the named scripts (check_ci.sh step 2b passes the two drivers)

The self-test is here because this file is the only thing standing between a
reintroduced hardcoded bound and a silently truncated help: "it catches the
hole" is a claim that needs its own testbench. It drives the same functions
over fixture strings and recorded exit codes; it runs no repo script and
needs no klt, PDK, yosys or iverilog -- both real scripts exit from their
argument loop before touching a tool, so the real scan is bash + sed only.

Exit 0 when every named script's help is clean, 1 otherwise.
"""

import pathlib
import subprocess
import sys

DRIVER_SCRIPTS = [
    "scripts/setup-env.sh",
    "sim/pad-sta/run-opensta.sh",
]


def help_problems(help_text, rc):
    """Problems with one script's --help output (empty list = clean)."""
    problems = []
    if rc != 0:
        problems.append(f"--help exited {rc}, expected 0")
    lines = help_text.splitlines()
    if not any(line.strip() for line in lines):
        problems.append("--help printed nothing")
    for n, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            problems.append(
                f"line {n} of --help is shell source, not a comment: {line!r}"
            )
    if not any(line.startswith("# Usage:") for line in lines):
        problems.append("--help has no '# Usage:' line")
    return problems


def check_script(path):
    """Run `bash <path> --help` and return (problems, rc, tail-of-stdout)."""
    proc = subprocess.run(
        ["bash", str(path), "--help"],
        capture_output=True,
        text=True,
    )
    problems = help_problems(proc.stdout, proc.returncode)
    if proc.stderr.strip():
        problems.append(f"--help wrote to stderr: {proc.stderr.strip()[:200]}")
    return problems, proc.returncode, proc.stdout


def self_test():
    """Fixture cases: each direction of the assertion is exercised."""
    failures = []

    def record(ok, what, detail=""):
        if not ok:
            failures.append(f"{what} ({detail})")

    good_header = (
        "#!/usr/bin/env bash\n"
        "#\n"
        "# driver.sh -- do a thing.\n"
        "#\n"
        "# Environment: FOO must be set.\n"
        "#\n"
        "# Usage: driver.sh [--foo BAR]\n"
        "set -euo pipefail\n"
        "\n"
        "while [ $# -gt 0 ]; do\n"
        '  case "$1" in\n'
        "    -h|--help) sed '1d;/^[^#]/,$d' \"${BASH_SOURCE[0]}\"; exit 0 ;;\n"
        '    *) echo "unknown option: $1" >&2; exit 1 ;;\n'
        "  esac\n"
        "  shift\n"
        "done\n"
    )
    header_text = good_header[good_header.index("#\n")
                               : good_header.index("set -euo pipefail")]
    record(
        help_problems(header_text, 0) == [],
        "a comment-block-only help is clean",
        f"got {help_problems(header_text, 0)}",
    )

    # setup-env.sh's pattern-anchored help ends on the blank line before
    # `set -uo pipefail`: blank lines are not shell source, so this is clean.
    trailing_blank = header_text + "\n"
    record(
        help_problems(trailing_blank, 0) == [],
        "a trailing blank line is tolerated",
        f"got {help_problems(trailing_blank, 0)}",
    )

    # The overshoot that motivated the issue: bound past `set -euo pipefail`.
    overshoot = header_text + "set -euo pipefail\n\n"
    record(
        any("shell source" in p for p in help_problems(overshoot, 0)),
        "a `set -` line in help fails",
        f"got {help_problems(overshoot, 0)}",
    )

    # The harder form: bound into the arg loop itself (run-opensta.sh on main
    # before the fix ended mid-case, with the arms printed as code).
    mid_case = (
        "# Usage: driver.sh [--foo BAR]\n"
        "\n"
        "while [ $# -gt 0 ]; do\n"
        '  case "$1" in\n'
        "    -h|--help) sed -n '2,53p' \"${BASH_SOURCE[0]}\"; exit 0 ;;\n"
        '    *) echo "unknown option: $1" >&2; exit 1 ;;\n'
    )
    record(
        any("shell source" in p for p in help_problems(mid_case, 0)),
        "arg-loop scaffolding in help fails",
        f"got {help_problems(mid_case, 0)}",
    )

    record(
        help_problems("", 0) != [],
        "empty help fails",
    )
    nonzero_case = "# Usage: x\n"
    record(
        any("exited 1" in p for p in help_problems(nonzero_case, 1)),
        "a nonzero --help exit fails",
        f"got {help_problems(nonzero_case, 1)}",
    )
    no_usage = "# driver.sh -- do a thing.\n#\n# See the README.\n"
    record(
        any("Usage" in p for p in help_problems(no_usage, 0)),
        "help without a '# Usage:' line fails",
        f"got {help_problems(no_usage, 0)}",
    )

    if failures:
        print(f"\n::error::{len(failures)} help-text self-test(s) failed: "
              + "; ".join(failures))
        return 1
    print("\nhelp-text check reports every reintroduced hardcoded bound checked here")
    return 0


def main(argv):
    if not argv:
        print(f"usage: {argv0()} <script.sh> [<script.sh> ...] | --self-test",
              file=sys.stderr)
        return 2
    any_problem = False
    for arg in argv:
        path = pathlib.Path(arg)
        problems, rc, out = check_script(path)
        if problems:
            any_problem = True
            print(f"::error file={path}::--help is not comment-only "
                  f"(exit {rc}): {'; '.join(problems)}")
            print(f"FAIL {path} -- last lines of help output:")
            for line in out.splitlines()[-6:]:
                print(f"  | {line}")
        else:
            n_lines = len(out.splitlines())
            print(f"ok {path}: --help is {n_lines} comment lines, no shell source")
    return 1 if any_problem else 0


def argv0():
    return pathlib.Path(sys.argv[0]).name


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        sys.exit(self_test())
    sys.exit(main(sys.argv[1:]))
