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
regeneration first (pinned yowasp-yosys synthesis, STA re-run, freshness
check, the 32-chain-cell structural check, the item-1 attestation), then
place-and-route and its dependents, checks, manifest re-pin, signoff
re-render — as one batch-fleet `repo-script` job
(heavy image), which is where these ~25-minute runs belong; the shared
dispatch worker is not a place-and-route host. Placement is never edited by
hand.

The electrical-limit classification is re-run separately:
`layout/electrical/run.sh` (klt sta, DEF + SPEF, one session per shipped
liberty corner, ~1 min) or `layout/electrical/run.sh check` (cheap: the
committed classification record still binds the committed DEF/SPEF).

## Request

`layout/place-and-route.json`: `sky130_fd_sc_hd`, `tt_025C_1v80`, clock port
`clk` at 20 ns (50 MHz, target-spec row 1), 30 % utilisation, `sky130hd` PDN
preset (tapcells and `power.pdn`), seed 1, `target_stage: route`,
`post_route_spef`, `portable_paths`.

**Electrical constraints (#173).** `max_fanout` 8, `max_transition_ns` 0.45
and `max_antenna_repair_iterations` 3 steer the `repair_design` /
`repair_timing` / `repair_antennas` passes klt already runs, at the single tt
deck they see: the fanout bound splits every structural violation class the
classification found (10-50-sink repair-inserted trees), the 0.45 ns slew
target is the worst in-supply corner's ~1.5 ns liberty limit divided by its
measured tt degradation (~3.3x), and the extra antenna iterations clear the
one violation the default single pass left. The plain
`max_transition_violation_count` fields in the response measure against that
0.45 ns request target, not the library; the `_vs_library` fields and
`layout/electrical/` are the graded evidence.

**Corner.** The request names one liberty corner, `tt_025C_1v80`. Decision 0004
(still *proposed (unratified)*) sets the core STA corner set to every liberty
corner in the pinned PDK; a P&R run optimises against one deck, and row 17
(area) is graded at `typ`, so typical was used. The response additionally
reports post-route slack at all 16 shipped corners (below). Nothing here closes
timing across the set; that is item 5.

## Records (`layout/records/`)

> Regenerated for #173 on a batch-fleet heavy instance (2026-11-22,
> `scripts/fleet-regen-layout.sh`, job group `rs-20261122T033123Z-7b4f3dda`,
> pinned klt 0.8.0 + OpenROAD 26Q4-1310 + ciel-provisioned sky130A at
> open_pdks `f6eeac7dad085`): the same #101 netlist
> (`sha256:5ea579ba0640d6d73dc84e04e410a889b0588b313785f2697c4f4cfbc38a9f64`,
> re-synthesized byte-identical in the job), routed under the electrical
> constraints #173 added to the request (`max_fanout` 8,
> `max_transition_ns` 0.45, `max_antenna_repair_iterations` 3 — see
> Request). **0 max-transition, 0 max-capacitance (library limits) and 0
> antenna violations at every one of the 16 corners** (the #101 records:
> 612, 22, 1); the DEF/SPEF classification agrees (`layout/electrical/`).
> Core area 80 417.1 µm² unchanged (utilisation 35.2 % after the inserted
> repair buffers), route DRC 0, worst setup slack across corners -15.41 ns
> at `ss_n40C_1v28` (the #101 records: -18.75 ns).
>
> Regenerated for #101 on a batch-fleet heavy instance (2026-11-18,
> `scripts/fleet-regen-layout.sh` with its new netlist phase, pinned klt 0.8.0 +
> OpenROAD 26Q4-1310 + ciel-provisioned sky130A at open_pdks `f6eeac7dad085`):
> these records now come from the post-tap-delay-refactor netlist (issue #101)
> at `sha256:5ea579ba0640d6d73dc84e04e410a889b0588b313785f2697c4f4cfbc38a9f64`,
> which `sim/hyperram/records/hyperram_ctrl.netlist.v` still is (`hyperram.py
> check` re-synthesizes byte-for-byte; the regen job ran the check and re-minted
> `evidence/item1.json` before place-and-route). They supersede the #52 records
> (netlist `sha256:038c7e9a13aff7062aa1a0e5303707865c423f28995dc347cf0189c206409ca3`,
> core 82 372.8 µm², worst setup slack -27.28 ns at `ss_n40C_1v28`, route DRC 0,
> antenna 0, tapcells 1070), which are not edited in place — the superseded
> numbers are quoted here and in PR #52.
>
> The earlier regeneration banner, for #52 (2026-11-18, same script without the
> netlist phase), recorded the post-`rd_flush`-fix netlist (#48, PR #51)
> superseding the pre-#51 records (netlist
> `sha256:c0f912a10e0dcc2d73e673b4bcf9a76fdac99a705e9dea63bffc3a5dd3d40d0f`,
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
- Core area 80 417.1 µm² (0.0804 mm²) against row 17's ≤ 0.10 mm² budget (the
  #52 records: 82 372.8 µm²). Row 17 is a proposal, so this is a number, not a
  pass.
- Route DRC (the router's own) 0; antenna violations 0 (three
  `repair_antennas` iterations, #173; the #101 records had 1). This is not
  `klt drc` (#16), which is clean on the routed GDS, and not LVS
  (#17), which matches; the router's own checker is reported as found.
- Setup slack +9.54 ns at tt, hold +0.21 ns. Across the 16 corners the worst
  setup slack is **-15.41 ns at `ss_n40C_1v28`** (the #101 records: -18.75 ns),
  and negative at `ss_n40C_1v28` (-15.41 ns) and `ss_n40C_1v35` (-4.49 ns)
  only — `ss_n40C_1v40` moved positive (+0.14 ns; `ss_n40C_1v44` +2.85 ns,
  `ss_n40C_1v60` +8.90 ns). The negative corners sit below the 1.8 V -10 %
  supply (1.62 V) of decision 0004, which the decision's corner list does not
  reconcile. Left as found (item 5 / #2).
- `max_transition_violation_count_vs_library` 0 and
  `max_capacitance_violation_count_vs_library` 0 at every corner (the #101
  records: 612 and 22; classified and fixed by #173 — see "Electrical
  limits" below). The unsuffixed `max_transition_violation_count` (5 088 at
  `ss_n40C_1v28`) counts against the request's 0.45 ns repair target, not the
  library: those pins are legal at every corner.
- The SPEF session names 2689 of 2707 design nets (`annotation_complete:
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
(abstracted gate-level SPICE, extract response, LVS report). Details and
warnings in `manifests/README.md` § "Item-4 LVS".

## Electrical limits (#173)

`layout/electrical/` classifies the max-transition / max-capacitance
violations the response only counts: `run.sh` drives `klt sta` over the
committed DEF + SPEF at every shipped liberty corner, keeps each corner's
engine stdout as the pin/limit/value evidence
(`records/opensta-<corner>.log`), and `classify.py` renders
`records/electrical-checks.{json,md}` — class, driver, sink population and
worst slew/load per violating net, reconciled against the response's own
per-corner counts and pin map (`run.sh check` re-verifies the record still
binds the committed geometry). Limits are the liberty's own as the tool
reports them; nothing re-derives a limit.

**Before (the #101 records, bound to the superseded DEF/SPEF):** 26
violating nets. Every structural class was a `repair_design`-inserted
driver the single-tt-deck optimiser built without a fanout or slew bound:
reset distribution (8 nets, 33-50 sinks, including one through a
`clkdlybuf4s50_1`), control fanout (9 nets, 10-32 sinks), enables (4 nets,
16-17 sinks, `ss_n40C_1v60` only) and one weak restructured driver
(`u_fsm/_0121_`, 4 rows at `ss_n40C_1v76`). Only the reset distribution
violated at tt (34 rows); the slow corners held 442-609 rows each.

**After (the current records):** 0 max-transition, 0 max-capacitance rows
at all 16 corners in the DEF/SPEF sessions (2689 of 2707 design nets
annotated), matching the response's `_vs_library` counts of 0/0 and
antenna 0. Signal nets grew 2434 → 2707 (the inserted repair buffers) in
the same utilisation-sized core.

The engine stdout garbles the odd violator row (duplicated slack columns,
interleaved-write fragments); `classify.py` recovers them token-wise,
records what it recovered in `engine_stdout_artifacts`, and refuses to
render a record whose row count cannot be reconciled. The `klt sta`
response itself undercounts those garbled rows — filed as
2AMLogic/klayout-tools#7161.
