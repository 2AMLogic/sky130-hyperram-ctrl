# Post-route multi-corner STA of the routed DEF + SPEF, RWDS strobe clock declared (issue #172)

`make hyperram-sta-postroute` -> [`sta-postroute.json`](sta-postroute.json) (clocks left **related**) and [`sta-postroute-async.json`](sta-postroute-async.json) (the same request with `clk` and `hb_rwds_i` in asynchronous `clock_groups`), the unmodified `klt sta` responses. Requests: [`flow/sta-hyperram-postroute.json`](../../../flow/sta-hyperram-postroute.json) and [`flow/sta-hyperram-postroute-async.json`](../../../flow/sta-hyperram-postroute-async.json) -- `def` + `spef` mode on `layout/records/hyperram_ctrl.def` and `layout/records/hyperram_ctrl.spef`, `constraints.propagated_clock: true`, and `constraints.clocks` declaring `clk` (primary; target-spec row 1) **and** `hb_rwds_i` at the same 20.0 ns, so the strobe propagates through the `hr_tap_delay` chain to the `u_cap/` capture flops; all 16 shipped `sky130_fd_sc_hd` corners in one round trip per reading.

- DEF: `layout/records/hyperram_ctrl.def`, sha256:cf7eb6c5021763aec3d753425386284d5fe0bfdc5c83df9c19edf1540df8be4d.
- SPEF: `layout/records/hyperram_ctrl.spef`, sha256:f8d72e9d22153d8c6cdc0294f13db74bfde863888e9c39f90878bfc491c84117.
- Engine: openroad 26Q3-1510-g6cb3f2b704; klt 0.9.2; PDK open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7.
- `hyperram_ctrl`, status `ok`, `geometry_source: routed`, `clock_mode: propagated`, and `timing_status: constrained` at every corner of both readings.

## What was assumed

Read out of the responses, not asserted here:

