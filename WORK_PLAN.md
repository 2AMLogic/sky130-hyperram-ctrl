# Work Plan

Roadmap generated from GitHub label state by the Guide triage role.
Only the region between the markers is machine-generated.

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#2**: Draft and ratify the target spec
- **#52**: Regenerate place-and-route and layout-dependent evidence after rd_flush ST_LAT fix (#48)
- **#81**: Committed gate-level netlist does not reproduce under the pinned yosys, but item 1 records the freshness check as passed

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#81**: Committed gate-level netlist does not reproduce under the pinned yosys, but item 1 records the freshness check as passed

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#2**: Draft and ratify the target spec *(curated)*
- **#5**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#52**: Regenerate place-and-route and layout-dependent evidence after rd_flush ST_LAT fix (#48) *(curated)*
- **#81**: Committed gate-level netlist does not reproduce under the pinned yosys, but item 1 records the freshness check as passed *(curated)*

## Proposed (Architect / Hermit)

- **#70**: Remove drifted layout/toolchain.json inventory and stale bring-up stubs *(hermit)*
- **#78**: Trim the 175k-line dead_metal list from the committed klt extract record *(hermit)*
- **#84**: Remove vendored design-evidence-tiers.md: the pinned klt wheel ships a byte-identical copy *(hermit)*
- **#86**: Device model ignores the CK level it is passed: check edge polarity or drop the parameter *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 3 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 4 |
| Architect / Hermit proposals | 4 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
