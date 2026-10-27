# verification

Cold start, from a fresh checkout:

```
scripts/setup-env.sh        # pinned toolchain, see docs/environment.md
make -C verification        # model self-test + cocotb smoke test
```

## Contents

- `smoke/` - cocotb + Icarus smoke test on the toolchain smoke counter.
- `hyperram_model/` - behavioural HyperBus-class device model (`model.py`)
  and its self-test (`test_model.py`, plain `unittest`, no simulator).

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

## Status

Controller benches (one module per CT row of `spec/target-spec.md`, random
traffic scoreboard), the `klt functional-verification` request and the T1
item-9 attestation wait on the controller RTL (#13).
