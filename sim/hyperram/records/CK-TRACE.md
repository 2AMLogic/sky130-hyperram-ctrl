# Post-route CK / command-address pin-waveform trace (SDF-annotated, typ)

Issue #187 (item 7 follow-up): locate the first divergence between the routed
controller and the expected six-byte CA transfer at 50 MHz, and correct the CK
launch path **if** the waveform establishes a design defect. The waveform does
not: this record traces the annotated pins, refutes the proposed ICG / tap-chain
cause, and locates the divergence the 0/43 annotated suite (the pre-#199 bench) reported --
in the bench's pad-sample position, not in the design (single typ corner). The design, the bench,
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
  Icarus 13.0, klt 0.9.2. Timestamps are `$realtime` in ns at 1 ps precision
  (the bench's `` `timescale 1ns/1ps`` is inherited by the routed netlist,
  which declares none). An earlier revision of the bench logged integer `$time`
  (1 ns rounding) and so mis-sampled DQ; every number below is from the
  `$realtime` transcript. The bench also logs `CK5` lines: DQ and OE at each CK
  edge and again 5 ns later, the position the cocotb pad driver samples.
- Stimulus (the `ca_spans_three_ck_cycles` transfer plus one read): a CR0
  register write, host address 0x400 -> device word address 0x800, expected CA
  bytes in wire order `60 00 01 00 00 00`, and a memory-space read at host
  address 0x155 (device word 0x2AA, expected CA `a0 00 00 55 00 02`).
  `cfg_ck_tap` is left at its reset value 3; the trace confirms tap 3 selects
  `taps[3] = dly[8]`, i.e. eight of the sixteen `hr_tap_delay` cells (the
  selected mux input follows `dly[8]`).

## What the annotated pins do (typ corner only)

Register write (all times ns, `$realtime`; E = the core clock edge that
launches CA byte 0, 5310.674 at `rclk`):

| event | time | note |
|---|---|---|
| core edge E (`rclk` rise) | 5310.674 | |
| CS# falls | 5291.042 | one core period earlier (core edge 5290.674); also the ICG local-clock rise |
| `ck_en` asserts | 5291.820 | 0.778 after the ICG local clock rose |
| OE rises | 5311.014 | |
| DQ byte 0 = `60` settled | 5311.207 | `00` -> `20` (5311.104) -> `60` |
| ICG GCLK first rise | 5311.172 | the gated pulse of edge E |
| CK pin rise / fall | 5316.646^ 5327.652v 5336.646^ 5347.652v 5356.646^ 5367.652v 5376.646^ 5387.652v | 8 edges = 6 CA + 2 write-data |
| CK high / low widths | 11.006 / 8.994 | see duty below |
| OE falls | 5391.048 | after the single register-write data beat |
| CS# rises | 5391.204 | |

- **First CK edge is rising and CA byte 0 is already driven** at the instant
  of the edge: the first CK rise (5316.646) sees DQ=`60`, settled since
  5311.207 (setup margin 5.439) and holding until the byte-1 transition begins
  at 5320.703 (hold margin 4.057). The same read of each edge: e1 fall
  (5327.652) sees `00` inside byte 1 (`00` from 5321.690 to 5330.462; margins
  5.962 / 2.810, the smallest observed) and e2 rise (5336.646) sees `01` inside
  byte 2 (`01` from 5331.309 to 5341.664; margins 5.337 / 5.018). Bytes 3..5
  are all `00`, so no DQ transition bounds those windows and their margins are
  not observable from this stimulus. The read transaction repeats the geometry
  (CS# 5631.042, OE 5651.014, CK first rise 5656.646, CA `a0 00 00 55 00 02`
  at the six edges, OE falls 5711.048).
- **No early CK edge at typ.** There is no CK activity between the CS# fall
  (5291.042) and the first CK rise (5316.646); the ICG's first GCLK edge
  (5311.172) is the CA-launch edge E. The `ck_en` assertion (5291.820) arrives
  after the ICG local clock has already risen, so it is captured in the
  following low phase and the gated pulse is full width. This is an observation
  of the annotated typ run; it is not shown for any other corner.
- **The zero-delay early edge of PR #188 reproduces without annotation.**
  `make ck-trace-gl0` (`UNIT_DELAY=#0`, FUNCTIONAL stand-ins): at the CS#-fall
  edge (5270) `ck_en`, GCLK and CK all rise together; CK falls at 5280 (**one**
  pulse before OE); OE and CA byte 0 (`60`) appear at 5290 together with the
  next CK rise. With every delay zero, `ck_en` changes in the same time step as
  the ICG clock, so the pulse is a time-step ordering artifact of the
  zero-delay model. The annotated run, whose `ck_en` arrives 0.778 ns after the
  ICG clock, does not show it. Hypothesis, not measured here: the synthesized
  zero-delay netlist's 43/43 may owe its pass to `ck_en` logic depth in that
  mapping; the trace does not examine that netlist. Whether any other corner
  orders `ck_en` behind the ICG clock is not claimed.

## CK duty and tap latency at the pins

- Measured tap-3 latency GCLK -> CK pin at typ: **5.474 ns rise** (GCLK
  5311.172 -> CK 5316.646) **/ 6.182 ns fall** (GCLK 5321.470 -> CK 5327.652),
  against the quarter-period (5 ns) design target. Every observed edge still
  sits inside its observed byte window (smallest margin 2.810 ns, above).
- CK duty at the pins over the transaction: **high 11.006 / low 8.994** at the
  20 ns core period. SDF typ sums along GCLK -> `hb_ck` (all 6161 INTERCONNECT
  entries of this SDF are 0.000 at typ, so cell IOPATHs only) give
  **rise 5.485 / fall 6.189 ns**, agreeing with the measured values to 0.011 ns
  and showing a +0.70 ns fall-side asymmetry made of: the tap output muxes
  `mux4_1` A2->X 0.210/0.471 (+0.261) and `mux2_2` 0.188/0.313 (+0.125), the
  four CTS `buf_4` pairs inserted on the `dly[2,4,6,8]` nets (+0.24), the eight
  delay cells (+0.078), the ICG itself (0.130/0.123, -0.007).
- The 8.994 ns low half-period is what the behavioural model's tCK check flags
  (it requires >= 10 ns halves at t_ck_min 20 ns). `spec/device-model-params.md`
  Table 9.2 sources a 9-11 ns half-period range with a qualification on the
  50 MHz column; #2 owns that interpretation, so this record flags the duty
  numbers and changes nothing.

## Where the annotated suite's pad sample lands

The bench's pad driver (`verification/ctrl/hrbench.py`, `_ck_mon`) samples
DQ/OE **5 ns after each CK edge** -- the documented stand-in for the real
CK's quarter-period position, valid while the RTL cells are zero-delay
stand-ins. On this annotated design CK *already* carries the real tap delay.
The bench logs both instants directly (`CK5` lines), register write, ns:

| CK edge | time | DQ/OE at the edge | time +5 | DQ/OE at +5 ns |
|---|---|---|---|---|
| e0 ^ | 5316.646 | `60` / 1 | 5321.646 | **`40`** / 1 (mid-transition: `40` from 5320.703, `00` from 5321.690) |
| e1 v | 5327.652 | `00` / 1 | 5332.652 | `01` / 1 |
| e2 ^ | 5336.646 | `01` / 1 | 5341.646 | `01` / 1 (leaves `01` at 5341.664) |
| e3 v | 5347.652 | `00` / 1 | 5352.652 | `00` / 1 |
| e4 ^ | 5356.646 | `00` / 1 | 5361.646 | `00` / 1 |
| e5 v | 5367.652 | `00` / 1 | 5372.652 | `00` / 1 |

- The six +5 ns samples are **`40 01 01 00 00 00`**. The first differs from
  the expected `60` because the sample lands during the byte-0 -> byte-1
  transition (a glitching bus: `60` -> `40` -> `00`); the +5 ns instants of
  e1 and e2 both read `01`. This matches an independent log of the arguments
  passed to `HyperRamModel.clock` in `ca_spans_three_ck_cycles` taken during review. The
  earlier revision of this record (integer `$time`) reported `00 01 00 00 00
  00` -- a rounding artifact, superseded here.
- Read transaction, +5 ns samples: e0 `00`, e1 `00`, e2 `55`, e3 `00`,
  e4 `02` at OE=1, and the sixth sample at 5712.652 sees OE=0 (OE fell at
  5711.048) with DQ=`00`. The sixth sample falls after OE; whether that raises the model's
  "DQ must be driven by the host during CA" is the hypothesis below.
  Write-data samples: 5381.646 OE=1, then 5392.652 OE=0 (OE fell 5391.048).

## The 43 failures: observations versus hypotheses

Observed on the pre-#199 bench (the committed report at merge-base `b60c730`,
`functional-verification-ctrl-sdf.report.json`, reproduced 0/43 with identical
messages). That report is superseded: `main` has since landed #199 (sample on
the annotated CK pin edge) and #200 (cfg_read settle) and re-minted the
report, now 4 passed / 39 failed. The sample-position divergence measured here
is therefore a landed fix, not a hypothesis; the table below is kept as the
evidence that motivated it and is not the current suite state:

