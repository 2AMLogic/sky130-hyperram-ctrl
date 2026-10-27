# Block manifest and tier-verdict record

- **`sky130-hyperram-ctrl.json`**: block manifest for
  [`klt signoff --manifest`](https://github.com/2AMLogic/klayout-tools/blob/main/docs/cli/signoff.md).
  `kind: digital`; `evidence."10"` cites `evidence/item10.json`, the
  `klt signoff --attest 10` envelope for `attest/item10.json`; `evidence."4"`
  cites the `klt lvs` report `layout/lvs/records/report.json` directly (see
  "Item-4 LVS" below). Other T1 items are in the manifest as they land.
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

## Item-4 LVS

`evidence."4"` is `layout/lvs/records/report.json`, `klt lvs` (engine
`klayout`, 0.30.12) at `klayout-tools==0.8.0`: the routed GDS
(`layout/records/hyperram_ctrl.gds`) extracted with every `sky130_fd_sc_hd__*`
cell abstracted (`layout/lvs/extract.json`), compared against the as-built
routed netlist `layout/records/hyperram_ctrl.routed.v`
(`reference.form: gate-level-verilog`). `status: match` and
`power_connectivity.status: match`. Re-run: `layout/lvs/run.sh` (~8 min, mostly
extraction); cheap re-hash: `layout/lvs/run.sh check`. After a re-run, copy
`provenance.input.content_hash` of the report into `evidence."4".content_hash`
and regenerate the signoff record (command above).

What `match` covers: signal connectivity of 2425 nets and 165 pins at
black-box standard-cell level, and that all 12361 instances' `VPWR` reach net
`VDD` and `VGND` reach `VSS` (`expected_nets`; `VDD`/`VSS` are the PDN nets the
place-and-route response names in `power.power_net`/`ground_net`). It does not
cover transistor-level devices inside the cells (0 devices on both sides) or
geometric rail continuity (`klt ring-check`, `klt power`). The report's content
hash pins the extracted netlist; the GDS binding is in
`layout/lvs/records/extract.response.json` (`provenance.input`, equal to the
item-2 GDS hash).

Warnings, as reported:

- `topology.power_only_pruned`: 5 power-only circuits (`fill_1/2/4/8`,
  `tapvpwrvgnd_1`) removed before the signal compare, by design.
- `topology.top_level_pins_anchored`: 165 top-level pins anchored by name.
- `klt extract`: 93 warnings. 90 are `--abstract-cells` cell types whose
  substrate port resolves only through the deck's global net `vsubs`, so it is
  dropped from the black box (the same symptom as klayout-tools#3749, which is closed;
  not re-filed, still present at 0.8.0 on this design). The rest note `VPB`/`VPWR` on one net per
  instance, 13462 routing-stack clusters joining no extracted net, and 13
  layers outside the deck's connectivity graph. Not investigated further here.
- `power_pins` is `VGND, VPB, VPWR`; `VNB` is not in the checked universe
  because of the dropped substrate port above.