- **Propagated clock** (`clock_mode: "propagated"`) on both declared clocks: hold/removal includes the clock-tree insertion delay and skew the DEF carries, and, for the strobe, the `hr_tap_delay` chain it propagates through. The latency evidence block reports 5 clock sinks and a worst network latency of 2.460365 ns (`clock_sinks_sample: u_fsm/_2164_/CLK, u_cap/_812_/CLK, u_out/_22_/CLK, u_out/_28_/CLK, _409_/CLK`).
- **Routed geometry, real parasitics to the extent the SPEF annotated** (`def_path` and `spef_path` name the committed `layout/records/hyperram_ctrl.def` / `layout/records/hyperram_ctrl.spef`). The SPEF session names 2379 of 2397 design nets (`annotation_complete: false`) -- the gaps are named below.
- **Two clocks, relationship unsettled.** `clk` is primary; `hb_rwds_i` is declared as a second clock at the same period so the capture domain is timed rather than unclocked. Whether the strobe domain is synchronous, asynchronous, or something phase-specific to the read burst is decision **C4 in #2**, not this record's: the two responses are the **related** reading (cross-domain paths timed as synchronous -- conservative) and the **asynchronous** reading (they are not timed at all). **Every number below is provisional on whichever of those two assumptions it sits beside, pending #2.**
- **No I/O delays.** The draft spec states no setup/hold figure for any port relative to `clk` (its boundary figures -- tIS/tIH, tCSS, tCKD -- are HyperBus-pin-to-HyperBus-pin numbers, not core-clock numbers), so none is guessed: every input and output is left unconstrained and counted below. A scalar default is not an option either: the pinned klt applies I/O delays relative to the primary clock only, would land one on `hb_rwds_i` itself, and cannot express a DQ input delay relative to the strobe clock at all (klayout-tools#7399).
- **No false paths.** `constraints.false_path_from` is deliberately absent; hiding the capture path is what this record exists not to do.

## Corners inside the ratified supply window (graded)

Decision 0004 puts the core supply at 1.8 V +/- 10 %, i.e. 1.62-1.98 V. Unlike `make hyperram-sta`, this target does **not** fail on a negative slack at these 8 corners: under an unsettled clock relationship a failing cross-domain path is a finding for the ratifier and a filed design-iteration issue, not a gate to relax the request against. Each negative below is linked. The `fmax (MHz)` column is OpenSTA's own extrapolation over the `clk` domain, reported as the response carries it and graded by nothing here.

**Related-clocks reading** (cross-domain paths timed as synchronous):

| corner | supply (V) | setup slack (ns) | hold slack (ns) | fmax (MHz) | status |
|---|---|---|---|---|---|
| `ff_100C_1v65` | 1.65 | 0.00662 | -0.55785 | 500.721 | constrained |
| `ff_100C_1v95` | 1.95 | 2.25563 | -0.44937 | 628.463 | constrained |
| `ff_n40C_1v65` | 1.65 | -0.67122 | -0.60923 | 465.464 | constrained |
| `ff_n40C_1v76` | 1.76 | 0.88485 | -0.53343 | 530.476 | constrained |
| `ff_n40C_1v95` | 1.95 | 2.60207 | -0.4472 | 633.764 | constrained |
| `ss_n40C_1v76` | 1.76 | -6.76799 | -1.069 | 256.187 | constrained |
| `tt_025C_1v80` | 1.80 | -1.5614 | -0.67362 | 414.173 | constrained |
| `tt_100C_1v80` | 1.80 | -1.86471 | -0.6644 | 419.836 | constrained |

**Asynchronous-clock-groups reading** (cross-domain paths not timed):

| corner | supply (V) | setup slack (ns) | hold slack (ns) | fmax (MHz) | status |
|---|---|---|---|---|---|
| `ff_100C_1v65` | 1.65 | 9.10244 | 0.29993 | 500.721 | constrained |
| `ff_100C_1v95` | 1.95 | 9.35313 | 0.2392 | 628.463 | constrained |
| `ff_n40C_1v65` | 1.65 | 8.69705 | 0.30291 | 465.464 | constrained |
| `ff_n40C_1v76` | 1.76 | 8.91177 | 0.26722 | 530.476 | constrained |
| `ff_n40C_1v95` | 1.95 | 9.15394 | 0.22593 | 633.764 | constrained |
| `ss_n40C_1v76` | 1.76 | 8.51824 | 0.55869 | 256.187 | constrained |
| `tt_025C_1v80` | 1.80 | 9.0379 | 0.3594 | 414.173 | constrained |
| `tt_100C_1v80` | 1.80 | 9.06982 | 0.36708 | 419.836 | constrained |

### Per-clock worst paths (in-window corners)

The response reports one worst row per path group without naming the group; the split below attributes each row by capture register -- an endpoint under `u_cap/` is the strobe (`hb_rwds_i`) domain, every other endpoint the `clk` domain -- with the related reading's rows before the asynchronous reading's, setup before hold within each:

| corner | clock | side | worst path | slack (ns) |
|---|---|---|---|---|
| `ff_100C_1v65` | `clk` | setup (related) | `u_cap/_844_/Q` -> `_519_/D` | 0.00662 |
| `ff_100C_1v65` | `hb_rwds_i` | setup (related) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 9.10244 |
| `ff_100C_1v65` | `clk` | hold (related) | `hb_rwds_i` -> `u_fsm/_2214_/D` | -0.55785 |
| `ff_100C_1v65` | `hb_rwds_i` | hold (related) | `u_cap/_950_/Q` -> `u_cap/_949_/D` | 0.3874 |
| `ff_100C_1v65` | `clk` | setup (async) | `u_out/_44_/Q` -> `u_out/_24_/D` | 9.68969 |
| `ff_100C_1v65` | `hb_rwds_i` | setup (async) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 9.10244 |
| `ff_100C_1v65` | `hb_rwds_i` | hold (async) | `u_cap/_939_/Q` -> `u_cap/_943_/D` | 0.29993 |
| `ff_100C_1v95` | `clk` | setup (related) | `u_cap/_844_/Q` -> `_519_/D` | 2.25563 |
| `ff_100C_1v95` | `hb_rwds_i` | setup (related) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 9.35313 |
| `ff_100C_1v95` | `clk` | hold (related) | `hb_rwds_i` -> `u_fsm/_2214_/D` | -0.44937 |
| `ff_100C_1v95` | `hb_rwds_i` | hold (related) | `u_cap/_950_/Q` -> `u_cap/_949_/D` | 0.314 |
| `ff_100C_1v95` | `clk` | setup (async) | `u_out/_44_/Q` -> `u_out/_24_/D` | 9.75428 |
| `ff_100C_1v95` | `hb_rwds_i` | setup (async) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 9.35313 |
| `ff_100C_1v95` | `hb_rwds_i` | hold (async) | `u_cap/_939_/Q` -> `u_cap/_943_/D` | 0.2392 |
| `ff_n40C_1v65` | `clk` | setup (related) | `u_cap/_844_/Q` -> `_519_/D` | -0.67122 |
| `ff_n40C_1v65` | `hb_rwds_i` | setup (related) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 8.69705 |
| `ff_n40C_1v65` | `clk` | hold (related) | `hb_rwds_i` -> `u_fsm/_2214_/D` | -0.60923 |
| `ff_n40C_1v65` | `hb_rwds_i` | hold (related) | `u_cap/_950_/Q` -> `u_cap/_949_/D` | 0.39171 |
| `ff_n40C_1v65` | `clk` | setup (async) | `u_out/_44_/Q` -> `u_out/_24_/D` | 9.67956 |
| `ff_n40C_1v65` | `hb_rwds_i` | setup (async) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 8.69705 |
| `ff_n40C_1v65` | `hb_rwds_i` | hold (async) | `u_cap/_939_/Q` -> `u_cap/_943_/D` | 0.30291 |
| `ff_n40C_1v76` | `clk` | setup (related) | `u_cap/_844_/Q` -> `_519_/D` | 0.88485 |
| `ff_n40C_1v76` | `hb_rwds_i` | setup (related) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 8.91177 |
| `ff_n40C_1v76` | `clk` | hold (related) | `hb_rwds_i` -> `u_fsm/_2214_/D` | -0.53343 |
| `ff_n40C_1v76` | `hb_rwds_i` | hold (related) | `u_cap/_950_/Q` -> `u_cap/_949_/D` | 0.35027 |
| `ff_n40C_1v76` | `clk` | setup (async) | `u_out/_44_/Q` -> `u_out/_24_/D` | 9.72322 |
| `ff_n40C_1v76` | `hb_rwds_i` | setup (async) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 8.91177 |
| `ff_n40C_1v76` | `hb_rwds_i` | hold (async) | `u_cap/_939_/Q` -> `u_cap/_943_/D` | 0.26723 |
| `ff_n40C_1v95` | `clk` | setup (related) | `u_cap/_844_/Q` -> `_519_/D` | 2.60207 |
| `ff_n40C_1v95` | `hb_rwds_i` | setup (related) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 9.15394 |
| `ff_n40C_1v95` | `clk` | hold (related) | `hb_rwds_i` -> `u_fsm/_2214_/D` | -0.4472 |
| `ff_n40C_1v95` | `hb_rwds_i` | hold (related) | `u_cap/_950_/Q` -> `u_cap/_949_/D` | 0.30135 |
| `ff_n40C_1v95` | `clk` | setup (async) | `u_out/_44_/Q` -> `u_out/_24_/D` | 9.76938 |
| `ff_n40C_1v95` | `hb_rwds_i` | setup (async) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 9.15394 |
| `ff_n40C_1v95` | `hb_rwds_i` | hold (async) | `u_cap/_939_/Q` -> `u_cap/_943_/D` | 0.22593 |
| `ss_n40C_1v76` | `clk` | setup (related) | `u_cap/_828_/Q` -> `_519_/D` | -6.76799 |
| `ss_n40C_1v76` | `hb_rwds_i` | setup (related) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 8.51824 |
| `ss_n40C_1v76` | `clk` | hold (related) | `hb_rwds_i` -> `u_fsm/_2214_/D` | -1.069 |
| `ss_n40C_1v76` | `hb_rwds_i` | hold (related) | `u_cap/_950_/Q` -> `u_cap/_949_/D` | 0.71397 |
| `ss_n40C_1v76` | `clk` | setup (async) | `u_out/_44_/Q` -> `u_out/_24_/D` | 9.41319 |
| `ss_n40C_1v76` | `hb_rwds_i` | setup (async) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 8.51824 |
| `ss_n40C_1v76` | `hb_rwds_i` | hold (async) | `u_cap/_939_/Q` -> `u_cap/_943_/D` | 0.55869 |
| `tt_025C_1v80` | `clk` | setup (related) | `u_cap/_828_/Q` -> `_519_/D` | -1.5614 |
| `tt_025C_1v80` | `hb_rwds_i` | setup (related) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 9.03789 |
| `tt_025C_1v80` | `clk` | hold (related) | `hb_rwds_i` -> `u_fsm/_2214_/D` | -0.67362 |
| `tt_025C_1v80` | `hb_rwds_i` | hold (related) | `u_cap/_950_/Q` -> `u_cap/_949_/D` | 0.46552 |
| `tt_025C_1v80` | `clk` | setup (async) | `u_out/_44_/Q` -> `u_out/_24_/D` | 9.63471 |
| `tt_025C_1v80` | `hb_rwds_i` | setup (async) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 9.03789 |
| `tt_025C_1v80` | `hb_rwds_i` | hold (async) | `u_cap/_939_/Q` -> `u_cap/_943_/D` | 0.3594 |
| `tt_100C_1v80` | `clk` | setup (related) | `u_cap/_844_/Q` -> `_519_/D` | -1.86471 |
| `tt_100C_1v80` | `hb_rwds_i` | setup (related) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 9.06982 |
| `tt_100C_1v80` | `clk` | hold (related) | `hb_rwds_i` -> `u_fsm/_2214_/D` | -0.6644 |
| `tt_100C_1v80` | `hb_rwds_i` | hold (related) | `u_cap/_950_/Q` -> `u_cap/_949_/D` | 0.47579 |
| `tt_100C_1v80` | `clk` | setup (async) | `u_out/_44_/Q` -> `u_out/_24_/D` | 9.62659 |
| `tt_100C_1v80` | `hb_rwds_i` | setup (async) | `u_cap/_956_/Q` -> `u_cap/_817_/D` | 9.06982 |
| `tt_100C_1v80` | `hb_rwds_i` | hold (async) | `u_cap/_939_/Q` -> `u_cap/_943_/D` | 0.36708 |

## Findings (negative in-window slack)

- **hold -1.069 ns worst** (at `ss_n40C_1v76`), `hb_rwds_i` -> `u_fsm/_2214_/D` -- related reading at `ff_100C_1v65` (-0.55785), `ff_100C_1v95` (-0.44937), `ff_n40C_1v65` (-0.60923), `ff_n40C_1v76` (-0.53343), `ff_n40C_1v95` (-0.4472), `ss_n40C_1v76` (-1.069), `tt_025C_1v80` (-0.67362), `tt_100C_1v80` (-0.6644). Design-iteration issue: #185.
- **setup -6.76799 ns worst** (at `ss_n40C_1v76`), `u_cap/_828_/Q` -> `_519_/D` -- related reading at `ss_n40C_1v76` (-6.76799), `tt_025C_1v80` (-1.5614). Design-iteration issue: #184.
- **setup -1.86471 ns worst** (at `tt_100C_1v80`), `u_cap/_844_/Q` -> `_519_/D` -- related reading at `ff_n40C_1v65` (-0.67122), `tt_100C_1v80` (-1.86471). Design-iteration issue: #184.

## Corners outside it (reported, not graded)

The PDK ships liberty at supplies decision 0004's window excludes. These 8 corners are recorded and printed, and the target does not fail on them, exactly as `make hyperram-sta` reports them.

**Related-clocks reading:**

| corner | supply (V) | setup slack (ns) | hold slack (ns) | fmax (MHz) | status |
|---|---|---|---|---|---|
| `ff_n40C_1v56` | 1.56 | -2.48384 | -0.69422 | 409.841 | constrained |
| `ss_100C_1v40` | 1.40 | -25.7613 | -1.70745 | 162.284 | constrained |
| `ss_100C_1v60` | 1.60 | -13.9717 | -1.21829 | 227.062 | constrained |
| `ss_n40C_1v28` | 1.28 | -73.0595 | -4.27708 | 65.513 | constrained |
| `ss_n40C_1v35` | 1.35 | -46.6379 | -3.05922 | 99.0636 | constrained |
| `ss_n40C_1v40` | 1.40 | -35.3624 | -2.50072 | 118.723 | constrained |
| `ss_n40C_1v44` | 1.44 | -28.7733 | -2.1782 | 124.029 | constrained |
| `ss_n40C_1v60` | 1.60 | -13.8019 | -1.42909 | 200.308 | constrained |

**Asynchronous-clock-groups reading:**

| corner | supply (V) | setup slack (ns) | hold slack (ns) | fmax (MHz) | status |
|---|---|---|---|---|---|
| `ff_n40C_1v56` | 1.56 | 8.44999 | 0.34168 | 409.841 | constrained |
| `ss_100C_1v40` | 1.40 | 4.63834 | 1.05469 | 162.284 | constrained |
| `ss_100C_1v60` | 1.60 | 8.44111 | 0.73147 | 227.062 | constrained |
| `ss_n40C_1v28` | 1.28 | -23.1896 | 2.13478 | 65.513 | constrained |
| `ss_n40C_1v35` | 1.35 | -9.18471 | 1.56669 | 99.0636 | constrained |
| `ss_n40C_1v40` | 1.40 | -3.35421 | 1.29678 | 118.723 | constrained |
| `ss_n40C_1v44` | 1.44 | 0.01228 | 1.13497 | 124.029 | constrained |
| `ss_n40C_1v60` | 1.60 | 7.71156 | 0.75191 | 200.308 | constrained |

## What was not timed

`constraint_completeness` is `incomplete` and the target does not gate on it. **Unclocked registers: 0 at every corner of both readings** -- declaring `hb_rwds_i` clocks the 143 registers the pre-layout record left unclocked (every flop under `u_cap/`, on `rwds_d`). 137 endpoints remain unconstrained, all boundary-condition gaps, in three classes:

- **Outputs without an output delay** -- `wb_ack`, `wb_stall`, `wb_dat_r[31:0]`, `cfg_rdata[15:0]`, `hb_ck`, `hb_cs_n`, `hb_reset_n`, `hb_dq_o[7:0]`, `hb_dq_oe`, `hb_rwds_o`, `hb_rwds_oe`: the spec states no `clk`-referenced output budget (above).
- **The DQ capture inputs** -- `hb_dq_i[7:0]` and the `u_cap/` data pins they feed: the one constraint that matters for read capture is the DQ-to-RWDS relationship, which the pinned klt cannot express (I/O delays are primary-clock-only, klayout-tools#7399). **The DQ-versus-RWDS capture check itself is therefore not in this record**; no local OpenSTA script or checker stands in for it. Its SPICE halves are the delay-chain campaign (#99) and the pad timing (#98, the I/O ring sibling).
- **Inputs without an input delay** -- `rst_n` and the `wb_*`/`cfg_*` ports: same absence of a stated figure (the Wishbone rows are functional-only in the draft spec).

### SPEF annotation gaps

The SPEF names 2379 of 2397 design nets; `annotation_complete` is `false`. The response's `design_nets_missing_sample` names all 18 uncorrelated nets: `VDD`, `u_fsm/_0955_`, `u_fsm/_0956_`, `u_fsm/_0957_`, `u_fsm/_0958_`, `u_fsm/_0959_`, `u_fsm/_0960_`, `u_fsm/_0961_`, `u_fsm/_0962_`, `u_fsm/_0963_`, `u_fsm/_0964_`, `u_fsm/_0965_`, `u_fsm/_0966_`, `u_fsm/_0967_`, `u_fsm/_0968_`, `u_fsm/_0969_`, `u_fsm/_0970_`, `u_fsm/_0971_`. Inspected against the committed DEF and routed netlist, the class is: `VDD` (a power net, which a signal SPEF does not extract) and 17 nets that are each the output of a `sky130_fd_sc_hd__conb_1` constant tie cell driving **no other pin** (e.g. `u_fsm/_0955_` is `u_fsm/_2216_`'s `HI` and nothing else) -- unrouted, unextracted, on no timed path. That they still force `annotation_complete: false` is klayout-tools#7367. Separately, `read_spef` discarded 1043 records with STA-1650/1648 warnings: every backslash-escaped bus-bracket net name (`clknet_*dly[N]`, `u_cap/mem[N][M]`, ...) is rejected by the reader while klt's own correlation un-escapes it, so those nets' parasitics -- including the CK delay-chain clock nets -- are not in the timing: klayout-tools#7401. The slack numbers above are real-parasitics only to that extent; DEF/SPEF hashes in this note's header pin the inputs.

## What this does not prove

This is the **post-route, all-core, strobe-clocked** timing half of what T1 item 5 asks a ratified spec to cite -- prepared so item 5 is one manifest edit away once #2 closes, and cited by **no** manifest item in this PR: which corners bind is the ratifier's (C4), and the tiers doc makes a verdict against a draft spec provisional. **No spec row is called met here.** Not proven, each for the stated reason: read capture at the pins and its margin (rows 11-12 -- the DQ/RWDS relationship is not expressible here, above), the write path (row 14 -- needs the pads), timing at the pins (row 19 -- pads and the core-to-pad seam are the I/O ring sibling's, compared by name in the repo README). The manifest, `spec/` and decision 0004 are untouched by this target.

Also not here: a settled strobe-domain modelling choice (#2, C4); the SDF-annotated bench run (#171); max-transition/max-capacitance repair (#173, open -- the DEF/SPEF may regenerate under it, and the freshness gate will catch that); any claim about 100 MHz.

<!-- sta-postroute-inputs def=sha256:cf7eb6c5021763aec3d753425386284d5fe0bfdc5c83df9c19edf1540df8be4d spef=sha256:f8d72e9d22153d8c6cdc0294f13db74bfde863888e9c39f90878bfc491c84117 request=sha256:bd55bccbb25afc29d7b260fec3ccdd598c1d7cb7d91b209323e1db061250763a request-async=sha256:eb626c14984b28ecc5543cfeaaa787926fb1e2aa6012dbb1b3dbab69c16325ae -->
