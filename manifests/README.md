# Block manifest and tier-verdict record

- **`sky130-hyperram-ctrl.json`**: block manifest for
  [`klt signoff --manifest`](https://github.com/2AMLogic/klayout-tools/blob/main/docs/cli/signoff.md).
  `kind: digital`; `evidence."10"` cites `evidence/item10.json`, the
  `klt signoff --attest 10` envelope for `attest/item10.json`. No other T1
  item has evidence yet.
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
