# Block manifest and tier-verdict record

- **`sky130-hyperram-ctrl.json`**: block manifest for
  [`klt signoff --manifest`](https://github.com/2AMLogic/klayout-tools/blob/main/docs/cli/signoff.md).
  `kind: digital`; `evidence."10"` cites `evidence/item10.json`, the
  `klt signoff --attest 10` envelope for `attest/item10.json`;
  `evidence."3"` cites the `klt drc` report (see Item-3 DRC evidence below).
- **`sky130-hyperram-ctrl.signoff.json`**: the committed verdict of record,
  the output of `klt signoff --manifest ... --format json`. CI re-renders it
  and byte-compares; whoever changes the manifest, the vendored doc, or the
  `klt` pin regenerates it in the same PR:

  ```
  uvx --from klayout-tools==0.8.0 klt signoff \
      --manifest manifests/sky130-hyperram-ctrl.json \
      --tiers-doc manifests/design-evidence-tiers.md \
      --format json > manifests/sky130-hyperram-ctrl.signoff.json
  ```

  Exit 3 (grader ran, some item unmet) is expected and accepted.
- **`design-evidence-tiers.md`**: vendored from
  [klayout-tools](https://github.com/2AMLogic/klayout-tools)
  `docs/design-evidence-tiers.md` at tag `v0.8.0`
  (commit `c572046be644e0407f693f2410f3abb799d68a3a`). Its license is
  klayout-tools', not this repo's.

## klt pin

`klayout-tools==0.8.0`, set in `scripts/check_ci.sh` (`KLT_VERSION`) and in
the install step of `.github/workflows/ci.yml`. Bump both, the vendored doc
and the signoff record together.

Two consecutive local runs at 0.8.0 produced byte-identical output.

## Item-3 DRC evidence

`evidence."3"` cites `layout/records/drc.report.json` directly (the `klt drc`
JSON report is itself the envelope). It is `status: clean`,
`violation_count: 0`, input hash `sha256:b23e5f6c85c6e8546bce2b5d4d6c7c38521c692e2f3603dba368e126aecd57d6`
(the GDS item 2 cites), deck `sky130` (curated, released) with content hash
`sha256:ba0f97887e3d231aec8b54f1f52f2941ded0228f0234b6759712bcaca0e942e6`,
`klt 0.8.0`, KLayout 0.30.12. Two consecutive runs were byte-identical.

Re-run (about one minute, no PDK needed) and re-check:

```
uvx --from klayout-tools==0.8.0 klt drc --deck sky130 --format json \
    layout/records/hyperram_ctrl.gds > layout/records/drc.report.json
uvx --from klayout-tools==0.8.0 klt drc --check layout/records/drc.report.json
```

`make drc` does the same. A clean verdict is bounded by what the deck
covers. The three disclosure fields, quoted verbatim from the report's
`coverage` block (claimant-enforced; `klt signoff` does not check them):

- `coverage.layers_in_stream_without_rules` (drawn in the GDS, no rule in the deck):
  `["64/5", "64/16", "64/59", "66/15", "67/5", "67/16", "68/5", "68/16", "70/5", "70/16", "72/5", "72/16", "81/4", "81/23", "83/44", "122/16", "235/4", "236/0"]`
- `coverage.rules_skipped` (in the deck, not evaluated by this run; the report's
  `inapplicable` list gives the reason `no_applicable_geometry` for each):
  `["areaid_re.ongrid.1", "capm.enclosing.via3.1", "capm.separation.via3.1", "capm.space.1", "capm.width.1", "capm2.enclosing.via4.1", "capm2.separation.via4.1", "capm2.space.1", "capm2.width.1", "dnwell.angle.1", "dnwell.ongrid.1", "hvi.angle.1", "hvi.ongrid.1", "hvntm.angle.1", "hvntm.ongrid.1", "hvtr.angle.1", "hvtr.ongrid.1", "lvtn.angle.1", "lvtn.ongrid.1", "met3.enclosing.capm.1", "met4.enclosing.capm2.1", "mf.angle.1", "mf.ongrid.1", "ncm.angle.1", "ncm.ongrid.1", "nsm.angle.1", "nsm.ongrid.1", "nwell.enclosed.hvi.1", "pad.angle.1", "pad.ongrid.1", "pwbm.angle.1", "pwbm.ongrid.1", "pwde.angle.1", "pwde.ongrid.1", "pwell_rs.angle.1", "pwell_rs.ongrid.1", "rpm.angle.1", "rpm.ongrid.1", "rpm.width.1", "tunm.angle.1", "tunm.ongrid.1", "uhvi.angle.1", "uhvi.ongrid.1", "urpm.width.1", "vhvi.angle.1", "vhvi.ongrid.1", "vpp.angle.1", "vpp.ongrid.1"]`
- `coverage.deck_scope` (DRM chapters the deck transcribes at all):
  `["cap2m", "capm", "ct", "difftap", "li", "licon", "m1", "m2", "m3", "m4", "m5", "npc", "nsdm", "nwell", "poly", "psdm", "rpm", "urpm", "via", "via2", "via3", "via4", "x"]`

Not covered by this evidence: rules outside `deck_scope`, the
`unmodeled_rules` the report lists, and the foundry's own signed-off deck (T2).

## Item-10 attestation

The envelope pins the raw-byte hashes of `README.md`, `LICENSE`,
`.github/workflows/ci.yml` and `attest/item10.json`, so any later edit to one
of them (a pin mention in the README included) makes
`klt signoff --attest 10 ... --check` fail in CI until it is regenerated, and
the manifest's `content_hash` (the inventory's hash) and the signoff record
are refreshed. Any PR touching those files must do all three, in this order:

```
uvx --from klayout-tools==0.8.0 klt signoff --attest 10 \
    --inventory attest/item10.json -o evidence/item10.json
# if attest/item10.json changed, update evidence."10".content_hash in the
# manifest to provenance.input.content_hash of the new envelope, then:
uvx --from klayout-tools==0.8.0 klt signoff \
    --manifest manifests/sky130-hyperram-ctrl.json \
    --tiers-doc manifests/design-evidence-tiers.md \
    --format json > manifests/sky130-hyperram-ctrl.signoff.json
```

`make smoke` is declared `local_only`: it needs the `scripts/setup-env.sh`
toolchain, so `--check` on the CI runner skips it and reports its committed
outcome.
