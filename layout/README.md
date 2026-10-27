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
and re-pin `manifests/sky130-hyperram-ctrl.json` item 2 to the new GDS hash.
Placement is never edited by hand.

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
  (1134 tapcells).
- Core area 83 687.8 µm² (0.0837 mm²) against row 17's ≤ 0.10 mm² budget. Row
  17 is a proposal, so this is a number, not a pass.
- Route DRC (the router's own) 0, antenna violations 0. This is not `klt drc`
  (#16) and not LVS (#17).
- Setup slack +9.54 ns at tt, hold +0.34 ns. Across the 16 corners the worst
  setup slack is **-24.29 ns at `ss_n40C_1v28`**, and negative at `v1p35`,
  `v1p40` and `v1p44` at -40 °C; `ss_n40C_1v60` is +7.73 ns. The negative
  corners sit below the 1.8 V -10 % supply (1.62 V) of decision 0004, which
  the decision's corner list does not reconcile. Left as found.
- `max_transition_violation_count` 732 and `max_capacitance_violation_count`
  20 against the library limits. Not investigated here.
- The SPEF session names 2407 of 2425 design nets (`annotation_complete:
  false`), so its slack (+9.53 ns) is not a full real-parasitics measurement.
- Pins are placed by the tool on arbitrary edges; no pad-facing pin plan exists
  (the pads belong to the I/O ring sibling).
- Not looked at: whether the CK-output and RWDS-capture delay-chain instances
  sit together. `klt place-and-route` offers no grouping or region control
  (2AMLogic/klayout-tools#4344), so placement of that path is
  whatever the tool chose.

## LVS (T1 item 4)

`layout/lvs/`: `extract.json` and `request.json` (the `klt extract` and
`klt lvs` requests), `run.sh` (re-run, or `check` to re-hash), and `records/`
(abstracted gate-level SPICE, extract response, LVS report). Details and
warnings in `manifests/README.md` § "Item-4 LVS".
