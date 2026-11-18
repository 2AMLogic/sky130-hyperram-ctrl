#!/usr/bin/env python3
"""Structurally assert ensure_pdk never points PDK_ROOT into the repo.

Why this exists (issue #155). `ensure_pdk` in
`scripts/fleet-regen-layout.sh` fetches the pinned sky130A PDK OUTSIDE the
repository root (issue #142): a PDK under `${REPO_ROOT}` makes klt record
the liberty deck as {"path": ".fleet-pdk/...", "scope": "repo"} in the
evidence it writes -- a repo-scoped path into a tree .gitignore deliberately
excludes, unresolvable in every checkout. Outside the repo the same field
records scope "external", exactly as the baked /opt/pdk path has always
recorded.

No bench can catch the regression: a reverted `export PDK_ROOT=` surfaces
only when a fleet job runs the regeneration end to end (~26 min later), by
which time the wrong evidence is already committed. This is the structural
guard instead, a pure read of the committed script in the step 3c style,
asserting every assignment to PDK_ROOT inside `ensure_pdk` -- an
`export PDK_ROOT=`, a `declare -x`/`readonly`/`typeset -x`, a plain
`PDK_ROOT=`, or a bare `export PDK_ROOT` re-exporting one -- has a target

  1. the literal /opt/pdk (the image's baked PDK root), or
  2. the caller-supplied ${PDK_ROOT} (verified in place before any fetch),
     or
  3. rooted at ${TMPDIR:-/var/tmp} -- directly, or through a local variable
     assigned from it (`shared_root`, `staging` in the current script),

and never anything containing ${REPO_ROOT}. Any other target fails closed,
as does a missing `ensure_pdk`, a body with no PDK_ROOT assignment at all,
or a body whose braces do not close on a bare `}` line (a stray brace
mid-line would truncate the body and hide the later targets); heredoc
bodies inside the function are skipped as string literals, so their braces
are data -- whatever quoting the delimiter carries (`<<'EOF'`, `<< \\EOF`,
`<<E\\OF`: bash matches the terminator on the unquoted word) -- and a
heredoc that never terminates fails closed: a rename must not silently
pass.

  scripts/check_pdk_root.py               check the committed script (CI)
  scripts/check_pdk_root.py --self-test   check this checker, on fixtures

Needs no PDK, no klt, no network, so it runs on every PR from
`scripts/check_ci.sh` (step 3d). Exit 0 when the invariant holds, 1
otherwise.
"""

import contextlib
import io
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "fleet-regen-layout.sh"
FUNC = "ensure_pdk"

BAKED = "/opt/pdk"                  # the image's baked PDK root
TMP_ROOT = "${TMPDIR:-/var/tmp}"    # the sanctioned scratch root (issue #142)
REPO_VAR = "${REPO_ROOT}"

# Any declaration keyword that can introduce a PDK_ROOT assignment: the
# judged target is the assignment itself, so a plain `PDK_ROOT=` later
# re-exported bare (`export PDK_ROOT`, no `=`) cannot slip past, and
# neither can `declare -x`, `readonly` or `typeset -x` spellings.
TARGET_RE = re.compile(
    r"^\s*(?:(?:export|local|readonly)\s+|declare\s+(?:-\w+\s+)*|typeset\s+(?:-\w+\s+)*)?"
    r"PDK_ROOT=(.+?)\s*$"
)
ASSIGN_RE = re.compile(r"^\s*([A-Za-z_]\w*)=(.+?)\s*$")
VARREF_RE = re.compile(r"^\$\{([A-Za-z_]\w*)\}$")
# A `<<`/`<<-` heredoc introduction: quoted, escaped, or bare delimiter,
# optional whitespace before it. A backslash in the delimiter (`<< \EOF`,
# `<<E\OF`, `<<-\EOF`) is a bash quoting character, so the word is captured
# with escapes and unescaped below -- bash matches the terminator line on
# the unquoted word. The lookbehind keeps `<<<` (a here-string, whose text
# sits on the same line) from matching as a heredoc.
HEREDOC_RE = re.compile(r"(?<!<)<<-?\s*['\"]?((?:\\?\w+)+)['\"]?")

failures = []


