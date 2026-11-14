# Roadmap

A HyperBus-class memory controller and its pad-level I/O timing on the SkyWater
sky130 open PDK, testing whether the open flow can close DDR read capture at the pins.

Status as of 2026-11-14, `main` @ `c2304fc`.

[`WORK_PLAN.md`](../WORK_PLAN.md) is the generated label-state view and
[`WORK_LOG.md`](../WORK_LOG.md) the merge history; neither is restated here.

## Where it stands

The verdict of record is
[`manifests/sky130-hyperram-ctrl.signoff.json`](../manifests/sky130-hyperram-ctrl.signoff.json)
(`klt signoff`, klayout-tools 0.8.0): `tier: null`, **7 of 11** T1 items `met`,
all graded against a **draft** spec, so every verdict is provisional.

| Item | State | Evidence, or what is missing |
|---|---|---|
| 1 Design sources | met | `rtl/hyperram_ctrl/`, `sim/hyperram/records/hyperram_ctrl.netlist.v`, re-minted under the pinned Yosys (#81, PR #87) |
| 2 Layout | met, **stale** | `layout/records/hyperram_ctrl.gds` was routed from the netlist before the #48 fix (PR #51); `make layout-check` reports STALE |
| 3 DRC clean | met, **stale** | `layout/records/drc.report.json`, on the stale GDS |
| 4 LVS clean | met, **stale** | `layout/lvs/records/report.json`, on the stale GDS |
| 5 Full corner verification vs a ratified spec | unmet | no ratified spec (#2); no corner-complete timing record for the current netlist |
| 6 Monte Carlo for statistical claims | unmet | no evidence; whether the spec makes a statistical claim is #2's call |
| 7 Post-layout verification | unmet | no SDF or parasitic-annotated run; needs a fresh layout (#52) |
| 8 Characterization report | unmet | no report; needs items 5 and 7 |
| 9 Testbenches shipped | met | `verification/ctrl/` (43 cocotb tests, one module per CT row, plus random traffic), `verification/hyperram_model/`, `evidence/item9.json` |
| 10 Repo hygiene | met | `evidence/item10.json`, re-checked by `npm run check:ci` |
| 11 Power delivery (structural) | met, **stale** | `layout/records/erc.report.json`, on the stale GDS |

Also in the tree, outside the tier record:

- The same 43 tests pass on the gate-level netlist with the PDK's cell models,
  zero delay (`make -C verification/ctrl GL=1`, #59, PR #60).
- The spec is drafted but unratified: `spec/target-spec.md` (20 rows), seven
  decision records, and the pad and clock interface tables with their gaps
  filed on the siblings (2AMLogic/sky130-io-ring#7, 2AMLogic/sky130-pll#332).
- The device-model timing **table** is now sourced: every row of
  `spec/device-model-params.md` carries a value with table and page, or an
  explicit "not published" note, and the document locator actually read is
  recorded (PR #94). The **code** side does not match it yet:
  `verification/hyperram_model/model.py`'s `PLACEHOLDER` set runs tCKD/tCKDS
  at 6.0 ns, above the sourced 1.00-5.50 ns 100 MHz column — a gap the model
  itself records and leaves for #2 (see Now 1).
- `sim/` holds no I/O timing study and `design/` no custom cell. The read
  capture this block exists to prove (target-spec rows 11, 12, 14, 19) has no
  evidence yet, and both of the spec's open questions (a) and (b) are untried.
- Findings recorded in `layout/README.md` and left as found: post-route setup
  slack is negative at the four `ss_n40C` liberty corners below 1.62 V (worst
  -24.29 ns at `ss_n40C_1v28`), which decision 0004's "all liberty corners"
  does not reconcile with its 1.8 V ±10 % supply; 732 max-transition and 20
  max-capacitance violations against the library limits are uninvestigated.

## Now (can start today, one PR each)

1. **Bring `hyperram_model.model.PLACEHOLDER` in line with the sourced spec
   table (#2).** The sourced-rows half of the old criterion is done on
   `main` (PR #94): every row of `spec/device-model-params.md` carries a value
   with table and page from the cited document, or an explicit "not
   published" note, and the document locator actually read is recorded. What
   remains is the model half: `PLACEHOLDER` still runs tCKD/tCKDS at 6.0 ns,
   above the sourced 1.00-5.50 ns 100 MHz column. Ratifying the result is a
   separate act (see Blocked and waiting).
2. **Ignore the gate-level build directory (#91, in progress).** Done when
   `make -C verification/ctrl GL=1` leaves `git status --porcelain` empty.
3. **Pre-layout timing record for the current netlist** (#97, in progress).
   Done when `sim/hyperram/records/sta.json` holds `klt sta` slack for
   `hyperram_ctrl.netlist.v` at 20 ns for every shipped `sky130_fd_sc_hd`
   corner, with the corners below 1.62 V listed separately, and a
   `make hyperram-sta` target reproduces it.
4. **Answer open question (a): does static timing see through the pad cells?**
   (#98, in progress). Done when a record under `sim/` states, for the pinned
   PDK, which `sky130_fd_io` liberty views exist and whether OpenSTA reports
   core-to-pad and pad-to-core arcs, and `spec/target-spec.md` question (a)
   cites it.
5. **Answer open question (b): delay-chain monotonicity across PVT** (#99, in
   progress). Done when an ngspice campaign on the `dlygate4sd3_1` chain used by
   `hr_rd_capture.v` records per-tap delay at every decision-0004 corner under
   `sim/`, with a monotonic / not-monotonic result per corner.
6. **Correct status lines the tree has outrun** (#100). Of its done-criteria,
   `spec/README.md` already lists decision 0007 on `main` (since `cdaac7b`);
   still owed: `spec/target-spec.md` no longer saying no proof exists for the
   CT rows, the README ladder line matching the item-9 benches, and
   `npm run check:ci` passing with item 10 re-attested.

## Next

- **Regenerate layout and its evidence (#52).** Unblocks when the batch image
  can run DRC, LVS and ERC (see below). Done when `make layout-check` reports
  fresh and items 2, 3, 4 and 11 cite records built from the current netlist.
- **Bind the layout evidence to its source netlist.** After #52: items 2, 3, 4
  and 11 stayed `met` on a stale layout because the item-2 envelope binds only
  the GDS hash. Done when `npm run check:ci` fails on a netlist/layout
  mismatch, or the gap is filed on klayout-tools as a grader gap.
- **Pad and strobe-delay timing campaign (rows 11, 12, 14).** After Now 4 and
  5, and pad data from the I/O ring sibling (2AMLogic/sky130-io-ring#7). Done
  when `sim/` holds a per-corner setup and hold margin at the capturing flop
  against the row-12 figure.
- **Item 7, post-layout verification.** After #52. Done when the GL benches run
  with SDF from the fresh layout and the manifest cites the report.
- **Max-transition and max-capacitance violations.** After #52, on the fresh
  response. Done when each class is fixed or explained in `layout/README.md`.

## Later

- **Items 5 and 8 (corner-complete verification, characterization report).**
  First: is the spec ratified, and which liberty corners does decision 0004
  actually bind once the sub-1.62 V corners are reconciled?
- **Item 6.** First: does the ratified spec make any statistical claim?
- **Custom delay cell (`design/`).** First: does open question (b) fail?
- **A `consumes:` edge to the pad ring and PLL siblings.** First: do the
  siblings publish pad delay tables and a clock output stage this block can
  pin to a commit?
- **Shuttle seat and measured silicon** (the README ladder's last rungs).
  First: does pin-level timing close at 50 MHz with the pads included?

## Blocked and waiting

- **#52** is held on 2AMLogic/2am#7142: the batch image runs place-and-route
  but lacks magic, netgen and the sky130 PDK for DRC, LVS and ERC.
- **#2 ratification** is a human/Champion act (`spec/README.md`); items 5 to 8
  wait on it, drafting under #2 does not. It also owes a decision record for
  the spec's gap **C3**: tCSM is not tabulated for the -40 to +125 °C
  *Extended* range this spec's corner set uses, the published bounds fall 4x
  over a +20 °C step (tightening with temperature), so the model's 1.00 us
  default — taken on an explicitly *Industrial Plus* basis — is not
  conservative at +125 °C (`spec/target-spec.md` row 9).
- **#70, #78, #84** are cleanup proposals waiting on an operator decision.
- **#5**, the T1 tracker, still carries its 2026-10-17 checklist; the signoff
  manifest above supersedes it.
- The pad-timing campaign waits on pad data (2AMLogic/sky130-io-ring#7).

## Not planned

- The memory device, an I/O ring or a PLL (README scope); device-compatibility
  certification, or targeting a named memory part.
- 100 MHz features (a calibrated delay line, a DLL) and wrapped bursts, both
  stretch rows, before 50 MHz closes at the pins.
- Host access to the odd register words (decision 0007); relaxing a spec row
  or a check to make a result pass.
