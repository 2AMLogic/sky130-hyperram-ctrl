# Pad requirements (DRAFT)

Compared with `2AMLogic/sky130-io-ring` at commit
`1aecfa749b69da677fb47570ab910ffffcefbe3c`, that repo's HEAD on
2026-11-14T01:28:45Z, read the same day. (Issue #2's curation named
`3042d4cd0771f9316c2a81c844269761368277d8`, its HEAD on 2026-11-13; the sibling
moved before this pass ran, so the later commit is the one actually read.) This
supersedes the earlier comparison against `9cf5d41503b5566935da2bc0b74ccb50a00fcfab`
(read 2026-10-17).

**What changed since `9cf5d41`, and why every verdict below moved.** At that
commit the sibling's `spec/` was an empty placeholder and its README held a
DRAFT table. It now holds a real specification — `spec/io-ring.md` with
numbered rows in eight sections plus `spec/io-ring.json` as the machine-readable
source, four decision records, and a `check_spec.py` that fails if the tables
and the data disagree. Its status is **proposed, pending EE-key and market-key
review and then operator ratification** (their 2026-10-22 ruling, 2am#5864);
nothing in it is ratified, and its authors cannot ratify their own design. The
GPIO cell is also now **netlisted and drawn** (`design/netlists/sky130_ioring_gpio*.spice`,
`design/xschem/`, `layout/gds/sky130_ioring_gpio.gds`).

So the rows that used to read "**gap**: no data" have changed *kind*, in two
different directions, and it matters which:

- **Drive, edge rate and toggle rate now have target figures at a stated
  corner.** These rows become fits against a proposal.
- **Delay and its spread still have no usable figure** — not because the
  sibling is silent, but because what it states is a **one-sided maximum at a
  single slow corner**, and read capture needs the *spread*. A maximum cannot
  bound a spread. This is now "characterizable but not characterized, and the
  stated target is the wrong shape for us", which is a sharper ask than "no
  data".

`measurements/` in that repo is still a three-line placeholder README with no
other file in it, so **no measured pad figure exists anywhere**. Every io-ring
value below is a design target.

The sky130 foundry I/O library (`sky130_fd_io`) still has not been read directly
by this repo; rows are marked "unchecked (ours)" where that read is owed. Note
that `io-ring.md` now cites the foundry user guide per row (VDDIO operating
range, `gpiov2` over-voltage tolerance in its Table 101, 80 µm GPIO pitch,
197.965 µm depth, the ~150 Ω core-access series resistor), so those figures
reach us second-hand with a citation rather than not at all.

## Requirements table

Row ids in the third column are `io-ring.md`'s own (`SUP.n`, `GF.n`, `GE.n`,
`CELL.n`, `PVT.n`).

