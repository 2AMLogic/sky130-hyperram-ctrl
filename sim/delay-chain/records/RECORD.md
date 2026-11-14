# RWDS delay chain across PVT (spec open question (b))

**Monotonic at every simulated corner, rise and fall.**

Per-tap delay across corners (min/max over corners with usable measurements; details in taps.csv):

| tap | cells | rise min-max (ns) | rise max/min | fall min-max (ns) | fall max/min |
|---|---|---|---|---|---|
| 0 | 2 | 0.5248 - 1.3814 | 2.6320 | 0.5090 - 1.4779 | 2.9034 |
| 1 | 4 | 1.0415 - 2.7579 | 2.6479 | 0.9926 - 2.9525 | 2.9744 |
| 2 | 6 | 1.5529 - 4.1342 | 2.6623 | 1.4759 - 4.4270 | 2.9994 |
| 3 | 8 | 2.0720 - 5.5104 | 2.6594 | 1.9614 - 5.9019 | 3.0090 |
| 4 | 10 | 2.5798 - 6.8858 | 2.6692 | 2.4466 - 7.3764 | 3.0149 |
| 5 | 12 | 3.0999 - 8.2602 | 2.6646 | 2.9318 - 8.8503 | 3.0188 |
| 6 | 14 | 3.6082 - 9.6347 | 2.6702 | 3.4159 - 10.3243 | 3.0224 |
| 7 | 16 | 4.1202 - 10.9936 | 2.6682 | 3.8938 - 11.7813 | 3.0257 |

Corners in report: 45 (expected 45); monotonic (rise and fall): 45.

Result of the `make delay-chain` campaign (decision 0004 ngspice corner set) over the 16-cell `g_rwds_dly` chain of rtl/hyperram_ctrl/hr_rd_capture.v. The second chain (`g_ck_dly`, hr_dq_out.v) is the same cell, length and tap arithmetic, so this record answers for it too; no row-14 claim is made here.

## Provenance (from the run's own report)

- engine: ngspice 47 (engine_host: worker); build banner: ****** ** ngspice-47 : Circuit level simulation program ** Compiled with KLU Direct Linear Solver ** The U. C. Berkeley CAD Group ** Copyright 1985-1994, Regents of the University of California. ** Co
- batch job(s): klt-sim-7f61c0d68dcf (state: done)
- runner/client klt skew (deliberate, runner_version_check=warn): runner 0.9.0 vs client 0.8.0 (the repo pin); the runner is the newer side, so no request feature can be silently dropped
- klt: 0.8.0
- PDK: open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7 (also installed via search root: ~/.volare; client pinned $PDK_ROOT); models_lib: external (sha256 17c208a699228f5acb87bf59c09c22a4c4d3937b6766b4957737d34e8e075f64)

## Assumptions (stated, per AC1)

- **Schematic-level figures.** The PDK cell subckts are eight MOSFETs and zero capacitors: this record carries no parasitics of any kind, including the chain's own layout RC. A post-layout number is `klt pex`, not this record.
- Input: full-rail pulse, 0.15 ns rise/fall, one rising edge (~2 ns) and the matching falling edge (~22 ns). Amplitude follows the corner rail (`corners.supply_waveforms`), i.e. the on-chip condition after the pad seam; pad delay and swing are open question (a), out of scope.
- Loads exactly as the committed netlist: an even tap node drives the next delay cell PLUS one mux4_2 A pin, an odd node only the next cell, dly16 only its mux; each mux feeds its clkbuf_1. Select held static (tap_sel = 0, S0 = S1 low) -- the design holds it for a whole burst, and the per-tap delay is read at the dly nodes, before the mux.
- Delay = 50 % rail crossing at the tap minus the 50 % crossing at the input node (supply-relative trip point via `frac_of`), first rise and first fall in 0..60 ns -- the window spans the worst-corner delay, not the typ-only one the first submit used (10 slow corners' late-tap fall edges landed past 30 ns and came back empty). Transient `5p 60n 0 25p` (tmax bounds the solver step near the edges).
- Monotonicity test (AC3): delay(tap k+1) > delay(tap k) for every k, for rise and for fall, at that corner. Tap k+1's chain strictly contains tap k's, so a failure would point at a measurement artifact before the circuit.
- Simulated circuit: sim/delay-chain/dlychain.sp; request: flow/sim-delay-chain.json; raw response: sim.report.json (committed verbatim); declared matrix: corners.json, machine-checked with `klt corner-matrix check`.
