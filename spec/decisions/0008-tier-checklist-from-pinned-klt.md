# 0008 The tier checklist is not vendored; the pinned klt alone selects it

Status: operator-ruled (rjwalters, `fleet:decide` round 20261121-r19, question
q103, 2026-11-23), made once for the twelve repos that asked the same
question. Issue #84; reverses the vendoring introduced by #4.

## Decision

The repo does not vendor `design-evidence-tiers.md`, and no caller passes
`--tiers-doc`. The pinned `klayout-tools` release alone selects the checklist:
`klt signoff` reads the copy its own wheel bundles
([docs/design-evidence-tiers.md](https://github.com/2AMLogic/klayout-tools/blob/v0.9.2/docs/design-evidence-tiers.md)
at tag `v0.9.2`). This reverses #4's criterion that "the `klt` version is
pinned in CI and in the vendored-doc provenance" with a vendored
`manifests/design-evidence-tiers.md`, on an explicit operator ruling, not an
agent decision.

Regenerating `manifests/sky130-hyperram-ctrl.signoff.json` without the flag
(at `klayout-tools==0.9.2`, this PR) changed exactly one line: `source_doc`
`manifests/design-evidence-tiers.md` → `docs/design-evidence-tiers.md`. The
`source_doc_content_hash` is unchanged — the 0.9.2 wheel's bundled doc is
byte-identical to the copy that was vendored — so no item text, verdict,
`t1_met_count` (7/11) or tier result moved.

## Consequences

- A `klt` pin bump is a two-part edit: `KLT_VERSION` in `scripts/klt.sh`, then
  the signoff record — no vendored doc to re-copy.
- The CI byte-compare of a fresh `klt signoff` render against the committed
  record (step 7 of `scripts/check_ci.sh`) is unchanged and is what catches a
  checklist change at a pin bump: a changed doc changes the fresh render and
  fails the compare until the record is regenerated and reviewed.
- Prose in `manifests/README.md` links the doc in klayout-tools at the pinned
  tag instead of describing a vendored copy.