| count | failure message |
|---|---|
| 37 | `DQ must be driven by the host during CA` |
| 3 | message-free `AssertionError`: row 04 `test_row04_latency.py:74` (`assert b.model.fixed_latency`), row 06 `test_row06_write_mask.py:47` (`assert b.model.regs[0x800] == 0x1234`), row 07 `test_row07_register_space.py:32` (`assert b.model.regs[REG_CR0] == 0x8F17`) |
| 1 | `transfer timed out: issued 5/24, acked 0` (random-traffic scoreboard; zero acknowledgements in a read) |
| 1 | `device-model violations` -- tCK half period 9.0 ns (`ca_spans_three_ck_cycles`) |
| 1 | `cfg 4: 0x0024 has bits set outside documented field 0x000f` (`no_calibration_port_or_status_bit`) |

Only the sample-position observations above and these messages are
evidence of this trace. What follows was hypothesis when the trace was taken
(the post-#199/#200 report on `main` is the later evidence for the first and
last items; the rest remain unexplained by this trace):

- The 37 CA-driven failures are consistent with the sixth CA sample landing
  after OE falls (read trace above); the 5 ns sample offset is the candidate
  cause (#199).
- The three message-free assertions check fixed-latency mode and register
  contents; that the register writes never reach the device, or that the
  controller's write acknowledgement precedes the model's sixth CA edge, is a
  hypothesis -- the failing assertions do not show why.
- The scoreboard timeout (a read with zero acknowledgements) is not
  explained by the sample position alone; configuration settling is an
  unproved candidate.
- `no_calibration_port_or_status_bit` reads `0x24` from the config bus; a fixed
  1 ns settle in `Bench.cfg_read` racing the annotated `cfg_rdata` mux is a
  hypothesis (#200); the trace does not instrument `cfg_rdata`.

## Verdict

- At the annotated typ corner the routed CK launch path puts a rising first CK
  edge at a point where CA byte 0 is already driven, with five alternating
  edges inside observed byte windows (smallest margin 2.810 ns) and no early
  or truncated ICG pulse. The ICG/tap-chain cause proposed by the #171 probe
  is not supported at typ; the zero-delay early edge is one CK pulse that
  annotation does not show. No other corner is claimed.
- The measured effect on the bench is that its 5 ns post-edge sample lands in
  the next byte's transition (`40 01 01 00 00 00`). That is observed; its
  causal role in each of the 43 failures was the hypothesis list above
  (since exercised by #199/#200 landing on `main`: 43 -> 39 failing), and
  the design is left unchanged here with no bench, model or spec row touched.
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
