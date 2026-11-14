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

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#2**: Draft and ratify the target spec
- **#91**: GL bench run leaves an untracked sim_build_gl/ directory (.gitignore covers sim_build/ only)

## In Progress

Issues currently being built (`loom:building`).

_None._

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

## Proposed (Architect / Hermit)

- **#70**: Remove drifted layout/toolchain.json inventory and stale bring-up stubs *(hermit)*
- **#78**: Trim the 175k-line dead_metal list from the committed klt extract record *(hermit)*
- **#84**: Remove vendored design-evidence-tiers.md: the pinned klt wheel ships a byte-identical copy *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 1 |
| Ready (`loom:issue`) | 2 |
| In Progress (`loom:building`) | 0 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 3 |
| Architect / Hermit proposals | 3 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
