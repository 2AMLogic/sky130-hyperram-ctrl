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
- **#98**: Answer spec open question (a): do the pinned PDK's sky130_fd_io liberty views give OpenSTA arcs through the pad cells?
- **#99**: Answer spec open question (b): ngspice per-tap delay of the RWDS delay chain across the decision-0004 corners

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#91**: GL bench run leaves an untracked sim_build_gl/ directory (.gitignore covers sim_build/ only)
- **#98**: Answer spec open question (a): do the pinned PDK's sky130_fd_io liberty views give OpenSTA arcs through the pad cells?
- **#99**: Answer spec open question (b): ngspice per-tap delay of the RWDS delay chain across the decision-0004 corners

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#96**: docs: roadmap as of 2026-11-13
- **#108**: evidence: pad-liberty STA record - OpenSTA sees through the pads, no in-window fast corner
- **#109**: feat: ngspice 45-corner RWDS delay-chain campaign; spec question (b) answered at the schematic level

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#104**: chore: ignore the GL=1 cocotb build directory, not just sim_build/

## Proposed

Issues carrying `loom:curated`.

- **#2**: Draft and ratify the target spec *(curated)*
- **#5**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#52**: Regenerate place-and-route and layout-dependent evidence after rd_flush ST_LAT fix (#48) *(curated)*
- **#91**: GL bench run leaves an untracked sim_build_gl/ directory (.gitignore covers sim_build/ only) *(curated)*
- **#98**: Answer spec open question (a): do the pinned PDK's sky130_fd_io liberty views give OpenSTA arcs through the pad cells? *(curated)*
- **#99**: Answer spec open question (b): ngspice per-tap delay of the RWDS delay chain across the decision-0004 corners *(curated)*

## Proposed (Architect / Hermit)

- **#70**: Remove drifted layout/toolchain.json inventory and stale bring-up stubs *(hermit)*
- **#78**: Trim the 175k-line dead_metal list from the committed klt extract record *(hermit)*
- **#84**: Remove vendored design-evidence-tiers.md: the pinned klt wheel ships a byte-identical copy *(hermit)*
- **#101**: Share the tap delay line: hr_dq_out and hr_rd_capture build the same 16-cell chain twice *(hermit)*
- **#103**: Stop restating six toolchain pins in docs/environment.md: a hand-maintained copy nothing checks *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 3 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 3 |
| Approved PRs awaiting merge | 1 |
| Curated | 6 |
| Architect / Hermit proposals | 5 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
