# Pre-layout STA of the controller netlist (all shipped liberty corners)

`make hyperram-sta` -> [`sta.json`](sta.json), the unmodified `klt sta` response.
Request: [`flow/sta-hyperram.json`](../../../flow/sta-hyperram.json) -- `clk` at 20.0 ns (50 MHz, spec/target-spec.md row 1's target, not the 100 MHz stretch), 16 corners in one round trip.

- Netlist: `sim/hyperram/records/hyperram_ctrl.netlist.v`, sha256:0f03005ab04a2fc45365680d543d13e1742a8e4288228c28eb279b0b94e463d7.
- Engine: openroad 26Q4-1310-g98c6045c72; klt 0.9.2; PDK open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7.
- `hyperram_ctrl`, status `ok`, `geometry_source: netlist_estimate`.

## What was assumed

Read out of the response, not asserted here:

- **Ideal clock** (`clock_mode: "ideal"`) -- no CTS, no clock-tree insertion delay, no propagated-clock latency. The reported `clock_skew_ns` is OpenSTA's ideal-network estimate.
- **No wire load** (`wire_load_model: null`, `wire_load_mode: null`) and **no placement or routing** (`def_path: null`, `spef_path: null`): interconnect is OpenSTA's own estimate from the netlist. These are pre-layout numbers, not post-route ones.
- **No pads.** Only `sky130_fd_sc_hd` is loaded; no `sky130_fd_io` cell, no pad delay, no bond/package model, no core-to-pad seam.
- **No I/O constraints.** The request sets only the clock port and period: no input/output delay, no driving cell, no input transition, no output load. The design's ports are therefore unconstrained (below).

## Corners inside the ratified supply window (graded)

Decision 0004 puts the core supply at 1.8 V +/- 10 %, i.e. 1.62-1.98 V. `make hyperram-sta` fails on a negative setup or hold slack at any of these 8 corners.

| corner | supply (V) | worst setup (ns) | worst hold (ns) | setup viol. endpoints | setup TNS (ns) | hold viol. endpoints | hold TNS (ns) | fmax (MHz) | status |
|---|---|---|---|---|---|---|---|---|---|
| `ff_100C_1v65` | 1.65 | 9.64408 | 0.27604 | 0 | 0 | 0 | 0 | 280.6 | constrained |
| `ff_100C_1v95` | 1.95 | 9.72145 | 0.21974 | 0 | 0 | 0 | 0 | 364.291 | constrained |
| `ff_n40C_1v65` | 1.65 | 9.61458 | 0.27562 | 0 | 0 | 0 | 0 | 250.445 | constrained |
| `ff_n40C_1v76` | 1.76 | 9.66518 | 0.24213 | 0 | 0 | 0 | 0 | 293.449 | constrained |
| `ff_n40C_1v95` | 1.95 | 9.72341 | 0.20407 | 0 | 0 | 0 | 0 | 364.402 | constrained |
| `ss_n40C_1v76` | 1.76 | 9.24029 | 0.519 | 0 | 0 | 0 | 0 | 131.404 | constrained |
| `tt_025C_1v80` | 1.80 | 9.55587 | 0.33121 | 0 | 0 | 0 | 0 | 221.529 | constrained |
| `tt_100C_1v80` | 1.80 | 9.56054 | 0.33955 | 0 | 0 | 0 | 0 | 224.929 | constrained |

## Corners outside it (reported, not graded)

The PDK ships liberty at supplies decision 0004's window excludes. These 8 corners are recorded and printed, and the target does not fail on them. `ss_100C_1v60` and `ss_n40C_1v60` miss the 1.62 V floor by 20 mV; that is the window's arithmetic, not a judgement about those corners. The same decision's "all liberty corners" line does not reconcile with the window -- left as found, and #2 owns settling it.

| corner | supply (V) | worst setup (ns) | worst hold (ns) | setup viol. endpoints | setup TNS (ns) | hold viol. endpoints | hold TNS (ns) | fmax (MHz) | status |
|---|---|---|---|---|---|---|---|---|---|
| `ff_n40C_1v56` | 1.56 | 9.55665 | 0.31153 | 0 | 0 | 0 | 0 | 214.746 | constrained |
| `ss_100C_1v40` | 1.40 | 6.58385 | 0.98269 | 0 | 0 | 0 | 0 | 74.5371 | constrained |
| `ss_100C_1v60` | 1.60 | 9.03149 | 0.67759 | 0 | 0 | 0 | 0 | 110.066 | constrained |
| `ss_n40C_1v28` | 1.28 | -17.9418 | 2.00452 | 181 | -878.787 | 0 | 0 | 26.3561 | constrained |
| `ss_n40C_1v35` | 1.35 | -5.52991 | 1.45077 | 21 | -64.3886 | 0 | 0 | 39.1697 | constrained |
| `ss_n40C_1v40` | 1.40 | -0.43424 | 1.19796 | 2 | -0.73932 | 0 | 0 | 48.9375 | constrained |
| `ss_n40C_1v44` | 1.44 | 2.56021 | 1.05445 | 0 | 0 | 0 | 0 | 57.3401 | constrained |
| `ss_n40C_1v60` | 1.60 | 8.9227 | 0.69001 | 0 | 0 | 0 | 0 | 93.0207 | constrained |

## What was not timed

`constraint_completeness` is `incomplete` at every corner and the target does not gate on it. The counts are identical across all 16 corners:

- **143 unclocked registers.** Every sampled pin is under `u_cap/`, the `hr_rd_capture` instance. That module clocks its capture flops off `rwds_d` -- the input strobe after the delay chain -- on both edges, and this request constrains exactly one clock port, so OpenSTA sees no clock on them. **The read-capture path is unconstrained and unreported in this record.**
- **341 unconstrained endpoints** -- the design's output ports and `cfg_rdata`, since no output delay or load is set (above).

Neither is masked. `constraints.false_path_from` would have hidden the capture path instead of recording the gap, and the pinned klt's (0.9.2) request schema can declare a second clock port and asynchronous clock groups (`constraints.clocks`/`constraints.clock_groups`, klayout-tools#4241) but still cannot express a generated clock on `rwds_d` -- an internal net, not a port -- so the capture domain stays unconstrained here. Constraining that domain is a modelling choice that belongs to the spec (#2); its real delays belong to the ngspice delay-chain campaign (#99) and its pad-facing half to #98.

All 0 cells yosys left as blackboxes () are defined in the liberty every corner read, so the delay chain is timed with real cell delays rather than as zero delay. `make hyperram-sta` fails if that is ever untrue.

## What this does not prove

This is the **STA, all core** half of `spec/target-spec.md` row 1's proof ("STA + SPICE pad timing", corners "all core + all ngspice") and nothing more. It is **not** a proof of row 11 (read capture), row 12 (read-capture margin), row 14 (write path) or row 19 (timing at the pins): each of those needs the pads, SPICE, or the strobe domain, none of which are in this record. **No spec row is called met here** -- the rows and their proof status are `spec/`'s to state (#2, #100), and the manifests and signoff record are untouched by this target.

Also not here: place-and-route, wire load, SPEF, DRC/LVS (`layout/`, #52), and any claim about 100 MHz -- the `fmax_mhz` column is OpenSTA's ideal-clock, no-wire-load estimate for the `clk` domain alone, reported, not graded.
