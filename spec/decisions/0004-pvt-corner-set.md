# 0004 PVT corner set

Status: proposed (unratified).

## Decision
Core STA: all `sky130_fd_sc_hd` liberty corners in the pinned PDK. ngspice:
tt/ff/ss/fs/sf, temperature −40 … +125 °C sampled at −40/27/125 °C. Supplies:
core 1.8 V ±10 %, I/O supply ±10 % around its nominal (decision 0002).

## Context
The −40 … +125 °C range is the one proposed in issue #2; this record
makes it a decision rather than an assumption.

### Independent corroboration from two siblings (read 2026-11-14)

This is corroboration, not a new argument, and it changes no number here.

- **`2AMLogic/sky130-pll`** at `37484b328e16a4afddf4e96d3647ec191be902eb`
  **ratified** its rows 19 and 20 on 2026-08-27 (`DR-003`, their #77): process
  `tt ff ss sf fs`, and −40 °C to 125 °C **sampled at −40 / 27 / 125 °C**. That
  is identical to this record, including the 27 °C mid sample. `DR-003` records
  that the mixed-skew corners `sf`/`fs` were added deliberately, over a prior
  `tt`/`ss`/`ff`-only harness convention, because they stress an un-cascoded
  current mirror — i.e. the five-corner set was argued, not inherited. Their row
  20 further notes `2AMLogic/sky130-bandgap` independently adopting the same
  temperature range for the same PDK.
- **`2AMLogic/sky130-io-ring`** at `1aecfa749b69da677fb47570ab910ffffcefbe3c`
  adopts the same five process corners in its decision 0003 (**proposed**, not
  ratified, 2026-10-17), confirmed against section names in `sky130.lib.spice`
  in the inspected PDK.

So three blocks on the same PDK converge on the same five process corners and
the same temperature range. Two differences are left for the ratifier rather
than settled here:

1. **Mid temperature sample point.** sky130-pll ratified **27 °C** (as here);
   sky130-io-ring proposes **25 °C**. A 2 °C difference changes no verdict, but
   results named `..._25C` and `..._27C` are not interchangeable, and this
   repo compares pad figures with io-ring's. Settle which point this spec cites
   at ratification.
2. **Cross-supply codes.** io-ring's PVT.5 crosses the two supplies
   (`hl` = VDDIO high with VDD low, `lh` = the reverse) specifically to stress
   the level shifter, giving 75 named corners. This record names no
   cross-supply code. Since this controller's read and write paths run *through*
   that level shifter, adopting the cross-supply points is worth considering —
   but it widens the corner set, so it is a ratification choice, not a
   Builder's.

Neither point is a reason to change a number in this record now.

## Consequences
Each result records its corner in its name; recorded results are append-only.
