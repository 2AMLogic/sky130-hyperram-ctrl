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

### C3 — the +125 °C point is outside the device's published tCSM basis

Found 2026-11-14, while transcribing the interface definition. This record's
temperature range is **−40 … +125 °C**, which §8.3.1 of that definition (p. 28)
calls *Extended*. One device parameter this controller must respect is **not
tabulated for Extended**: **tCSM**, the maximum time CS# may stay low. It is
published only as **4.00 µs** for *Industrial* (−40…+85 °C) and **1.00 µs** for
*Industrial Plus* (−40…+105 °C) — Table 9.4, p. 36.

The gap is not benign, because the bound moves the **wrong way** for us: it
falls **4× for a +20 °C step**, and Table 3.2 note 1 (p. 10) ties the limit to a
*"distributed refresh interval for HyperRAM memory"* — a retention limit, which
shortens as temperature rises. Extrapolating that trend past +105 °C puts the
Extended bound **below 1.00 µs**, by an amount the source does not publish. So
adopting 1.00 µs at +125 °C is the **loose** direction, not the conservative
one: a down-counter sized to it could hold CS# low longer than the device
tolerates between refreshes, and that would not show up at 27 °C.

Not settled here, and no number in this record changes. `tCSM` is kept
**parameterized** in [`../target-spec.md`](../target-spec.md) row 9 with 1.00 µs
recorded as an *Industrial Plus*-basis default, and the +125 °C point is marked
not covered for that row. The ratifier's choice — stated, not implied:

1. accept an explicitly Industrial Plus thermal basis for this row, leaving
   +125 °C uncovered for tCSM while the rest of the corner set stands; or
2. narrow this record's temperature range to +105 °C, which costs coverage
   everywhere else and conflicts with the two siblings above; or
3. obtain or measure an Extended-range figure, which the public definition does
   not supply.

Like C1/C2 in [`../pad-interface.md`](../pad-interface.md), this is owed a
decision record before ratification, and no row is relaxed to make it go away.

## Consequences
Each result records its corner in its name; recorded results are append-only.
