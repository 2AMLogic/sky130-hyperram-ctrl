# Roadmap

A HyperBus-class memory controller and its pad-level I/O timing on the SkyWater
sky130 open PDK, testing whether the open flow can close DDR read capture at the pins.

Status as of 2026-11-23, `main` @ `ae25a3b`.

[`WORK_PLAN.md`](../WORK_PLAN.md) is the generated label-state view and
[`WORK_LOG.md`](../WORK_LOG.md) the merge history; neither is restated here.

## Where it stands

The verdict of record is
[`manifests/sky130-hyperram-ctrl.signoff.json`](../manifests/sky130-hyperram-ctrl.signoff.json)
(`klt signoff`, klayout-tools 0.9.2): `tier: null`, **7 of 11** T1 items `met`,
all graded against a **draft** spec, so every verdict is provisional.

| Item | State | Evidence, or what is missing |
|---|---|---|
| 1 Design sources | met | `rtl/hyperram_ctrl/`, `sim/hyperram/records/hyperram_ctrl.netlist.v`, re-minted under the pinned Yosys (#81, PR #87) |
| 2 Layout | met, **stale** | `layout/records/hyperram_ctrl.gds` was routed from the netlist before the #48 fix (PR #51); `make layout-check` reports STALE |
| 3 DRC clean | met, **stale** | `layout/records/drc.report.json`, on the stale GDS |
| 4 LVS clean | met, **stale** | `layout/lvs/records/report.json`, on the stale GDS |
| 5 Full corner verification vs a ratified spec | unmet | no ratified spec (#2); no corner-complete timing record for the current netlist |
| 6 Monte Carlo for statistical claims | unmet | no evidence; whether the spec makes a statistical claim is #2's call |
| 7 Post-layout verification | unmet, **probed** | the SDF-annotated run exists and fails: 39 of 43 benches on `hyperram_ctrl.routed.v` with the DEF+SPEF SDF at `tt_025C_1v80` fail — the bench samples on the annotated CK pin edge (#199), so the six CA bytes decode and the residuals are the ~9/11 ns annotated CK half-period vs the model's 20 ns placeholder (#2), the register configuration-read settle (#200) and host acknowledgement under annotation; #187 traced the typ CK/CA pins and found no fault in the CK launch path or the ICG (`sim/hyperram/records/CK-TRACE.md`); report `sim/hyperram/records/functional-verification-ctrl-sdf.report.json` |
| 8 Characterization report | unmet | no report; needs items 5 and 7 |
| 9 Testbenches shipped | met | `verification/ctrl/` (43 cocotb tests, one module per CT row, plus random traffic), `verification/pin_edge_sample/` (the bench's pin-edge pad sample, #205), `verification/hyperram_model/`, `evidence/item9.json` |
| 10 Repo hygiene | met | `evidence/item10.json`, re-checked by `npm run check:ci` |
| 11 Power delivery (structural) | met, **stale** | `layout/records/erc.report.json`, on the stale GDS |

Also in the tree, outside the tier record:

- The same 43 tests pass on the gate-level netlist with the PDK's cell models,
  zero delay (`make -C verification/ctrl GL=1`, #59, PR #60).
- The SDF-annotated post-route run exists (#171): `klt sta` on the committed
  DEF + SPEF wrote `layout/records/hyperram_ctrl.tt_025C_1v80.sdf`, and the
  same benches with that SDF back-annotated on the routed netlist fail 39/43
  (`make -C verification/ctrl sdf`; the bench samples on the annotated CK
  pin edge — #199 fixed the +5 ns stand-in offset double-counting the tap
  delay, so the six CA bytes now decode and the probe transactions deliver
  `60 00 01 00 00 00` (CR0 write) and `a0 00 00 55 00 02` (array read) to
  the model; `environment.sdf.annotated: true` — partial, though:
  `environment.sdf.partial: true`, 732 entries dropped in that report, 504
  `timingcheck` plus 208 + 20 zero-delay interconnect; see Next item 7).
  #187 traced the annotated pins at the typ corner
  (`sim/hyperram/records/CK-TRACE.md`, `make ck-trace`) and refuted the
  ICG / tap-chain cause: the first CK edge rises with CA byte 0 already
  driven, every observed edge sits inside its byte window, and the single
  early CK pulse seen at zero delay is not present when annotated; the
  failure it observed was the bench's +5 ns pad sample landing mid byte
  transition, which #199 then fixed. The residual signatures are the
  annotated CK duty (~9/11 ns half-periods, which the model's 20 ns tCK
  placeholder flags; #2), the register configuration-read settle (#200),
  and read host acknowledgement under annotation. The bench's offset-0
  sample is taken in the read-only phase of the CK edge's timestep (#205):
  a DQ/RWDS/OE transition inside that timestep is sampled at its settled
  value instead of whichever update the simulator applied first (an
  order-dependent read; on the zero-delay RTL, where the coincidence is
  real, it failed 42/43 with 126 "DQ must be driven by the host during
  CA" assertions before the fix). The re-run after #205 is per-test
  identical to the pre-#205 run (4/43, 0 "during CA") and keeps it
  verbatim under
  `sim/hyperram/records/functional-verification-ctrl-sdf.runs/` —
  recorded results are append-only. The manifest cites the failing
  report, so item 7 grades `unmet`/`check_failed`, not `no_evidence`.
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
- Both of the spec's open questions now have first answers, from two I/O
  timing studies under `sim/`. Question (a), does static timing see through
  the pad cells: yes for the delay arcs — `OUT -> PAD` and `PAD -> IN` are
  real arcs in the shipped `sky130_fd_io` liberty — but only **2 of 21**
  `top_gpiov2` liberty corners fall inside decision 0002's 2.97–3.63 V I/O
  window and neither is a fast corner, so liberty yields a slow/max pad
  delay but no fast/min bound; the min/max spread still needs ngspice
  (`sim/pad-sta/records/RECORD.md`). Question (b), delay-chain
  monotonicity across PVT: monotonic at every corner, rise and fall —
  45 of 45 corners over the 16-cell `g_dly` chain of `hr_tap_delay`
  (`u_rwds_dly`; `sim/delay-chain/records/RECORD.md`). The pre-layout core STA record
  (`sim/hyperram/records/sta.json`, `sim/hyperram/records/STA.md`) is not
  I/O-timing evidence: it loads only `sky130_fd_sc_hd` — no pads, no I/O
  constraints. `design/` still holds no custom cell.
- Findings recorded in `layout/README.md` and left as found: post-route setup
  slack is negative at the four `ss_n40C` liberty corners below 1.62 V (worst
  -27.28 ns at `ss_n40C_1v28`), which decision 0004's "all liberty corners"
  does not reconcile with its 1.8 V ±10 % supply; 284 max-transition and 15
  max-capacitance violations against the library limits are uninvestigated.

## Now

Each item is routing as of the header sha above; live label state is
[`WORK_PLAN.md`](../WORK_PLAN.md). Landed items name the record that closed
them; open ones keep their done-criterion.

1. **Bring `hyperram_model.model.PLACEHOLDER` in line with the sourced spec
   table (#2).** The sourced-rows half of the old criterion is done on
   `main` (PR #94): every row of `spec/device-model-params.md` carries a value
   with table and page from the cited document, or an explicit "not
   published" note, and the document locator actually read is recorded. What
   remains at the header sha is the model half: `PLACEHOLDER` still runs
   tCKD/tCKDS at 6.0 ns, above the sourced 1.00-5.50 ns 100 MHz column.
   Ratifying the result is a separate act (see Blocked and waiting).
2. **Ignore the gate-level build directory (#91).** Landed on `main` (PR
   #104): `.gitignore`'s `sim_build*/` glob covers the GL=1 variant directory
   (`SIM_BUILD = sim_build_gl`), so `make -C verification/ctrl GL=1` leaves
   `git status --porcelain` empty.
3. **Pre-layout timing record for the current netlist (#97).** Landed on
   `main` (PR #107): `sim/hyperram/records/sta.json` holds `klt sta` slack
   for `hyperram_ctrl.netlist.v` at 20 ns for every shipped
   `sky130_fd_sc_hd` corner, corners below 1.62 V listed separately;
   `make hyperram-sta` reproduces it and `sim/hyperram/records/STA.md`
   records it. Core-only — no pads, no I/O constraints (see Where it
   stands).
4. **Answer open question (a): does static timing see through the pad
   cells? (#98).** Answered on `main` (PR #108):
   `sim/pad-sta/records/RECORD.md` — yes for the delay arcs (`OUT -> PAD`,
   `PAD -> IN`), but exactly 2 of 21 shipped `top_gpiov2` liberty corners
   fall inside decision 0002's 2.97–3.63 V I/O window and neither is a fast
   corner, so liberty alone cannot bound the min/max pad delay; the spread
   still needs ngspice (Next).
5. **Answer open question (b): delay-chain monotonicity across PVT (#99).**
   Answered on `main` (PR #109): `sim/delay-chain/records/RECORD.md` —
   monotonic at every corner, rise and fall (45 of 45), over the 16-cell
   `g_dly` `dlygate4sd3_1` chain of `hr_tap_delay` (instantiated as
   `u_rwds_dly` in `hr_rd_capture.v`).
6. **Correct status lines the tree has outrun** (#100). Of its done-criteria,
   `spec/README.md` already lists decision 0007 on `main` (since `cdaac7b`);
   still owed at the header sha: `spec/target-spec.md` no longer saying no
   proof exists for the CT rows, the README ladder line matching the item-9
   benches, and `npm run check:ci` passing with item 10 re-attested.

## Next

As of the header sha above; live label state is
[`WORK_PLAN.md`](../WORK_PLAN.md).

- **Regenerate layout and its evidence (#52).** Unblocks when the batch image
  can run DRC, LVS and ERC (see below). Done when `make layout-check` reports
  fresh and items 2, 3, 4 and 11 cite records built from the current netlist.
- **Bind the layout evidence to its source netlist.** After #52: items 2, 3, 4
  and 11 stayed `met` on a stale layout because the item-2 envelope binds only
  the GDS hash. Done when `npm run check:ci` fails on a netlist/layout
  mismatch, or the gap is filed on klayout-tools as a grader gap.
- **Pad and strobe-delay timing campaign (rows 11, 12, 14).** Now 4 and 5 are
  answered (records above); what remains is pad data from the I/O ring
  sibling (2AMLogic/sky130-io-ring#7) and the ngspice min/max pad-delay
  spread that question (a) left open. Done when `sim/` holds a per-corner
  setup and hold margin at the capturing flop against the row-12 figure.
- **Item 7, post-layout verification.** The probe landed (#171): the SDF from
  the committed DEF + SPEF exists in `layout/records/` with its producing STA
  response, and the annotated bench run is recorded — it fails 39/43 now
  that the bench samples on the annotated CK pin edge (#199) instead of
  double-counting the tap-3 CK delay, so item 7 stays `unmet` with the
  failing report cited. #187 traced the typ CK/CA pins
  (`sim/hyperram/records/CK-TRACE.md`) and found no fault in the CK launch
  path or the ICG. What remains is the CK-duty interpretation and model
  limit (#2; the annotated half-periods measure ~8.9/9.0 ns against the 20 ns
  placeholder), the register configuration-read settle (#200) and read host
  acknowledgement under annotation; done when a re-run of
  `make post-route-verify` passes (or its remainders are re-triaged narrower).
  A `met` grade from that run carries a named assumption: Icarus drops every
  SDF TIMINGCHECK (504 entries in the landed report,
  `sim/hyperram/records/functional-verification-ctrl-sdf.report.json`, PR
  #188), so the run proves IOPATH/INTERCONNECT-annotated function only —
  `$setup`/`$hold` run against the cell library's placeholder timing, not
  the SDF's characterised limits. Setup/hold margin is the item-5 STA
  record's claim (#172), not this run's.
- **Max-transition and max-capacitance violations.** After #52, on the fresh
  response. Done when each class is fixed or explained in `layout/README.md`.

## Later

- **Items 5 and 8 (corner-complete verification, characterization report).**
  First: is the spec ratified, and which liberty corners does decision 0004
  actually bind once the sub-1.62 V corners are reconciled?
- **Item 6.** First: does the ratified spec make any statistical claim?
- **Custom delay cell (`design/`).** Its gate question, open question (b), is
  answered and did not fail: 45 of 45 corners monotonic, rise and fall
  (`sim/delay-chain/records/RECORD.md`); `design/` still holds no custom
  cell.
- **A `consumes:` edge to the pad ring and PLL siblings.** First: do the
  siblings publish pad delay tables and a clock output stage this block can
  pin to a commit?
- **Shuttle seat and measured silicon** (the README ladder's last rungs).
  First: does pin-level timing close at 50 MHz with the pads included?

## Blocked and waiting

- **#52** is held on 2AMLogic/2am#7142: the batch image runs place-and-route
  but lacks magic, netgen and the sky130 PDK for DRC, LVS and ERC.
- **#2 ratification** is a human/Champion act (`spec/README.md`); items 5, 6
  and 8 wait on it, drafting under #2 does not. Item 7 no longer waits on it
  either: the provisional SDF-annotated run exists (#171) and what it waits
  on is the CK-path design iteration (#187). #2 also owes a decision record for
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
