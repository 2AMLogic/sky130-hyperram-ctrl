# layout

Routed layout of the controller core (`hyperram_ctrl`), T1 item 2. It is the
core only: no pad ring and no PLL (sibling repos, see the repo README scope).

## Re-run

```
scripts/setup-env.sh          # once; installs the pinned toolchain
make layout                   # klt place-and-route, then refresh layout/records/ and evidence/item2.json (~25 min)
make layout-check             # cheap: request inputs vs the committed response, GDS vs the item-2 envelope
```

`make layout` needs OpenROAD and the sky130A PDK (`PDK=sky130A`, the default
the Makefile exports). It reads the item-1 netlist
`sim/hyperram/records/hyperram_ctrl.netlist.v` through
`layout/place-and-route.json`; run `make hyperram-synth` first if the RTL
changed. After a re-run commit `layout/records/` and `evidence/item2.json`,
re-pin `manifests/sky130-hyperram-ctrl.json` (items 2, 3, 4 and 11) to the new
evidence and re-render the signoff record in the same PR.
`scripts/fleet-regen-layout.sh` runs the whole sequence — netlist
regeneration first (pinned yowasp-yosys synthesis, STA re-run, the
32-chain-cell structural check, the item-1 attestation, whose freshness
command runs the byte-compare check), then place-and-route and its
dependents, checks, manifest re-pin, signoff re-render — as one batch-fleet
`repo-script` job
(heavy image), which is where these ~25-minute runs belong; the shared
dispatch worker is not a place-and-route host. Placement is never edited by
hand.

## Request

`layout/place-and-route.json`: `sky130_fd_sc_hd`, `tt_025C_1v80`, clock port
`clk` at 20 ns (50 MHz, target-spec row 1), 30 % utilisation, `sky130hd` PDN
preset (tapcells and `power.pdn`), seed 1, `target_stage: route`,
`post_route_spef`, `portable_paths`.

**Corner.** The request names one liberty corner, `tt_025C_1v80`. Decision 0004
(still *proposed (unratified)*) sets the core STA corner set to every liberty
corner in the pinned PDK; a P&R run optimises against one deck, and row 17
(area) is graded at `typ`, so typical was used. The response additionally
reports post-route slack at all 16 shipped corners (below). Nothing here closes
timing across the set; that is item 5.

## Records (`layout/records/`)

> Regenerated for #170 on a batch-fleet heavy instance (2026-11-21,
> `scripts/fleet-regen-layout.sh`, pinned klt 0.9.2 + OpenROAD 26Q4-1310 +
> ciel-provisioned sky130A at open_pdks `f6eeac7dad085`): same RTL and the same
> pinned YoWASP Yosys, but klt 0.9.2 drives synthesis differently than the
> 0.8.0 pin did, so the re-synthesized netlist is a different mapping of the
> same design (2290 cells, 24 228.2 µm²) at
> `sha256:0f03005ab04a2fc45365680d543d13e1742a8e4288228c28eb279b0b94e463d7`,
> which `sim/hyperram/records/hyperram_ctrl.netlist.v` now is (`hyperram.py
> check` re-synthesizes byte-for-byte at 0.9.2; the regen job ran the check and
> re-minted `evidence/item1.json` before place-and-route, and the gate-level
> bench suite re-ran 43/43 against the new netlist). They supersede the #101
> records (netlist
> `sha256:5ea579ba0640d6d73dc84e04e410a889b0588b313785f2697c4f4cfbc38a9f64`,
> core 80 417.1 µm², worst setup slack -18.75 ns at `ss_n40C_1v28`, route DRC 0,
> antenna 1, tapcells 1060), which are not edited in place — the superseded
> numbers are quoted here and in the #101 records' commit (`2ff11a6`).
>
> The earlier regeneration banner, for #101 (2026-11-18, the same script at
> klt 0.8.0), recorded the post-tap-delay-refactor netlist (issue #101)
> superseding the #52 records (netlist
> `sha256:038c7e9a13aff7062aa1a0e5303707865c423f28995dc347cf0189c206409ca3`,
> core 82 372.8 µm², worst setup slack -27.28 ns at `ss_n40C_1v28`, route DRC 0,
> antenna 0, tapcells 1070), which in turn superseded the pre-#51 records
> (netlist `sha256:c0f912a10e0dcc2d73e673b4bcf9a76fdac99a705e9dea63bffc3a5dd3d40d0f`,
> core 83 687.8 µm², worst setup slack -24.29 ns at `ss_n40C_1v28`).

