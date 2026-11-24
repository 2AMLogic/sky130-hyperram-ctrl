# 0009 Pad-STA tool support at klt 0.9.2 is recorded as a dated note

Status: operator-ruled (rjwalters, `fleet:decide` round 20261121-r19, question
q296, 2026-11-23, option `annotate`). Issue #182; follows PR #175 (klt pin
0.8.0 → 0.9.2).

## Decision

`spec/target-spec.md` keeps the original 2026-11-14 finding verbatim ("The
pinned `klt` 0.8.0 cannot drive this experiment…") and carries a dated note
directly beside it: as of `klt` 0.9.2 (2026-11-23), `macros[]` is honoured and
the pad-STA request runs to completion. The original sentence is historical
context for why the evidence record was produced with the committed OpenROAD
session driver, which remains the record's reproduction path.

Evidence: `sim/pad-sta/records/klt-0.9.2-attempt/response-probe4-default.json`
(status `ok`).

## What this does not change

- The probe used a fast pad library outside the ratified 3.3 V ±10 % window
  (decision 0002), so the fast/min-corner coverage gap is **not** closed by it.
  Row 12's min/max spread still requires the ngspice characterization.
- No ratified requirement is changed or relaxed. Spec ratification stays with
  #2.
