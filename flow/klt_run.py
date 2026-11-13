#!/usr/bin/env python3
"""The one way a flow runner invokes klt: through scripts/klt.sh.

scripts/klt.sh holds the only klt version pin and the only rule for choosing
which klt binary runs, so a runner must never execute a bare `klt` off $PATH --
that resolves to whatever klt the host happens to provide, and the version then
lands unflagged in a committed record's provenance.

Not a command-line entry point; import it from a sibling runner in flow/.
`attest/item1.json` and `scripts/check_ci.sh` run those runners with
`python3 -I`, which keeps the script's own directory off sys.path, so add it
from __file__ before importing:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from klt_run import klt, klt_json
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KLT = REPO / "scripts/klt.sh"


def klt(*args, **kwargs):
    """Run the pinned klt with args and return the CompletedProcess, uninspected.

    For callers that read the exit status themselves (`--check` modes). kwargs
    go to subprocess.run (`env=` for the PDK the layout commands need).
    """
    return subprocess.run([str(KLT), *args], capture_output=True, text=True, **kwargs)


def klt_json(*args, **kwargs):
    """Run the pinned klt with --format json; return the parsed response or exit.

    Exits non-zero on a non-JSON stdout, a non-zero exit status, or an "error"
    key in the response, quoting what klt said.
    """
    proc = klt(*args, "--format", "json", **kwargs)
    try:
        doc = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"FATAL: klt {args[0]} gave no JSON (rc={proc.returncode}): {proc.stderr.strip()[:500]}")
    if proc.returncode != 0 or "error" in doc:
        sys.exit(f"FATAL: klt {args[0]} failed: {json.dumps(doc.get('error', doc))[:800]}")
    return doc
