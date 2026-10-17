# sky130-hyperram-ctrl — agent instructions

Open-source canary block: a HyperBus-class memory controller and its I/O
timing on SkyWater sky130, designed and verified by AI agents. **Digital,
with an I/O timing path** that may need custom cells, so both flows apply.

- **PDK**: SkyWater sky130 (open PDK, google/skywater-pdk), `sky130_fd_sc_hd`
  standard cells and the sky130 I/O library. Digital: cocotb + Icarus,
  Yosys, OpenROAD. Analog (strobe delay, pad timing): xschem + ngspice.
  Layout, DRC, and LVS through klayout-tools (`klt`) in both cases.
- **Read capture at the pins is the point, and the risk.** RWDS arrives
  edge-aligned with read data; the controller must delay it into the data
  eye through the sky130 pads, across PVT, with no DLL in v1. That is only
  provable with a timing model that includes the pads and the core-to-pad
  seam. If static timing cannot see through the pad cells, characterize them
  in ngspice across corners and say exactly what was assumed. Expect the
  tools to be weakest here and file accordingly.
- **The device model is written here.** Verification runs against a
  behavioural memory model written in this repo from the public interface
  definition, with its timing parameters cited. Do not import a
  vendor-licensed device model, and do not name or target a particular
  memory part.
- **Scope discipline.** This repo has no `consumes:` edge. Do not design an
  I/O ring or a PLL here. Specify what the pads must provide (drive,
  input delay and its spread, output enable timing) and what the clock must
  be, and compare against the sibling that builds each — the sky130 I/O
  ring canary opened alongside this repo and `sky130-pll` — by name and
  commit. A gap goes into the spec and is filed on the sibling (see
  `2am/REUSE.md`).
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue at
  `2AMLogic/klayout-tools` describing the tool gap generically — that tracker
  is scoped to the tool, so keep design-specific detail out of it and describe
  the gap, not the design.
- **Verification is the product**: no claim without a testbench. Every timing
  claim names its corner; recorded results are append-only evidence.
- Spec changes go through `spec/` with a decision record; agents do not relax
  the ratified spec to make results pass.
- **50 MHz is the target.** 25 MHz is the fallback and 100 MHz a stretch. Do
  not let 100 MHz requirements (a calibrated delay line, a DLL) drive
  architecture before 50 MHz closes at the pins.
- HyperBus and HyperRAM are used only to name the interface. Do not claim
  compatibility certification with any device.

<!-- BEGIN LOOM ORCHESTRATION -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration — see the Loom repository for the full guide (roles, labels, worktrees, configuration). When installed, Loom also writes a locally-substituted copy of that guide to `.loom/CLAUDE.md`.

Work is coordinated through `loom:` labels on issues and pull requests, and the same roles run either under `loom-daemon` or by hand in an attended session — daemon mode is optional. Create the labels once with `.loom/scripts/sync-labels.sh` (an install ships `.github/labels.yml` but does not create the labels on the forge). A pull request ready for review carries `loom:review-requested`; Judge reviews it and applies `loom:pr` (approved) or `loom:changes-requested`; Doctor fixes a `loom:changes-requested` pull request and returns it to `loom:review-requested`. Only a `loom:pr` pull request gets merged, and always via this repo's merge script (`.loom/scripts/merge-pr.sh`) — never a raw forge merge command such as `gh pr merge`. Full state machine: `.loom/docs/label-state-machine.md`.
<!-- END LOOM ORCHESTRATION -->
