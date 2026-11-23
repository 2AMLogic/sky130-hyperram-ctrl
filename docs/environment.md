# Environment

`scripts/setup-env.sh` provisions a repo-local `.venv` and checks the host
tools. It exits non-zero, with a message, if any pin below is not met.
`sky130_fd_sc_hd` must be present: `sky130_fd_pr` alone leaves synthesis
unable to run (the trap recorded in sky130-modexp#193), so the script enables
both libraries and checks the tt/ss/ff liberty files and the LEF exist.
`sky130_fd_io` is enabled alongside them because the pad-liberty STA evidence
(`sim/pad-sta/`, answering [open question (a)](../spec/target-spec.md)) reads
its liberty and LEF: verified on a fresh provision, `ciel enable` with only
`-l sky130_fd_pr -l sky130_fd_sc_hd` links exactly those two libraries into
`libs.ref/` — `sky130_fd_io` ships in the PDK but is not linked unless
named, so the script also checks its `top_gpiov2` liberty and LEF exist.

## Pinned versions

Authoritative values live in `scripts/klt.sh` and `scripts/setup-env.sh`;
`setup-env.sh` exits non-zero when a pin is not met.

| Item | Pin | Where enforced |
|---|---|---|
| sky130A PDK (open_pdks) | `CIEL_SKY130_VERSION` in `scripts/setup-env.sh` | `ciel enable`; `sky130A/SOURCES` must name it |
| ciel | `CIEL_VERSION` in `scripts/setup-env.sh` | pip into `.venv` |
| klayout-tools (`klt`) | `scripts/klt.sh --pin` | defined once in `scripts/klt.sh`; pip into `.venv` from `scripts/klt.sh --pin` |
| Yosys (YoWASP wheel) | `YOWASP_YOSYS_VERSION`, `YOWASP_YOSYS_WASM_SHA256` in `scripts/setup-env.sh` | hash checked, linked as `.venv/bin/yosys`; `flow/hyperram.py` also refuses to synthesize or compare when the yosys that answered is not this version (exit 4) |
| cocotb | `COCOTB_VERSION` in `scripts/setup-env.sh` | pip into `.venv` |
| Icarus Verilog | `>= 12` (record names the exact version) | host; checked, not installed |
| Verilator | `>= 5` (lint only; record names the exact version) | host; checked, not installed |
| OpenROAD | must run (`openroad -version`); `klt sta` records the engine version | host; checked, not installed |
| ngspice | must run (`ngspice --version`); the delay-chain record names the version from its run report (`environment.engine_version`/`engine_build`), the batch worker's | host; checked, not installed |

Host tools are never installed by the script. `openroad` on the dispatch
workers is a Docker wrapper; it needs access to the Docker daemon. A wrapper
that is on `$PATH` but cannot run fails step 4 of the script.

## Cold-start check

The smoke counter the flow originally brought up on (`rtl/smoke/`) is gone
(issue #114): the controller flow now exercises every step it did, on the
real design. The
cheapest post-setup probe is `make hyperram-lint hyperram-check` — verilator
`--lint-only -Wall` (warnings fatal) on the controller RTL, then a
re-synthesis compared against the committed netlist. Both need the
`scripts/setup-env.sh` toolchain.

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
