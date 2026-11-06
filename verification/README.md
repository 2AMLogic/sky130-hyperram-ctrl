# verification

Cold start, from a fresh checkout:

```
scripts/setup-env.sh        # pinned toolchain, see docs/environment.md
make -C verification        # model self-test + smoke test + controller benches
```

## Contents

- `smoke/` - cocotb + Icarus smoke test on the toolchain smoke counter.
- `hyperram_model/` - behavioural HyperBus-class device model (`model.py`)
  and its self-test (`test_model.py`, plain `unittest`, no simulator).
- `ctrl/` - cocotb + Icarus benches on `rtl/hyperram_ctrl` (zero-delay
  stand-ins for the sky130 cells): `hrbench.py` (pad-level model driver,
  Wishbone host, config port), one module per CT row, `test_random_traffic.py`
  (scoreboard) and `test_all.py` (aggregate for `klt functional-verification`).
  One module: `make -C verification/ctrl COCOTB_TEST_MODULES=test_row09_max_cs_low`.
- `../flow/functional-verification-ctrl.json` - the same benches as a
  `klt functional-verification` request (needs the `functional-verification`
  extra: `uvx --from "klayout-tools[functional-verification]==0.8.0" klt
  functional-verification flow/functional-verification-ctrl.json -o <dir>`),
  so item 5 can reuse them.
- `../attest/item9.json` / `../evidence/item9.json` - the T1 item-9
  inventory and its tool-produced envelope. The envelope hashes the raw bytes
  of every file in the inventory: after editing ANY listed file, regenerate it
  last with `klt signoff --attest 9 --inventory attest/item9.json -o
  evidence/item9.json` (and refresh the manifest hash and signoff record).

## Device model

Written here from the public interface definition cited in
`spec/device-model-params.md`; no vendor model is imported and no part is
named. It implements CA decode, variable latency with RWDS-signalled doubling,
fixed latency (CR0[3]), linear bursts, RWDS write masking, the register space
(ID0/ID1 read-only, CR0/CR1 writable), reset/power-up, and records a named
violation for tCSM, tCSHI, tCSS, tCSH, tCK, power-up and array bounds.
Skew knobs (`dq_skew_ns`, `rwds_skew_ns`) support the read-capture margin
sweep. Not modelled: wrapped bursts, the CR0 latency-field encoding, tIS/tIH.

