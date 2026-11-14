"""Aggregates every controller bench into one cocotb module, because a
`klt functional-verification` request names a single testbench module
(flow/functional-verification-ctrl.json). `make -C verification/ctrl` runs the
modules separately; both run the same tests.

The bench list is not written out here. It is derived from this directory by
the one controller-bench rule, applied identically in the three places that
need it (issue #93): every `test_*.py` beside this file except this file is a
bench module. verification/ctrl/Makefile globs with the same rule, and
scripts/check_bench_coverage.py asserts attest/item9.json declares every file
the rule can see -- so the module list `make` runs and the module list the
committed signoff evidence runs cannot drift apart, which is the failure that
would put a bench in the record without ever executing it.

Each bench module is imported and its public names re-exported here, in sorted
order, exactly as the `from <bench> import *` lines this replaces did: cocotb
discovers tests by scanning this module's own globals for `cocotb.Test`
objects (cocotb 2.0.1, regression.py `discover_tests`), so they have to land
here. A helper name defined in two benches resolves to the later module's, as
it did with the star imports -- harmless, because a bench function looks up
globals in the module that defines it, not in this one.
"""

import importlib
import pathlib

_HERE = pathlib.Path(__file__).resolve().parent

#: Every controller bench module, by the rule in this module's docstring.
BENCH_MODULES = sorted(
    p.stem for p in _HERE.glob("test_*.py") if p.name != pathlib.Path(__file__).name
)

if not BENCH_MODULES:
    raise RuntimeError(
        f"no controller bench matched test_*.py in {_HERE}: "
        "the glob or the benches moved"
    )

for _module_name in BENCH_MODULES:
    _module = importlib.import_module(_module_name)
    _exported = getattr(_module, "__all__", None)
    if _exported is None:
        _exported = [_name for _name in vars(_module) if not _name.startswith("_")]
    globals().update({_name: getattr(_module, _name) for _name in _exported})
