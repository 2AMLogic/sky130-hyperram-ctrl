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

- **#116**: sim/pad-sta: four record/driver polish items found reviewing PR #108

## In Progress

Issues currently being built (`loom:building`).

- **#106**: Bench-coverage assertion stops at verification/ctrl/: smoke and hyperram_model can still ship an undeclared bench
- **#111**: docs/ROADMAP.md: date the Now list to the header sha so merge-queue drift stops blocking review
- **#117**: Wire scripts/check_delay_chain_derive.py into check_ci.sh: a passing unit check nothing runs

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#119**: check: assert bench declarations for every verification/ subdirectory
- **#120**: docs: take Now/Next workflow state out of ROADMAP prose
- **#121**: ci: run the delay-chain derivation unit check in check_ci.sh

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#2**: Draft and ratify the target spec *(curated)*
- **#5**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#52**: Regenerate place-and-route and layout-dependent evidence after rd_flush ST_LAT fix (#48) *(curated)*
- **#100**: Correct three status lines the tree has outrun (spec/README decision list, target-spec proof note, README ladder) *(curated)*
- **#106**: Bench-coverage assertion stops at verification/ctrl/: smoke and hyperram_model can still ship an undeclared bench *(curated)*
- **#111**: docs/ROADMAP.md: date the Now list to the header sha so merge-queue drift stops blocking review *(curated)*
- **#113**: setup-env reports ngspice as '******'; delay_chain.py derive lacks the sim path's partial-collection and provenance guards *(curated)*
- **#116**: sim/pad-sta: four record/driver polish items found reviewing PR #108 *(curated)*

## Proposed (Architect / Hermit)

- **#70**: Remove drifted layout/toolchain.json inventory and stale bring-up stubs *(hermit)*
- **#78**: Trim the 175k-line dead_metal list from the committed klt extract record *(hermit)*
- **#84**: Remove vendored design-evidence-tiers.md: the pinned klt wheel ships a byte-identical copy *(hermit)*
- **#101**: Share the tap delay line: hr_dq_out and hr_rd_capture build the same 16-cell chain twice *(hermit)*
- **#103**: Stop restating six toolchain pins in docs/environment.md: a hand-maintained copy nothing checks *(hermit)*
- **#114**: Remove toolchain smoke flow: make smoke duplicates what the controller flow now exercises *(hermit)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 1 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 3 |
| Approved PRs awaiting merge | 0 |
| Curated | 8 |
| Architect / Hermit proposals | 6 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
