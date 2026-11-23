# Work Plan

Roadmap generated from GitHub label state by the Guide triage role.
Only the region between the markers is machine-generated.

<!-- guide:plan-body:start -->
_Generated: 2026-11-21T09:25:22Z (snapshot; compare against live labels)_
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#2**: Draft and ratify the target spec *(held)*
- **#170**: Bump the klayout-tools pin 0.8.0 -> 0.9.2 and regenerate the records and signoff render under it

## Important

`loom:important`; taken before unlabelled work.

- **#173**: Routed controller: 612 max-transition, 22 max-capacitance and 1 antenna violation are uninvestigated (and grew in the last regeneration)

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#170**: Bump the klayout-tools pin 0.8.0 -> 0.9.2 and regenerate the records and signoff render under it
- **#173**: Routed controller: 612 max-transition, 22 max-capacitance and 1 antenna violation are uninvestigated (and grew in the last regeneration)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#175**: data: regenerate the layout-chain records and GL report at klt 0.9.2

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#2**: Draft and ratify the target spec *(curated)* *(held)*
- **#5**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#170**: Bump the klayout-tools pin 0.8.0 -> 0.9.2 and regenerate the records and signoff render under it *(curated)*
- **#173**: Routed controller: 612 max-transition, 22 max-capacitance and 1 antenna violation are uninvestigated (and grew in the last regeneration) *(curated)*

## Proposed (Architect / Hermit)

- **#70**: Remove drifted layout/toolchain.json inventory and stale bring-up stubs *(hermit)* *(held)*
- **#78**: Trim the 175k-line dead_metal list from the committed klt extract record *(hermit)* *(held)*
- **#84**: Remove vendored design-evidence-tiers.md: the pinned klt wheel ships a byte-identical copy *(hermit)* *(held)*
- **#103**: Stop restating six toolchain pins in docs/environment.md: a hand-maintained copy nothing checks *(hermit)* *(held)*
- **#114**: Remove toolchain smoke flow: make smoke duplicates what the controller flow now exercises *(hermit)* *(held)*
- **#160**: Replace check_pdk_root.py (329-line shell parser) with a 4-line runtime assertion *(hermit)* *(held)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 2 |
| Important | 1 |
| Ready (`loom:issue`, net of holds/building/merge-pending) | 0 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 0 |
| Curated | 4 |
| Architect / Hermit proposals | 6 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
