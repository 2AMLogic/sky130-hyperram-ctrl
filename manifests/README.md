# Block manifest and tier-verdict record

- **`sky130-hyperram-ctrl.json`**: block manifest for
  [`klt signoff --manifest`](https://github.com/2AMLogic/klayout-tools/blob/main/docs/cli/signoff.md).
  `kind: digital`; the `evidence` map is empty on purpose, no T1 evidence
  has been produced yet.
- **`sky130-hyperram-ctrl.signoff.json`**: the committed verdict of record,
  the output of `klt signoff --manifest ... --format json`. CI re-renders it
  and byte-compares; whoever changes the manifest, the vendored doc, or the
  `klt` pin regenerates it in the same PR:

  ```
  uvx --from klayout-tools==0.7.0 klt signoff \
      --manifest manifests/sky130-hyperram-ctrl.json \
      --tiers-doc manifests/design-evidence-tiers.md \
      --format json > manifests/sky130-hyperram-ctrl.signoff.json
  ```

  Exit 3 (grader ran, some item unmet) is expected and accepted.
- **`design-evidence-tiers.md`**: vendored from
  [klayout-tools](https://github.com/2AMLogic/klayout-tools)
  `docs/design-evidence-tiers.md` at tag `v0.7.0`
  (commit `0e2362bda7309829398a35d54efaa989d5806065`). Its license is
  klayout-tools', not this repo's.

## klt pin

`klayout-tools==0.7.0`, set in `scripts/check_ci.sh` (`KLT_VERSION`) and in
the install step of `.github/workflows/ci.yml`. Bump both, the vendored doc
and the signoff record together.

Two consecutive local runs at 0.7.0 produced byte-identical output.
