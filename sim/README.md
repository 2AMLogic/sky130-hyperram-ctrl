# sim

Per-study simulation artifacts. Each study keeps its raw tool response under
`<study>/records/`, committed verbatim, with any derived record beside it:

- `smoke/` — toolchain bring-up flow (`make smoke`; module is NOT the design).
- `hyperram/` — the controller netlist, its synthesis stat report and the
  gate-level functional-verification report.
- `delay-chain/` — the RWDS delay-chain ngspice campaign across the
  decision-0004 corners (spec open question (b); `make delay-chain`).
