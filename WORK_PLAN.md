# Work Plan

Roadmap generated from GitHub label state by the Guide triage role.
Only the region between the markers is machine-generated.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#2**: Draft and ratify the target spec

## Important

`loom:important`; taken before unlabelled work.

- **#52**: Regenerate place-and-route and layout-dependent evidence after rd_flush ST_LAT fix (#48)
- **#89**: flow/hyperram.py yosys gate checks the engine version string, not the pinned wasm build
- **#97**: Record pre-layout STA of the current controller netlist at every shipped sky130_fd_sc_hd corner
- **#98**: Answer spec open question (a): do the pinned PDK's sky130_fd_io liberty views give OpenSTA arcs through the pad cells?
- **#99**: Answer spec open question (b): ngspice per-tap delay of the RWDS delay chain across the decision-0004 corners

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#91**: GL bench run leaves an untracked sim_build_gl/ directory (.gitignore covers sim_build/ only)
- **#93**: Derive the controller bench list from disk: three hand-maintained copies, none checked

## In Progress

Issues currently being built (`loom:building`).

- **#89**: flow/hyperram.py yosys gate checks the engine version string, not the pinned wasm build

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#95**: fix: gate synthesis on the pinned yosys.wasm hash, not just its version
- **#96**: docs: roadmap as of 2026-11-13

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#2**: Draft and ratify the target spec *(curated)*
- **#5**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#52**: Regenerate place-and-route and layout-dependent evidence after rd_flush ST_LAT fix (#48) *(curated)*
- **#89**: flow/hyperram.py yosys gate checks the engine version string, not the pinned wasm build *(curated)*
- **#91**: GL bench run leaves an untracked sim_build_gl/ directory (.gitignore covers sim_build/ only) *(curated)*
- **#98**: Answer spec open question (a): do the pinned PDK's sky130_fd_io liberty views give OpenSTA arcs through the pad cells? *(curated)*

## Proposed (Architect / Hermit)

- **#70**: Remove drifted layout/toolchain.json inventory and stale bring-up stubs *(hermit)*
- **#78**: Trim the 175k-line dead_metal list from the committed klt extract record *(hermit)*
- **#84**: Remove vendored design-evidence-tiers.md: the pinned klt wheel ships a byte-identical copy *(hermit)*
- **#101**: Share the tap delay line: hr_dq_out and hr_rd_capture build the same 16-cell chain twice *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 5 |
| Ready (`loom:issue`) | 2 |
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 2 |
| Approved PRs awaiting merge | 0 |
| Curated | 6 |
| Architect / Hermit proposals | 4 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
