# Work Plan

Roadmap generated from GitHub label state by the Guide triage role.
Only the region between the markers is machine-generated.

<!-- guide:plan-body:start -->
_Generated: 2026-11-23T21:15:00Z (snapshot; compare against live labels)_
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

- **#78**: Trim the 175k-line dead_metal list from the committed klt extract record
- **#173**: Routed controller: 612 max-transition, 22 max-capacitance and 1 antenna violation are uninvestigated (and grew in the last regeneration)
- **#179**: Retain and reconcile the P&R library-only pin rows for each routed corner
- **#182**: spec/target-spec.md:71 still says klt 0.8.0 cannot drive the pad-STA experiment (stale after the 0.9.2 pin bump)
- **#221**: The STA/STA-postroute gates still decode their inputs with the host locale (read side of #215)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#225**: fix: decode STA gate inputs as UTF-8 and bind the post-route note by bytes
- **#226**: docs(layout): record that per-pin library DRC rows are unretained; route structured rows upstream
- **#237**: docs(spec): note klt 0.9.2 macros[] support beside 0.8.0 pad-STA finding

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#235**: feat(lvs): trim dead_metal in the extract runner and check the extract record

## Proposed

Issues carrying `loom:curated`.

- **#2**: Draft and ratify the target spec *(curated)* *(held)*
- **#5**: Track the gap to T1 (klayout-tools design-evidence-tiers.md) *(curated)*
- **#78**: Trim the 175k-line dead_metal list from the committed klt extract record *(curated)*
- **#173**: Routed controller: 612 max-transition, 22 max-capacitance and 1 antenna violation are uninvestigated (and grew in the last regeneration) *(curated)*
- **#179**: Retain and reconcile the P&R library-only pin rows for each routed corner *(curated)*
- **#182**: spec/target-spec.md:71 still says klt 0.8.0 cannot drive the pad-STA experiment (stale after the 0.9.2 pin bump) *(curated)*
- **#221**: The STA/STA-postroute gates still decode their inputs with the host locale (read side of #215) *(curated)*
- **#236**: check_signoff_reasons.py: nothing mechanically asserts LEGITIMATE_REASONS still equals the pinned wheel's _REASON_* set *(curated)*

## Proposed (Architect / Hermit)

- **#78**: Trim the 175k-line dead_metal list from the committed klt extract record *(hermit)* *(runner trims dead_metal; committed record trimmed by the next `fleet-regen-layout.sh` run)*

## Epics

_None._

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 1 |
| Important | 1 |
| Ready (`loom:issue`, net of holds/building/merge-pending) | 0 |
| In Progress (`loom:building`) | 5 |
| PRs awaiting review | 3 |
| Approved PRs awaiting merge | 1 |
| Curated | 8 |
| Architect / Hermit proposals | 0 |
| Active epics | 0 |
<!-- guide:plan-body:end -->