def function_body(text, name):
    """The body of `name() { ... }`, or None when absent or unbalanced.

    Brace counting skips comment lines (the function's rationale comment
    quotes JSON braces) and pauses across heredoc bodies (issue #158): a
    `<<`/`<<-` heredoc is a string literal, so its braces are data -- a
    bare `}` inside one must not truncate the body and hide every later
    target. The delimiter may be quoted or backslash-escaped (`<<'EOF'`,
    `<< \\EOF`, `<<E\\OF`, issue #162); the escape/quote characters are not
    part of the word, so the terminator is matched on the unquoted word.
    Counting resumes after the delimiter line (at column 0, or
    tab-indented for `<<-`); a heredoc that never terminates fails closed,
    since the function's real `}` would otherwise be swallowed as heredoc
    content. Every ${...} expansion outside a heredoc carries balanced
    braces on one line, so the closing `}` at column 0 is where depth
    returns to 0. The body fails closed (None) unless that terminator is
    exactly `}`: an ordinary line carrying a stray `}` (a quoting typo, a
    `tr -d '}'`) would otherwise truncate the body early and hide every
    later target behind the one allowed export the truncation leaves
    behind.
    """
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if not re.match(rf"{re.escape(name)}\s*\(\)\s*\{{", ln):
            continue
        depth = 0
        pending = []  # open heredoc terminators, in body order
        for j in range(i, len(lines)):
            line = lines[j]
            if pending:
                dash, delimiter = pending[0]
                candidate = line.lstrip("\t") if dash else line
                if candidate == delimiter:
                    pending.pop(0)
                continue
            if not line.lstrip().startswith("#"):
                depth += line.count("{") - line.count("}")
                for m in HEREDOC_RE.finditer(line):
                    pending.append((m.group(0).startswith("<<-"), m.group(1).replace("\\", "")))
            if j > i and depth <= 0:
                if line.rstrip() == "}":
                    return "\n".join(lines[i + 1 : j])
                return None
        return None
    return None


def unquote(raw):
    """Strip a trailing line-continuation and one layer of outer quotes."""
    v = raw.strip()
    v = re.sub(r"\\\s*$", "", v).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1].strip()
    return v


def classify(value):
    """None when a concrete target is allowed; a reason string when not."""
    if REPO_VAR in value:
        return f"target contains {REPO_VAR} (repo-scoped PDK; the issue #142 regression)"
    if value.startswith(BAKED):
        return None
    if TMP_ROOT in value:
        return None
    if re.match(r"^\$\{PDK_ROOT[}:]", value):
        return None
    return f"target is not {BAKED}, ${{PDK_ROOT}}, or rooted at {TMP_ROOT}"


def resolve(value, variables, depth=0):
    """Follow plain ${var} references through local assignments; None if
    the reference resolves through no assignment in the body."""
    if depth > 8:
        return None
    m = VARREF_RE.match(value)
    if not m:
        return value
    rhs = variables.get(m.group(1))
    if rhs is None:
        return None
    return resolve(rhs, variables, depth + 1)


def judge(target, variables):
    """Classify one PDK_ROOT assignment target, resolving ${var} targets."""
    if VARREF_RE.match(target):
        resolved = resolve(target, variables)
        if resolved is None:
            return f"target {target} resolves through no local assignment in {FUNC}"
        return classify(resolved)
    return classify(target)


def check_body(body):
    """[problem, ...] for an `ensure_pdk` body; empty means it holds.

    Every assignment to PDK_ROOT is a target, whatever keyword introduces
    it: an `export PDK_ROOT=`, a `declare -x`/`readonly`/`typeset -x`, a
    plain `PDK_ROOT=`, or a bare `export PDK_ROOT` re-exporting a plain
    assignment (the assignment itself is the judged target).
    """
    variables = {}
    targets = []
    for ln in body.splitlines():
        stripped = ln.strip()
        if stripped.startswith("#"):
            continue
        m = TARGET_RE.match(ln)
        if m:
            value = unquote(m.group(1))
            targets.append(value)
            variables["PDK_ROOT"] = value
            continue
        m = ASSIGN_RE.match(ln)
        if m:
            variables[m.group(1)] = unquote(m.group(2))
    if not targets:
        return [f"{FUNC} contains no assignment to PDK_ROOT (a rename must not silently pass)"]
    return [
        f"PDK_ROOT={target}: {reason}"
        for target in targets
        if (reason := judge(target, variables)) is not None
    ]


def check_text(text, label):
    """0 when every export target in the text's ensure_pdk is allowed."""
    body = function_body(text, FUNC)
    if body is None:
        print(f"FAIL: {label}: no balanced {FUNC}() function found (a rename or a stray brace must not silently pass)", file=sys.stderr)
        return 1
    problems = check_body(body)
    if problems:
        for p in problems:
            print(f"FAIL: {label}: {p}", file=sys.stderr)
        return 1
    print(f"ok {label}: every PDK_ROOT assignment target in {FUNC} is {BAKED}, ${{PDK_ROOT}}, or {TMP_ROOT}-rooted")
    return 0


