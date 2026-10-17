#!/usr/bin/env python3
"""Fail if a relative markdown link in README.md points at a missing path.

External (scheme://, mailto:) and pure-anchor links are skipped; a
"#fragment" suffix on a relative link is stripped before the existence check.
"""
import re
import sys
from pathlib import Path

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def main(argv):
    files = [Path(a) for a in argv] or [Path("README.md")]
    bad = 0
    for md in files:
        for lineno, line in enumerate(md.read_text().splitlines(), 1):
            for target in LINK.findall(line):
                if re.match(r"^([a-z][a-z0-9+.-]*:|#)", target, re.I):
                    continue
                path = target.split("#", 1)[0]
                if path and not (md.parent / path).exists():
                    print(f"::error file={md},line={lineno}::broken relative link: {target}")
                    bad += 1
    if bad:
        return 1
    print(f"relative links OK in: {', '.join(str(f) for f in files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
