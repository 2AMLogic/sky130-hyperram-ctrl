# Pre-layout STA of the controller netlist (all shipped liberty corners)

`make hyperram-sta` -> [`sta.json`](sta.json), the unmodified `klt sta` response.
Request: [`flow/sta-hyperram.json`](../../../flow/sta-hyperram.json) -- `clk` at 20.0 ns (50 MHz, spec/target-spec.md row 1's target, not the 100 MHz stretch), 16 corners in one round trip.

- Netlist: `sim/hyperram/records/hyperram_ctrl.netlist.v`, sha256:5ea579ba0640d6d73dc84e04e410a889b0588b313785f2697c4f4cfbc38a9f64.
- Engine: openroad 26Q4-1310-g98c6045c72; klt 0.8.0; PDK open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7.
- `hyperram_ctrl`, status `ok`, `geometry_source: netlist_estimate`.

## What was assumed

Read out of the response, not asserted here:

- **Ideal clock** (`clock_mode: "ideal"`) -- no CTS, no clock-tree insertion delay, no propagated-clock latency. The reported `clock_skew_ns` is OpenSTA's ideal-network estimate.
- **No wire load** (`wire_load_model: null`, `wire_load_mode: null`) and **no placement or routing** (`def_path: null`, `spef_path: null`): interconnect is OpenSTA's own estimate from the netlist. These are pre-layout numbers, not post-route ones.
- **No pads.** Only `sky130_fd_sc_hd` is loaded; no `sky130_fd_io` cell, no pad delay, no bond/package model, no core-to-pad seam.
- **No I/O constraints.** The request sets only the clock port and period: no input/output delay, no driving cell, no input transition, no output load. The design's ports are therefore unconstrained (below).

## Corners inside the ratified supply window (graded)

Decision 0004 puts the core supply at 1.8 V +/- 10 %, i.e. 1.62-1.98 V. `make hyperram-sta` fails on a negative setup or hold slack at any of these 8 corners.

| corner | supply (V) | setup slack (ns) | hold slack (ns) | fmax (MHz) | status |
|---|---|---|---|---|---|
| `ff_100C_1v65` | 1.65 | 9.64408 | 0.27604 | 271.845 | constrained |
| `ff_100C_1v95` | 1.95 | 9.72145 | 0.21974 | 349.256 | constrained |
| `ff_n40C_1v65` | 1.65 | 9.61458 | 0.27562 | 256.342 | constrained |
| `ff_n40C_1v76` | 1.76 | 9.66518 | 0.24213 | 297.682 | constrained |
| `ff_n40C_1v95` | 1.95 | 9.72341 | 0.20407 | 363.35 | constrained |
| `ss_n40C_1v76` | 1.76 | 9.24029 | 0.519 | 128.852 | constrained |
| `tt_025C_1v80` | 1.80 | 9.55587 | 0.33121 | 214.138 | constrained |
| `tt_100C_1v80` | 1.80 | 9.56054 | 0.33955 | 215.878 | constrained |

## Corners outside it (reported, not graded)

The PDK ships liberty at supplies decision 0004's window excludes. These 8 corners are recorded and printed, and the target does not fail on them. `ss_100C_1v60` and `ss_n40C_1v60` miss the 1.62 V floor by 20 mV; that is the window's arithmetic, not a judgement about those corners. The same decision's "all liberty corners" line does not reconcile with the window -- left as found, and #2 owns settling it.

| corner | supply (V) | setup slack (ns) | hold slack (ns) | fmax (MHz) | status |
|---|---|---|---|---|---|
| `ff_n40C_1v56` | 1.56 | 9.55665 | 0.31153 | 221.297 | constrained |
| `ss_100C_1v40` | 1.40 | 5.88001 | 0.98269 | 70.8216 | constrained |
| `ss_100C_1v60` | 1.60 | 9.03149 | 0.67759 | 104.819 | constrained |
| `ss_n40C_1v28` | 1.28 | -17.3491 | 2.00452 | 26.7744 | constrained |
| `ss_n40C_1v35` | 1.35 | -5.31591 | 1.45077 | 39.5008 | constrained |
| `ss_n40C_1v40` | 1.40 | -0.36499 | 1.19796 | 49.1039 | constrained |
| `ss_n40C_1v44` | 1.44 | 2.49099 | 1.05445 | 57.1134 | constrained |
| `ss_n40C_1v60` | 1.60 | 8.9227 | 0.69001 | 92.1626 | constrained |

## What was not timed

`constraint_completeness` is `incomplete` at every corner and the target does not gate on it. The counts are identical across all 16 corners:

- **143 unclocked registers.** Every sampled pin is under `u_cap/`, the `hr_rd_capture` instance. That module clocks its capture flops off `rwds_d` -- the input strobe after the delay chain -- on both edges, and a `klt sta` request names exactly one `clock_port`, so OpenSTA sees no clock on them. **The read-capture path is unconstrained and unreported in this record.**
- **341 unconstrained endpoints** -- the design's output ports and `cfg_rdata`, since no output delay or load is set (above).

Neither is masked. `constraints.false_path_from` would have hidden the capture path instead of recording the gap, and the request schema cannot express a second or generated clock for `rwds_d` at the pinned klt. Constraining that domain is a modelling choice that belongs to the spec (#2); its real delays belong to the ngspice delay-chain campaign (#99) and its pad-facing half to #98.

All 3 cells yosys left as blackboxes (`sky130_fd_sc_hd__dlclkp_1`, `sky130_fd_sc_hd__dlygate4sd3_1`, `sky130_fd_sc_hd__mux2_1`) are defined in the liberty every corner read, so the delay chain is timed with real cell delays rather than as zero delay. `make hyperram-sta` fails if that is ever untrue.

## What this does not prove

This is the **STA, all core** half of `spec/target-spec.md` row 1's proof ("STA + SPICE pad timing", corners "all core + all ngspice") and nothing more. It is **not** a proof of row 11 (read capture), row 12 (read-capture margin), row 14 (write path) or row 19 (timing at the pins): each of those needs the pads, SPICE, or the strobe domain, none of which are in this record. **No spec row is called met here** -- the rows and their proof status are `spec/`'s to state (#2, #100), and the manifests and signoff record are untouched by this target.

Also not here: place-and-route, wire load, SPEF, DRC/LVS (`layout/`, #52), and any claim about 100 MHz -- the `fmax_mhz` column is OpenSTA's ideal-clock, no-wire-load estimate for the `clk` domain alone, reported, not graded.
