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
| klayout-tools (`klt`) | `0.8.0` | pip into `.venv` |
| Yosys (YoWASP wheel) | `0.68.0.0.post1208`, `yosys.wasm` sha256 `e37a7e65e3fa4efbbd64a9c1b0e906be16cdc6c4d5273109d17537f78449f38c` | hash checked, linked as `.venv/bin/yosys` |
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