| File | What |
|---|---|
| `hyperram_ctrl.gds` | routed GDS, bound by `evidence/item2.json` |
| `hyperram_ctrl.def` | routed DEF |
| `hyperram_ctrl.routed.v` | as-built gate-level netlist (CTS buffers, antenna diodes); this one, not the pre-CTS netlist, goes to LVS (`layout/lvs/`) |
| `hyperram_ctrl.spef` | post-route parasitics |
| `place-and-route.response.json` | the `klt place-and-route --format json` response |
| `area.json` | core area against row 17 |

The response is klt's own, with two edits by `flow/hyperram.py`: artifact paths
point at `layout/records/` instead of the untracked scratch dir `layout/.klt/`,
and the per-stage log/script paths are dropped (the logs stay in the scratch
dir; their hashes stay in the response).

## Reported, not graded

From the committed response (`tt_025C_1v80` unless a corner is named):

- `power.pdn: true`, `power.tapcell_master: sky130_fd_sc_hd__tapvpwrvgnd_1`
  (1060 tapcells at a 14 µm distance; the #52 records had 1070).
- Core area 80 287 µm² (0.0803 mm²) against row 17's ≤ 0.10 mm² budget (the
  #101 records: 80 417.1 µm²). Row 17 is a proposal, so this is a number, not a
  pass.
- Route DRC (the router's own) 0; antenna violations 1 (the #52 records had 0).
  This is not `klt drc` (#16), which is clean on the routed GDS, and not LVS
  (#17), which matches; it is the router's own checker, reported as found.
- Setup slack +9.54 ns at tt, hold +0.21 ns. Across the 16 corners the worst
  setup slack is **-21.21 ns at `ss_n40C_1v28`** (the #101 records: -18.75 ns),
  and negative at `ss_n40C_1v35` and `ss_n40C_1v40` at -40 °C (`ss_n40C_1v44`
  moved positive, +1.24 ns; `ss_n40C_1v60` is +8.45 ns). The negative corners
  sit below the 1.8 V -10 % supply (1.62 V) of decision 0004, which the
  decision's corner list does not reconcile. Left as found.
- `max_transition_violation_count` 619 and `max_capacitance_violation_count`
  22 against the library limits (the #101 records: 612 and 22). Not
  investigated here.
- The SPEF session names 2379 of 2397 design nets (`annotation_complete:
  false`), so its slack (+9.54 ns) is not a full real-parasitics measurement.
- Pins are placed by the tool on arbitrary edges; no pad-facing pin plan exists
  (the pads belong to the I/O ring sibling).
- Not looked at: whether the CK-output and RWDS-capture delay-chain instances
  sit together. `klt place-and-route` offers no grouping or region control
  (2AMLogic/klayout-tools#4344), so placement of that path is
  whatever the tool chose.

## LVS (T1 item 4)

`layout/lvs/`: `extract.json` and `request.json` (the `klt extract` and
`klt lvs` requests), `run.sh` (re-run, or `check` to re-hash), and `records/`
(abstracted gate-level SPICE, extract response, LVS report). The extract
response is klt's own with `dead_metal` emptied by `run.sh` (the count stays in
the klt warning; the full list needs the ~8 min re-run). Details and
warnings in `manifests/README.md` § "Item-4 LVS".