| Requirement | Value needed | io-ring at `1aecfa74` | Fit / gap |
|---|---|---|---|
| I/O supply | 3.3 V-class, ±10 % — **but see the conflict below**: the device's own VCCQ range is 2.70–3.60 V, so a shared rail at +10 % (3.63 V) is out of its range | **SUP.1** 3.3 V ±10 % (2.97 / 3.30 / 3.63 V). 5.5 V pad tolerance is *stretch*, not target: foundry `gpiov2` is not over-voltage tolerant (their user-guide Table 101) | **fit between the two repos, conflict with the device.** The pad spec and this spec agree exactly (both 3.3 V ±10 %); it is the *device interface* that permits only +9.1 %. Nothing to ask io-ring for — this is ours to settle |
| Core-side level | 1.8 V core, shifted inside the pad | **SUP.2** 1.8 V ±10 % (1.62 / 1.80 / 1.98 V), level shift owned by the pad cell; **GF.8** shifts both directions inside the cell | **fit** (proposed) |
| Bidirectional DQ[7:0], RWDS | output enable and input enable per pin | **GF.1** core-side OE, pad high-Z when OE inactive; **GF.2** core-side IE, core-side input held at a defined level when IE inactive | **fit** (proposed). GF.2's defined level matters for DQ turnaround — it means a floating bus does not toggle the core |
| CK output | output-only pad | **GF.1** fallback keeps output-only and input-only variants; the target GPIO covers it | **fit** |
| CS#, RESET# | output-only pads | as above | **fit** |
| Drive strength | enough for a short board trace at 50 MHz, fixed by SPICE at a stated load | **GE.1** VOH ≥ VDDIO − 0.4 V at IOH = −4 mA and **GE.2** VOL ≤ 0.4 V at IOL = 4 mA, both at corner ss / 125 °C / VDDIO 2.97 V / VDD 1.62 V. Fallback ±2 mA; stretch ±8 mA in a selectable strong mode. **GF.4** one fixed strength in the target, selectable drive is stretch | **fit, and the placeholder is resolved.** This row previously carried "placeholder: 10 pF, to be replaced" — io-ring characterizes into **10 pF**, the same load, so the two specs agree on the load by convergence rather than by assumption. 4 mA at the slow/hot/low corner is a figure we can design against. Still a target: `measurements/` is empty |
| Edge rate / input slew seen by the device | the device's AC timings **assume an input slew rate of 2 V/ns** (`device-model-params.md`, Table 9.1 note 1); a single-ended CK is allowed ≥ 1 V/ns (Table 9.3 note 1) | **GE.3** tr/tf (20–80 % of VDDIO) ≤ 3 ns into 10 pF at ss / 125 °C / 2.97 V, fallback ≤ 5 ns; **GE.4** tr/tf ≥ 0.8 ns into 10 pF at ff / −40 °C / 3.63 V | **conflict — see below.** GE.3's ceiling is far slower than 2 V/ns — **~3.4×** too slow at the slow corner. This row was written as a "fit" earlier in this same pass and is corrected here |
| Maximum toggle rate | 50 MHz at the pins, 25 MHz fallback | **GE.9** 50 MHz into 10 pF on both the output and input paths at ss / 125 °C / low supplies, fallback 25 MHz | **fit, exactly.** Our target and fallback match GE.9's target and fallback, at the corner we care about. This is the single strongest point of agreement between the two specs |
| Output delay and spread | pad-to-pin **minimum and maximum** over all ngspice corners, rise and fall separately, stated per cell | **GE.7** core-OUT-to-PAD 50 %–50 % ≤ 5 ns into 10 pF at ss / 125 °C / 2.97 V / 1.62 V; fallback ≤ 8 ns | **gap, narrowed and restated.** A maximum now exists at the slow corner. There is **no minimum, no fast-corner figure, and no rise/fall split**, so the spread — `max − min`, the only quantity read capture consumes — cannot be derived from it. A 5 ns ceiling is equally consistent with a spread of 0 ns or of 5 ns |
| Input delay and spread | pin-to-core minimum and maximum, same corners, tracked on RWDS and DQ **separately** | **GE.8** PAD-to-core-IN 50 %–50 % ≤ 3 ns at ss / 125 °C / 2.97 V / 1.62 V; fallback ≤ 5 ns | **gap, same kind.** One-sided maximum, no minimum, and no statement that two instances of the cell match each other. For read capture the per-pin *matching* is more important than the absolute value |
| Pad-to-pad delay matching | RWDS vs DQ input-path skew within 0.2 ns (our proposal) over all corners | **nothing.** GE.3/GE.4 bound each pad's own edge rate; no row in `io-ring.md` bounds the delay difference between two instances of the same cell | **gap, unchanged and now the critical one.** Edge rate is not inter-pin skew. This is the term `clock-phase-requirement.md` calls `e_pad`, and it is the one term in that budget that nothing upstream bounds |
| Output-enable timing | OE-to-pin-valid and OE-to-Hi-Z, minimum and maximum, to turn DQ around without contention | **GF.1** defines OE functionally (high-Z when inactive); **no OE timing row exists** in the GE section | **gap, unchanged.** Still no figure. Without it the read/write turnaround cannot be budgeted |
| Supply sequencing at power-up | the controller must be able to hold RESET# and CS# at defined levels from the moment the I/O supply is up (target-spec row 8) | **SUP.6** either supply may rise first; with VDD absent and VDDIO present the pad is **high-Z** and draws ≤ 1 µA from VDDIO at 25 °C. Stated as a design target to be confirmed by simulation, not a measured figure | **gap for us** (new row in this pass). A high-Z pad before the core supply is up means the controller **cannot** hold RESET# low during that interval — the board must, via a pull. Target-spec row 8 assumes the controller owns the power-up interval; that assumption holds only once VDD is up. Needs a decision record before ratification |
| Input threshold and hysteresis | CMOS levels, noise immunity on a board trace | **GE.5** VIL ≤ 0.3 × VDDIO and VIH ≥ 0.7 × VDDIO over all corners; **GF.7** Schmitt input with ≥ 200 mV hysteresis at 3.30 V, tt / 25 °C | **fit** (new row in this pass) |
| Pad leakage | must not corrupt a high-Z bus between transactions | **GE.6** \|I\| ≤ 100 nA at 25 °C and ≤ 1 µA at 125 °C over 0 ≤ VPAD ≤ VDDIO, corner ff / 3.63 V; flagged as a Monte Carlo candidate | **fit** (new row in this pass) |
| Pull-up/down | not required in v1 | **GF.3** one weak pull, selectable up or down, active only while OE is inactive, up and down mutually exclusive; **GE.10** 20–60 kΩ at VDDIO/2, fallback 10–100 kΩ | **fit** — more than we require. Note it interacts with the sequencing row above: a pull is only powered once VDDIO is up |
| Pin mapping | pad cells for DQ/RWDS/CK/CS#/RESET# physically adjacent so their delays match | **CELL.2** uniform 80 µm pitch for every pad cell, ring assembly treated as a placement problem; **CELL.1** a single GPIO cell type. No per-signal mapping or ordering | **partial** (was "gap"). A uniform pitch and one GPIO cell type make matched delays *plausible* — same cell, same geometry — but adjacency and ordering are still ring-level and unspecified, and nothing states that matching follows from sameness |
| Corner set | decision [0004](decisions/0004-pvt-corner-set.md): tt/ff/ss/fs/sf, −40 … +125 °C, I/O supply ±10 % | **PVT.1–PVT.5** 75 named corners: 5 process (tt/ff/ss/sf/fs) × 3 temperatures (−40 / **25** / 125 °C) × 5 supply codes (nn/hh/ll/hl/lh, cross-supply codes included to stress the level shifter) | **mostly fit.** Process set identical. Two differences to settle at ratification: io-ring samples the mid temperature at **25 °C** where decision 0004 says **27 °C**, and io-ring names **cross-supply** codes (VDDIO high with VDD low and vice versa) that 0004 does not. The cross-supply codes are the level-shifter stress points, so they are worth adopting |