**Parameters are placeholders.** The rows of `spec/device-model-params.md`
are still `TBD(src)` (#2), so `ModelParams` has no defaults and the self-test
passes values chosen for functional coverage, printing them on every run.
They are not datasheet numbers. Results are model-relative until #2 lands.

## Controller benches: what each module claims

| Row | Module | Claim |
|---|---|---|
| 3 | `test_row03_command_address` | CA is 6 bytes over 3 CK cycles; every host address bit and the register-space bit reach the device |
| 4 | `test_row04_latency` | variable latency 4..15, clamp below 4, doubling decision at the pins, fixed latency. Read data under doubled and fixed latency is checked (was `expect_fail`, fixed in #48) |
| 5 | `test_row05_bursts` | linear bursts of 1..16 beats, one transaction when it fits |
| 6 | `test_row06_write_mask` | all 16 byte-lane patterns, inside a burst, register writes unmasked |
| 7 | `test_row07_register_space` | ID0/CR0 read, CR0 write/readback, read-only ID0. ID1/CR1 are unreachable from the host (#48) |
| 8 | `test_row08_power_up` | CS# high and pads quiet for the programmed interval, interval is a register, short interval flagged by the model |
| 9 | `test_row09_max_cs_low` | bursts are split and re-issued, CS# low never exceeds tCSM across tCSM x latency, negative control (limit disabled) is flagged |
| 10 | `test_row10_rwds_extra_latency` | extra latency decided on the controller clock (insensitive to CA-phase RWDS skew); doubled-latency write correct. Doubled-latency read data is checked (was `expect_fail`, fixed in #48) |
| 13 | `test_row13_no_calibration` | absence check: no calibration port or status bit (spec: not applicable in v1) |
| 15 | `test_row15_host_interface` | one ack per accepted beat, stall, pipelining, cyc drop does not cancel |
| 16 | `test_row16_host_bursts` | long bursts with random host gaps lose nothing, split bursts |
| - | `test_random_traffic` | 120 random ops against a reference memory (seed printed, `RANDOM_SEED` / `RANDOM_OPS`) |

Row 9 relation, as verified: `cfg_tcsm = floor(tCSM / T) - 3` clocks keeps CS#
low within tCSM at 50 MHz for tCSM 30..64 clocks and latency 4..10; the model
first flags a violation at `+2` clocks over `tCSM / T`, so 3 is conservative
by 4 clocks.

## Gate-level run (`GL=1`)

`make -C verification/ctrl GL=1` runs the same 43 tests, unchanged (same 5 ns
sampling emulation), on the committed synthesized netlist
`sim/hyperram/records/hyperram_ctrl.netlist.v` with the PDK's own
`sky130_fd_sc_hd` functional models (`primitives.v`, `sky130_fd_sc_hd.v`, from
`$PDK_ROOT`, default `~/.ciel`, `-DFUNCTIONAL -DUNIT_DELAY=#0`). It does not
use `sky130_cells_behav.v`, so it also checks the hand stand-ins against the
real cell functions. Zero delay: no timing claim (SDF re-run is item 7).

- **Freshness guard**: before building, `flow/hyperram.py check` re-synthesizes
  (about 4 s) and aborts with `STALE` if the netlist differs. Use the pinned
  klt (`uvx --from "klayout-tools==0.8.0" ...` or the `.venv`); a newer klt
  reports a false STALE.
- **Negative control**: `make GL=1 GL_NETLIST=/tmp/bad.v` runs a substituted
  netlist and skips the guard. With `nand2_1` rewritten to `nor2_1` in a temp
  copy, tests fail from the first CA test on (run on this PR: failures, rc 2).
- **Internal names**: no test needs RTL-internal signals; they touch only
  top-level ports, which the netlist keeps.
- **Record**: `flow/functional-verification-ctrl-gl.json` is the klt request
  (absolute PDK model paths, since klt expands no variables; edit them if the
  PDK lives elsewhere). Its report is
  `sim/hyperram/records/functional-verification-ctrl-gl.report.json`, with the
  `inputs` block (netlist sha256 `9a4302c6…`, PDK model hashes) added by hand.
  Neither file is in `attest/item9.json`.

## What these benches do and do not claim

- **Model values are placeholders.** `hrbench.PLACEHOLDER` (printed at the
  start of every bench) is chosen for functional coverage, not taken from a
  datasheet (`spec/device-model-params.md` rows are `TBD(src)`, #2). Results are
  model-relative until #2 lands. tCSM is 1000 ns here.
- **No pad or CK timing.** The RTL runs with zero-delay cells, so the CK
  quarter-period shift (row 14) and the RWDS capture delay (rows 11, 12) are
  emulated by the bench: DQ/RWDS are sampled 5 ns after each CK edge and the
  model's RWDS is placed 5 ns after its DQ. Those rows are proved by SPICE and
  STA, not here.
- **Latency convention (changed in this PR).** The model now counts initial
  latency from the first CA clock, CA included (minimum 3; doubling doubles the
  whole count), which is how the controller counts. The earlier model counted
  from the end of CA and could not be reconciled with doubling. The source row
  is `TBD(src)`, so this is an assumption to confirm against the interface
  definition when #2 lands.
- **RWDS after CA.** The model drops RWDS low after CA when it signalled extra
  latency (public interface definition). The controller discards that edge by
  flushing the capture ring through `ST_LAT` (#48).
- Wrapped bursts, the CR0 latency-field encoding and tIS/tIH are not modelled.
