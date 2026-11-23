# Work Plan

Roadmap generated from GitHub label state by the Guide triage role.
Only the region between the markers is machine-generated.

<!-- guide:plan-body:start -->
_Generated: 2026-11-23T15:10:53Z (snapshot; compare against live labels)_
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#2**: Draft and ratify the target spec *(held)*

## Important

`loom:important`; taken before unlabelled work.

- **#173**: Routed controller: 612 max-transition, 22 max-capacitance and 1 antenna violation are uninvestigated (and grew in the last regeneration)

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#173**: Routed controller: 612 max-transition, 22 max-capacitance and 1 antenna violation are uninvestigated (and grew in the last regeneration)
- **#193**: No automated regression test for the runtime PDK_ROOT assertion in fleet-regen-layout.sh
- **#214**: check_signoff_reasons.py: re-derive the klt unmet-reason inventory and decide whether unverifiable_provenance belongs in the reject-list
- **#215**: Make sta()/sta-postroute note writers emit the canonical bytes their CI gates compare against

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#217**: fix: derive check_signoff_reasons fixture list from klt 0.9.2 _REASON_* constants
- **#220**: fix: make STA record producers write explicit UTF-8 bytes

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#219**: test: drive the fleet PDK_ROOT runtime guard over fixture shapes in CI

## Proposed

Issues carrying `loom:curated`.

- **#2**: Draft and ratify the target spec *(curated)* *(held)*
- **#5**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#173**: Routed controller: 612 max-transition, 22 max-capacitance and 1 antenna violation are uninvestigated (and grew in the last regeneration) *(curated)*
- **#182**: spec/target-spec.md:71 still says klt 0.8.0 cannot drive the pad-STA experiment (stale after the 0.9.2 pin bump) *(curated)* *(held)*
- **#193**: No automated regression test for the runtime PDK_ROOT assertion in fleet-regen-layout.sh *(curated)*
- **#214**: check_signoff_reasons.py: re-derive the klt unmet-reason inventory and decide whether unverifiable_provenance belongs in the reject-list *(curated)*
- **#215**: Make sta()/sta-postroute note writers emit the canonical bytes their CI gates compare against *(curated)*

## Proposed (Architect / Hermit)

- **#78**: Trim the 175k-line dead_metal list from the committed klt extract record *(hermit)* *(held)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 1 |
| Ready (`loom:issue`, net of holds/building/merge-pending) | 0 |
| In Progress (`loom:building`) | 4 |
| PRs awaiting review | 2 |
| Approved PRs awaiting merge | 1 |
| Curated | 7 |
| Architect / Hermit proposals | 1 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
