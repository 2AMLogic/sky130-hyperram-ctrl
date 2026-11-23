# Post-route CK / command-address pin-waveform trace (SDF-annotated, typ)

Issue #187 (item 7 follow-up): locate the first divergence between the routed
controller and the expected six-byte CA transfer at 50 MHz, and correct the CK
launch path **if** the waveform establishes a design defect. The waveform does
not: this record traces the annotated pins, refutes the proposed ICG / tap-chain
cause, and locates the divergence the 0/43 annotated suite actually reports --
in the bench's pad-sample position, not in the design. The design, the bench,
the model and the spec rows are all left unchanged.

- Reproduce: `make ck-trace` (annotated) and `make ck-trace-gl0` (zero-delay
  stand-ins, the PR #188 configuration) -> requests
  [`flow/functional-verification-ck-trace.json`](../../../flow/functional-verification-ck-trace.json),
  [`flow/functional-verification-ck-trace-gl0.json`](../../../flow/functional-verification-ck-trace-gl0.json),
  bench [`sim/hyperram/ck_trace_tb.v`](../ck_trace_tb.v). The `$monitor`
  transcripts land in the untracked `flow/.klt/ck-trace*/` scratch (re-created
  by each run; `make -C verification/ctrl GL=1` wipes `flow/.klt` through
  `flow/hyperram.py check`, so re-run the trace after it). The numbers below
  are derived from those transcripts.
- Inputs: the committed routed netlist and post-route SDF
  (`tt_025C_1v80`, typ corner) bound by
  [`functional-verification-ctrl-sdf.checksums.json`](functional-verification-ctrl-sdf.checksums.json);
  Icarus 13.0, klt 0.9.2. Timestamps carry the run's effective 1 ns time
  precision (the routed netlist declares no `timescale` of its own); sub-ns
  statements come from SDF typ sums, not the transcript.
- Stimulus (the `ca_spans_three_ck_cycles` transfer plus one read): a CR0
  register write, host address 0x400 -> device word address 0x800, expected CA
  bytes in wire order `60 00 01 00 00 00`, and a memory-space read at host
  address 0x155 (device word 0x2AA, expected CA `a0 00 00 55 00 02`).
  `cfg_ck_tap` is left at its reset value 3; the trace confirms tap 3 selects
  `taps[3] = dly[8]`, i.e. eight of the sixteen `hr_tap_delay` cells (the
  selected mux input follows `dly[8]`).

## What the annotated pins do

Register write (all times ns; E = the core edge that launches CA byte 0 onto
the pins, seen as the `hb_dq_oe` rise and the first DQ byte):

| event | time | note |
|---|---|---|
| CS# falls | 5291 | tCSS window opens |
| `ck_en` asserts | 5292 | combinational, with ST_CA, one core clock after CS# |
| OE rises, DQ byte 0 = `60` | 5311 | **E** |
| ICG GCLK first rise | 5311 | the same edge E: latch captured `ck_en` in the low phase |
| CK pin edges | 5317^ 5328v 5337^ 5348v 5357^ 5368v 5377^ 5388v | 8 edges = 6 CA + 2 write-data |
| CK high / low widths | 11 / 9 | see duty below |
| OE falls, CS# rises | 5391 | after the single register-write data beat |

- **First CK edge is rising and CA byte 0 is already driven**: CK first rises
  at E+6 with byte 0 (`60`) stable since E (window E..E+10); margins 4 ns
  (to the window end) and 6 ns (from its start). The five alternating edges
  carry bytes 1..5, each inside its own 10 ns byte window (falls at +7 in
  [E+10, E+20] etc.; worst margin 3 ns). The read transaction repeats the
  geometry identically (OE 5651..5711, CK 5657^..5708v, CA `a0 00 00 55 00 02`
  at the edges).
- **No early CK edge.** There is no CK activity between the CS# fall (5291)
  and E+6 (5317); the ICG's first GCLK edge is exactly the CA-launch edge E.
  The `ck_en` assertion (5292, with ST_CA) is captured by the latch in the
  following low phase, so the gated pulse is full-width.
- **The zero-delay "early edge" of PR #188 is a zero-delay race, not silicon
  behaviour.** `make ck-trace-gl0` reproduces it: with `UNIT_DELAY=#0`, GCLK
  and CK rise at the CS#-fall edge itself (5270) and two full CK pulses run
  before OE/byte 0 (5290). With everything at zero delay, the ICG's internal
  inverter (`clkn`) and the controller's combinational `ck_en` path resolve in
  the same time step, and the latch UDP can see GATE change while still
  enabled. Under annotation `ck_en` arrives ~1 ns after the local clock leaf
  (flop CLK->Q plus one NAND), always behind `clkn`, so the latch stays
  closed -- the race cannot happen at any real corner. The synthesized
  zero-delay netlist passes 43/43 only because its `ck_en` logic happens to be
  deeper (more delta levels) than the routed mapping; that ordering luck is
  exactly why the two zero-delay runs disagree.

## CK duty and tap latency at the pins

- Measured tap-3 latency GCLK -> CK pin: **6.0 ns rise / 7.0 ns fall** (1 ns
  trace granularity) against the quarter-period (5 ns) design target; the
  design target centres edges in the 10 ns byte windows, and the measured
  +6/+7 placement still leaves every edge inside its window with >= 3 ns
  margin on both sides.
- CK duty at the pins over the transaction: **high 11 / low 9** at the 20 ns
  core period. SDF typ sums along GCLK -> `hb_ck` (all 6161 INTERCONNECT
  entries of this SDF are 0.000 at typ, so cell IOPATHs only) give
  **rise 5.485 / fall 6.189 ns** -- a +0.70 ns fall-side asymmetry made of:
  the tap output muxes `mux4_1` A2->X 0.210/0.471 (+0.261) and `mux2_2`
  0.188/0.313 (+0.125), the four CTS `buf_4` pairs inserted on the
  `dly[2,4,6,8]` nets (+0.24), the eight delay cells (+0.078), the ICG
  itself (0.130/0.123, -0.007).
- The 9 ns low half-period is what the behavioural model's tCK check flags
  (it requires >= 10 ns halves at t_ck_min 20 ns). `spec/device-model-params.md`
  Table 9.2 sources a 9-11 ns half-period range with a qualification on the
  50 MHz column; #2 owns that interpretation, so this record flags the duty
  numbers and changes nothing.

## Where the annotated suite actually diverges first

The bench's pad driver (`verification/ctrl/hrbench.py`, `_ck_mon`) samples
DQ/OE **5 ns after each CK edge** -- the documented stand-in for the real
CK's quarter-period position, valid while the RTL cells are zero-delay
stand-ins. On this annotated design CK *already* carries the real tap delay,
so the +5 ns sample lands ~11-12 ns after the launching core edge -- inside
the **next** byte's window:

| CK edge | time | DQ at the edge (correct CA) | DQ at +5 ns (what the model sees) |
|---|---|---|---|
| e0 ^ | 5317 | `60` (byte 0) | `00` (byte 1) |
| e1 v | 5328 | `00` (byte 1) | `01` (byte 2) |
| e2 ^ | 5337 | `01` (byte 2) | `00` (byte 3) |
| e3 v | 5348 | `00` (byte 3) | `00` (byte 4) |
| e4 ^ | 5357 | `00` (byte 4) | `00` (byte 5) |
| e5 v | 5368 | `00` (byte 5) | `00` (write byte 0) |

- The model assembles CA one byte late: the register write decodes as
  `00 01 00 00 00 00`, whose CA[45]=0 is reported as "wrapped burst
  requested" (`ca_spans_three_ck_cycles`). On reads the sixth CA sample
  (E+62) lands after `hb_dq_oe` drops (E+60, OE spans only the three CA
  cycles), which is the 37x "DQ must be driven by the host during CA".
  Write-data samples past the last CK fall see OE already low ("on write
  data"); `Bench.write` returning on `wr_ack` (edge 6, before the model's
  sixth CA edge) empties `transactions[-1]` ("list index out of range", the
  three no-message register asserts, the scoreboard timeout). This is one
  mechanism -- the sample position -- tracked as #199.
- Separately, `no_calibration_port_or_status_bit` fails because
  `Bench.cfg_read`'s fixed 1 ns settle now races the annotated `cfg_rdata`
  mux (reads back a mid-transition `0x24` from CFG_CS_HI). Same family --
  a fixed bench delay calibrated to zero delay -- different mechanism;
  tracked as #200.

## Verdict

- The routed CK launch path meets the CA-alignment contract at the pins on
  the annotated typ design: a rising first CK edge with CA byte 0 already
  driven, five alternating edges carrying the remaining bytes, no early or
  truncated ICG pulse. The ICG/tap-chain cause proposed by the #171 probe is
  **refuted** for real delays; the zero-delay early edge it observed is an
  ordering race that annotation resolves the correct way.
- The 0/43 annotated suite result stands as committed evidence, but its
  failures decompose into the bench's zero-delay stand-in assumptions meeting
  real annotation (the +5 ns sample position; the 1 ns cfg-read settle; the
  ack-vs-sixth-edge race) plus the duty flag #2 owns. The narrower findings
  carry the reproductions; the design stays unchanged here and no bench,
  model or spec row was touched.
- Annotation metadata for the committed run: `environment.sdf` reports
  `annotated: true`, `partial: true`, dropped entries `timingcheck` 504,
  `zero_delay_bus_port_source_interconnect` 208,
  `zero_delay_physical_only_interconnect` 20 (#190 tracks the tier wording;
  #189 tracks that DEF/SPEF are not yet hashed).

## What this does not prove

Single corner (`tt_025C_1v80` typ), core only: no pads, no package, no
across-PVT duty claim -- the delay-chain campaign
(`sim/delay-chain/records/RECORD.md`) owns the chain's PVT behaviour, #2 owns
the duty requirement, and the pad-facing half stays with the I/O-ring sibling.
No spec row is called met here.