## Two conflicts with the device interface, found 2026-11-14

Both surfaced only once the interface definition was actually obtained (see
[device-model-params.md](device-model-params.md) for the locator and citations).
Neither is io-ring's fault, and neither is settled here — a Builder does not get
to pick a side, and no row above is relaxed to make the conflict go away. Both
are owed a decision record before ratification.

Both conflicts below are **pad-side**. A third gap found in the same pass,
**C3** — this spec's +125 °C corner lies outside the device's published
`tCSM` thermal basis — is not a pad matter and is recorded in
[decisions/0004](decisions/0004-pvt-corner-set.md), on the same footing.

### C1 — Input slew rate: the pad is far too slow at the slow corner

Table 9.1 note 1 of the interface definition (p. 32) states that **all** its AC
timings — every tIS, tIH, tCKD, tDSS figure this spec consumes — "assume an
input slew rate of 2 V/ns". Table 9.3 note 1 (p. 33) allows ≥ 1 V/ns for a
single-ended CK, which is the clock this spec chose (decision 0001).

Against io-ring's GE.3, taking 20–80 % of a 2.97 V swing (1.78 V) as the
measurement band:

| Corner / bound | tr,tf (20–80 %) | Implied slew | vs. 2 V/ns |
|---|---|---|---|
| GE.3 target, ss / 125 °C / 2.97 V | ≤ 3 ns | ≥ 0.59 V/ns | **~3.4× too slow** |
| GE.3 fallback | ≤ 5 ns | ≥ 0.36 V/ns | ~5.6× too slow |
| GE.4 minimum, ff / −40 °C / 3.63 V | ≥ 0.8 ns | ≤ 2.72 V/ns | meets it only here |