def run_check(path):
    try:
        text = pathlib.Path(path).read_text()
    except OSError as exc:
        print(f"FAIL: {path}: {exc}", file=sys.stderr)
        return 1
    return check_text(text, str(path))


def check_fixture(name, text, expect_ok):
    """Run the checker over a fixture script; the fixture must pass exactly
    when `expect_ok`. Returns (behaved_as_required, checker output)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = check_text(text, f"fixture:{name}")
    return rc == (0 if expect_ok else 1), buf.getvalue().strip()


GOOD_STAGING_EXPORT = 'export PDK_ROOT="${staging}"'
GOOD_SHARED_LINE = f'shared_root="{TMP_ROOT}/fleet-pdk-${{PDK_COMMIT}}"'

GOOD_FIXTURE = f"""\
#!/usr/bin/env bash
# Provision the pinned PDK; fetch outside the repo root (issue #142).
{FUNC}() {{
  if [ -z "${{PDK_ROOT:-}}" ] && [ -d {BAKED}/sky130A ]; then
    export PDK_ROOT={BAKED}
    return 0
  fi
  if [ -n "${{PDK_ROOT:-}}" ]; then
    return 0
  fi
  local shared_root staging
  {GOOD_SHARED_LINE}
  if pdk_ok "${{shared_root}}"; then
    export PDK_ROOT="${{shared_root}}"
    return 0
  fi
  staging="$(mktemp -d "{TMP_ROOT}/fleet-pdk.XXXXXXXX")" \\
    || exit 4
  {GOOD_STAGING_EXPORT}
}}
"""


def fixture_with(staging_export=GOOD_STAGING_EXPORT, shared_line=GOOD_SHARED_LINE):
    """The good shape with one line swapped for a regression."""
    text = GOOD_FIXTURE.replace(GOOD_STAGING_EXPORT, staging_export)
    return text.replace(GOOD_SHARED_LINE, shared_line)


def heredoc_fixture(open_line, content, repo_export=True):
    """The good shape with a heredoc spliced in after `local shared_root
    staging` (issue #158's mutation), and -- unless repo_export is False --
    the staging export swapped for a repo-rooted one. The heredoc body is
    literal text, so for `<<-` a content line may carry leading tabs."""
    text = GOOD_FIXTURE.replace(
        "  local shared_root staging",
        "  local shared_root staging\n  " + open_line + "\n" + content,
    )
    if repo_export:
        text = text.replace(GOOD_STAGING_EXPORT, f'export PDK_ROOT="{REPO_VAR}/.fleet-pdk"')
    return text


def record(ok, msg, detail=""):
    if ok:
        print(f"ok {msg}")
    else:
        print(f"FAIL {msg}\n{detail}")
        failures.append(msg)


def self_test():
    ok, out = check_fixture("good shape", GOOD_FIXTURE, True)
    record(ok, "fixture: baked /opt/pdk + caller ${PDK_ROOT} + ${TMPDIR:-/var/tmp} locals pass", out)

    ok, out = check_fixture(
        "repo-rooted export",
        fixture_with(staging_export=f'export PDK_ROOT="{REPO_VAR}/.fleet-pdk"'),
        False,
    )
    record(ok, f"fixture: export PDK_ROOT=\"{REPO_VAR}/.fleet-pdk\" fails", out)

    ok, out = check_fixture(
        "repo-rooted via local",
        fixture_with(shared_line=f'shared_root="{REPO_VAR}/.fleet-pdk-${{PDK_COMMIT}}"'),
        False,
    )
    record(ok, f"fixture: a local resolving into {REPO_VAR} fails", out)

    ok, out = check_fixture(
        "unrecognized root",
        fixture_with(staging_export='export PDK_ROOT="${HOME}/pdk"'),
        False,
    )
    record(ok, "fixture: a target outside the allowlist fails closed", out)

    ok, out = check_fixture(
        "unresolvable var",
        fixture_with(staging_export='export PDK_ROOT="${nowhere}/pdk"'),
        False,
    )
    record(ok, "fixture: a target resolving through no assignment fails closed", out)

    ok, out = check_fixture(
        "no ensure_pdk",
        "#!/usr/bin/env bash\nother_pdk() {\n  export PDK_ROOT=/opt/pdk\n}\n",
        False,
    )
    record(ok, "fixture: no ensure_pdk function fails closed", out)

    ok, out = check_fixture(
        "no export",
        f"#!/usr/bin/env bash\n{FUNC}() {{\n  log \"nothing to do\"\n}}\n",
        False,
    )
    record(ok, "fixture: ensure_pdk without any PDK_ROOT assignment fails closed", out)

    ok, out = check_fixture(
        "assign-then-bare-export",
        fixture_with(staging_export=f'PDK_ROOT="{REPO_VAR}/.fleet-pdk"\n  export PDK_ROOT'),
        False,
    )
    record(ok, f"fixture: a plain PDK_ROOT= assignment + bare export PDK_ROOT fails", out)

    ok, out = check_fixture(
        "declare -x",
        fixture_with(staging_export=f'declare -x PDK_ROOT="{REPO_VAR}/.fleet-pdk"'),
        False,
    )
    record(ok, f"fixture: declare -x PDK_ROOT=\"{REPO_VAR}/.fleet-pdk\" fails", out)

    truncated = GOOD_FIXTURE.replace(
        "  local shared_root staging",
        "  local shared_root staging\n  junk=\"$(echo stray | tr -d '}')\"",
    ).replace(GOOD_STAGING_EXPORT, f'export PDK_ROOT="{REPO_VAR}/.fleet-pdk"')
    ok, out = check_fixture("stray-brace truncation", truncated, False)
    record(ok, "fixture: a stray } truncating the body hides no repo-rooted export", out)

    # Issue #158: a heredoc body is a string literal, not shell; its braces
    # are data and must never move the depth that finds the function's `}`.
    # Each repo-rooted-export case must fail *with the ${REPO_ROOT} message*,
    # proving the export was judged rather than the body merely truncated.
    ok, out = check_fixture(
        "balanced heredoc",
        heredoc_fixture("cat <<'EOF'", "{\n}\nEOF"),
        False,
    )
    record(ok and REPO_VAR in out, "fixture: a balanced {/} heredoc still fails on the repo-rooted export", out)

    ok, out = check_fixture(
        "unbalanced heredoc, quoted",
        heredoc_fixture("cat <<'EOF'", "}\nEOF"),
        False,
    )
    record(ok and REPO_VAR in out, "fixture: a bare } in a <<'EOF' heredoc truncates nothing; the repo-rooted export fails", out)

    ok, out = check_fixture(
        "unbalanced heredoc, unquoted",
        heredoc_fixture("cat <<EOF", "}\nEOF"),
        False,
    )
    record(ok and REPO_VAR in out, "fixture: a bare } in an unquoted-<<EOF heredoc truncates nothing; the repo-rooted export fails", out)

    ok, out = check_fixture(
        "dash heredoc, tab-indented",
        heredoc_fixture("cat <<-EOF", "\t}\n\tEOF"),
        False,
    )
    record(ok and REPO_VAR in out, "fixture: <<- with a tab-indented terminator still judges the repo-rooted export", out)

    # Issue #162: a backslash in the delimiter (`<< \EOF`, `<<E\OF`) is a
    # bash quoting character, not part of the word; bash matches the
    # terminator line on the unquoted word, so the checker must too.
    ok, out = check_fixture(
        "unbalanced heredoc, escaped delimiter",
        heredoc_fixture("cat << \\EOF", "}\nEOF"),
        False,
    )
    record(ok and REPO_VAR in out, "fixture: a bare } in a << \\EOF heredoc truncates nothing; the repo-rooted export fails", out)

    ok, out = check_fixture(
        "escaped delimiter inside word",
        heredoc_fixture("cat <<E\\OF", "}\nEOF"),
        False,
    )
    record(ok and REPO_VAR in out, "fixture: a bare } in a <<E\\OF heredoc truncates nothing; the repo-rooted export fails", out)

    ok, out = check_fixture(
        "dash heredoc, escaped delimiter",
        heredoc_fixture("cat <<-\\EOF", "\t}\n\tEOF"),
        False,
    )
    record(ok and REPO_VAR in out, "fixture: <<-\\EOF with a tab-indented terminator still judges the repo-rooted export", out)

    # The issue's false-positive probes must stay fail-closed: a `<<` that
    # is not a heredoc introduction must never let a bad shape pass.
    for probe_line in ("x=$(( 1 << 2 ))", 'log "a << b"', "cat <<EOF.1"):
        ok, out = check_fixture(
            f"probe {probe_line!r}",
            heredoc_fixture(probe_line, "no bare terminator follows", repo_export=False),
            False,
        )
        record(ok, f"fixture: {probe_line} is not a heredoc introduction and still fails closed", out)

    ok, out = check_fixture(
        "unterminated heredoc",
        heredoc_fixture("cat <<'EOF'", "the body keeps going\nand never terminates", repo_export=False),
        False,
    )
    record(ok, "fixture: a heredoc that never terminates fails closed", out)

    if failures:
        print(f"\n{len(failures)} self-test case(s) failed: {failures}")
        return 1
    print("\nPDK-root checker self-test: all fixtures behave as required")
    return 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    return run_check(SCRIPT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
