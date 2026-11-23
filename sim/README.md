# sim

Per-study simulation artifacts. Each study keeps its raw tool response under
`<study>/records/`, committed verbatim, with any derived record beside it:

- `hyperram/` — the controller netlist, its synthesis stat report, the
  gate-level functional-verification report, the SDF-annotated post-route
  bench report (item 7), and the post-route CK/CA pin-waveform trace record
  (`records/CK-TRACE.md`, issue #187).
- `delay-chain/` — the RWDS delay-chain ngspice campaign across the
  decision-0004 corners (spec open question (b); `make delay-chain`).
