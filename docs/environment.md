# Environment

`scripts/setup-env.sh` provisions a repo-local `.venv` and checks the host
tools. It exits non-zero, with a message, if any pin below is not met.
`sky130_fd_sc_hd` must be present: `sky130_fd_pr` alone leaves synthesis
unable to run (the trap recorded in sky130-modexp#193), so the script enables
both libraries and checks the tt/ss/ff liberty files and the LEF exist.

## Pinned versions

| Item | Pin | Where enforced |
|---|---|---|
| sky130A PDK (open_pdks) | `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` | `ciel enable`; `sky130A/SOURCES` must name it |
| ciel | `2.6.1` | pip into `.venv` |
| klayout-tools (`klt`) | `0.8.0` | defined once in `scripts/klt.sh`; pip into `.venv` from `scripts/klt.sh --pin` |
| Yosys (YoWASP wheel) | `0.68.0.0.post1208`, `yosys.wasm` sha256 `e37a7e65e3fa4efbbd64a9c1b0e906be16cdc6c4d5273109d17537f78449f38c` | hash checked, linked as `.venv/bin/yosys`; `flow/hyperram.py` also refuses to synthesize or compare when the yosys that answered is not this version (exit 4) |
| cocotb | `2.0.1` | pip into `.venv` |
| Icarus Verilog | `>= 12` (record names the exact version) | host; checked, not installed |
| Verilator | `>= 5` (lint only; record names the exact version) | host; checked, not installed |
| OpenROAD | must run (`openroad -version`); `klt sta` records the engine version | host; checked, not installed |

Host tools are never installed by the script. `openroad` on the dispatch
workers is a Docker wrapper; it needs access to the Docker daemon. A wrapper
that is on `$PATH` but cannot run fails step 4 of the script.

## Smoke flow

`make smoke` runs, on `rtl/smoke/smoke_counter.v` (not part of the design):

1. `smoke-lint`: `verilator --lint-only -Wall` (warnings are fatal).
2. `smoke-sim`: cocotb + Icarus (`verification/smoke/`).
3. `smoke-synth`: `klt synthesize` to `sky130_fd_sc_hd`; netlist and stat
   report in `sim/smoke/records/`.
4. `smoke-sta`: `klt sta` on that netlist at `tt_025C_1v80`, `ss_100C_1v60`,
   `ff_n40C_1v95` (20 ns clock, ideal clock, no wire load), failing unless
   setup and hold slack are both non-negative.
5. `smoke-record`: `sim/smoke/records/RECORD.md` with the PDK revision and
   every tool version.

`PDK=sky130A` is exported by the Makefile; without it `klt` may resolve
another installed PDK variant (klayout-tools#3748).

## Controller STA

`make hyperram-sta` runs `klt sta` on the committed controller netlist
(`sim/hyperram/records/hyperram_ctrl.netlist.v`) at every `sky130_fd_sc_hd`
liberty corner the pinned PDK ships — 16 distinct corners (18 `.lib` files, two
of which are `_ccsnoise` variants of corners already in the set) — in one
request/response round trip, from `flow/sta-hyperram.json`: `clk` at 20 ns, no
other constraint. It needs `openroad` and the PDK, takes about a minute, and
does no place-and-route, so it is cheap enough to re-run after any
re-synthesis; `make layout` (~25 min) is the separate post-route path.

The response is written through unmodified to `sim/hyperram/records/sta.json`,
with the in/out-of-window split, the assumptions and what the record does not
prove generated beside it in `sim/hyperram/records/STA.md`. The target fails on
a negative setup or hold slack only at a corner inside decision 0004's
1.62–1.98 V core supply window; the corners outside it are recorded and printed
but not graded, the way `layout/README.md` already reports the place-and-route
numbers. It also fails if the corner set answered is not the one requested or if
a cell yosys left as a blackbox is absent from a corner's liberty, and it
deliberately does **not** gate on `constraint_completeness` — the read-capture
registers are clocked off the delayed strobe, which a single-`clock_port`
request cannot constrain, so `incomplete` is the expected and recorded state.
