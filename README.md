# sky130-hyperram-ctrl

A memory controller for the HyperBus-class interface — an 8-bit
double-data-rate bus with a read/write data strobe — on the
[SkyWater sky130](https://github.com/google/skywater-pdk) open PDK,
including the I/O timing at the pads, designed by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source flow: cocotb + Icarus, Yosys and OpenROAD for the controller,
xschem + ngspice for the I/O timing path.

**Status: just opened, specification phase.** Nothing is designed yet.

**Built agent-native.** Every specification, decision record, testbench, and
line of documentation here is produced by AI agents working from a ratified
spec and an append-only evidence trail — not human-authored work that agents
merely assisted with. Verification is the product: every claim traces to a
recorded result. Where the agents hit friction with the open-source tooling —
most often [klayout-tools](https://github.com/2AMLogic/klayout-tools) — that
friction is filed as a public issue against the tool itself, so the fix
benefits everyone using sky130, not just this repo.

## Setup and smoke flow

```bash
./scripts/setup-env.sh   # pinned klt, Yosys, cocotb, sky130A + sky130_fd_sc_hd; checks host tools
make smoke               # lint, cocotb sim, synthesis, three-corner STA on rtl/smoke/ (not the design)
```

Pins and the flow steps are in [docs/environment.md](docs/environment.md);
the run record lands in `sim/smoke/records/`.

## Why this block, on this node

The interface is small — chip select, a clock, eight DQ lines, a strobe
(RWDS) and reset — and the protocol is simple: a 48-bit command/address
phase over three clock cycles, a latency count, then data on both clock
edges. RWDS carries three meanings: during command/address it signals extra
latency, during writes it is the data mask, and during reads the memory
drives it edge-aligned with the data.

That last part is the canary. Capturing read data means delaying a strobe
that arrives edge-aligned with the data, through the sky130 I/O pads, by a
fraction of a bit time that holds across process, voltage and temperature —
without a delay-locked loop in v1. A controller's RTL is easy to verify in
simulation; whether its read capture works at the pins is a question about
pad delays, their spread, and the core-to-pad timing seam, and the open
flow has to answer it with a static timing model that includes the pads.
Any source-synchronous DDR interface on sky130 meets the same seam.

## Scope

- **In scope**: the protocol controller (command/address, latency handling
  including RWDS-signalled extra latency, burst reads and writes with
  masks, register access, reset sequencing); the DDR output path; read
  capture with a calibrated or fixed strobe delay; a host bus interface;
  I/O timing analysis including the pads.
- **From siblings**: the pads themselves, if the sky130 I/O ring canary
  provides them, and the clock, from a sibling PLL. This repo has no
  `consumes:` edge yet; it specifies both interfaces and stops.
- **Not in scope**: the memory device. Verification uses a behavioural
  device model written here from the public interface definition.

## Target specification (DRAFT — engineering to ratify, see issue #2)

| Parameter | Target | Fallback | Stretch |
|---|---|---|---|
| Bus clock | 50 MHz (100 MB/s) | 25 MHz | 100 MHz |
| I/O voltage | 3.3 V-class I/O pads | — | 1.8 V-class devices |
| Read capture | fixed, PVT-margined strobe delay | slower clock | calibrated delay line |
| Host bus | Wishbone-class, 32-bit | — | AXI-class |
| Bursts | linear bursts with write masking | single-word | wrapped bursts |
| Timing (all sky130_fd_sc_hd corners) | setup/hold met at the pins, pads included | — | — |
| Signoff | DRC + LVS clean | — | — |

Maturity ladder: spec ratified → controller verified against the device
model → pin-level timing closed across corners, pads included → layout
DRC/LVS-clean → shuttle seat → measured silicon. **Current position:
pre-spec.**

## Repo layout

```
spec/          ratified spec + decision records
rtl/           controller, DDR I/O wrappers, host interface
verification/  cocotb testbenches + behavioural device model
design/        custom strobe-delay or I/O cells, if any (xschem)
sim/           I/O timing studies + PVT corner results (ngspice)
layout/        GDS + DRC/LVS reports (klayout-tools driven)
measurements/  silicon characterization (empty until tape-out)
```

## Reproduce

```
npm run check:ci      # the CI gate: JSON validity, README links, item-10 attestation, klt signoff record
```

This runs `scripts/check_ci.sh`, the same script `.github/workflows/ci.yml`
runs. It uses `klt` pinned to `klayout-tools==0.8.0` (falling back to
`uvx --from klayout-tools==0.8.0 klt` if the installed `klt` differs). The
tier verdict of record is `manifests/sky130-hyperram-ctrl.signoff.json`; see
[manifests/README.md](manifests/README.md).

T1 item 10 (repo hygiene) is attested by `attest/item10.json` and the
tool-produced envelope `evidence/item10.json`. CI re-checks it; after editing
`README.md`, `LICENSE`, `.github/workflows/ci.yml` or the inventory, regenerate:

```
uvx --from klayout-tools==0.8.0 klt signoff --attest 10 \
    --inventory attest/item10.json -o evidence/item10.json
```

## License

Apache License 2.0 — see [LICENSE](LICENSE). HyperBus and HyperRAM are
trademarks of their owner; they are used here only to name the interface.