To reach 2 V/ns at 2.97 V the pad would need 20–80 % in ≤ 0.89 ns — which all
but collides with GE.4's ≥ 0.8 ns floor at the *fast* corner, leaving a
0.80–0.89 ns window across the whole PVT space. A single fixed-strength pad into
10 pF will not hold that.

Two things keep this from being a hard contradiction, and both are honest gaps
rather than escapes:

1. **The measurement band is not stated.** The source says "2 V/ns" without
   naming the fraction of swing it is measured over; io-ring's GE.3/GE.4 use
   20–80 %. The ratio above is therefore approximate, not exact.
2. **The figure is not tabulated at 50 MHz.** Table 9.1's columns are
   200 / 166 / 133 / 100 MHz only, and 2.0 V/ns is listed for all of them. There
   is no 50 MHz column, so **nothing read says what slew a 50 MHz bus needs.**
   It is plausible that a slower edge is fine at 50 MHz — the setup/hold windows
   are proportionally far larger — but that is an inference, not a cited value,
   and this spec does not get to assume it.

**Resolving it is an experiment, not an argument**: characterize the pad's
actual slew into the real load, then show the write-path setup/hold still closes
at 50 MHz with that slew, against a model whose tIS/tIH are the 100 MHz column
values. Until then, every write-timing claim in this repo rests on a slew
assumption it has not met. This is the strongest argument yet that the pad
characterization is on the critical path, and it is now reason **(5)** in the
ask below.

### C2 — I/O supply tolerance exceeds the device's range

The device's 3.0 V supply range is **2.70–3.60 V** (§8.3.3, p. 28). This spec
and io-ring both say 3.3 V **±10 %**, i.e. up to **3.63 V**. On a shared I/O
rail — the normal arrangement, and what decision 0002 implies — the high corner
sits 0.03 V outside what the device permits. The device's range corresponds to
3.30 V **+9.1 % / −18.2 %**.

Three ways out, none chosen here: tighten the shared-rail tolerance to +9 %;
lower the I/O nominal (3.15 V ±10 % is 2.84–3.47 V, inside the device range on
both sides and still inside io-ring's SUP.1 operating window); or state that the
device sits on its own rail and specify the level relationship across the two.
This belongs in a revision of decision 0002, since it changes what "3.3 V-class"
commits this controller to.

## The ask, restated

The four open gaps are now narrower and more specific than "no pad data". In
priority order for this controller:

1. **Pad-to-pad delay matching** between two instances of the GPIO cell, over
   the corner set — the `e_pad` term. Nothing upstream bounds it today.
2. **Delay spread**, i.e. a *minimum* as well as a maximum for GE.7 and GE.8,
   at the fast corner as well as the slow one, with rise and fall separated.
3. **Output-enable timing**, OE-to-valid and OE-to-Hi-Z, min and max.
4. **Supply-sequencing consequence** for a pad that must hold a reset level
   before the core supply is up.
5. **Achievable output slew rate** into the real load, across the corner set —
   not just the tr/tf ceiling of GE.3 but what the pad actually does, because
   conflict **C1** above means the device's whole AC timing set is predicated on
   a slew this pad may not reach.

(1) and (2) are what read capture consumes; a controller cannot close timing at
the pins against a one-sided ceiling. All four are now *characterizable* — the
cell is netlisted and drawn, so they are ngspice runs against an existing
netlist rather than requests for a cell that does not exist.

Pad delay figures must be matched between the input and output sides: this
controller assumes the DQ and RWDS pads are the same cell, which **CELL.1**
(one GPIO cell type) supports.

## Gap filing

`2AMLogic/sky130-io-ring#7` — "Pad timing data needed by a DDR memory-controller
consumer (delay, spread, OE timing, drive)". **Open**, carrying `loom:blocked`:
that repo parked it on its own issue #2 (spec ratification), and its curator
note gives "no GPIO cell exists yet" as the second reason. **That second reason
is now stale** — the GPIO cell is netlisted and drawn at `1aecfa74`. Updated
upstream with the restatement above, since what we are asking for has changed:
the drive-strength part of the original filing is answered by GE.1/GE.2, and the
delay part is now a request for a spread and a matching figure rather than for
any figure at all.
