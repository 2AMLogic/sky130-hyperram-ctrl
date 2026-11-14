# Behavioural device-model timing parameters (DRAFT)

The model is written in `verification/` from the public interface
definition. No vendor model is imported and no part is named or targeted.

## Source and provenance

**Source** (public interface definition): *HyperBus™ Specification — Low Signal
Count, High Performance DDR Bus*, Cypress Semiconductor (now Infineon),
document **001-99253 Rev. \*H**, revised **2019-02-06**, 44 numbered pages.

**Locator, recorded 2026-11-14** (this is the thing that was missing):

```
https://www.infineon.com/assets/row/public/documents/10/57/\
infineon-hyperbus-specification-low-signal-count-high-performance-ddr-bus-\
additionaltechnicalinformation-en.pdf
```

Retrieved and verified on 2026-11-14. The file carries one extra Infineon
rebranding cover sheet ahead of the document, so the PDF has **45** physical
pages while the document numbers itself "Page *n* of 44". Identification
checks run on the retrieved file: PDF title
`HYPERBUS SPECIFICATION LOW SIGNAL COUNT, HIGH PERFORMANCE DDR BUS`, author
`Cypress`, and the footer of every page reads
`Document Number: 001-99253 Rev. *H … Revised February 06, 2019`.

This matches, exactly, the copy issue #39 recorded reading on 2026-10-29
("Rev. \*H, 2019-02-06, 44 pages, Infineon-hosted") whose URL was never written
down. The provenance gap that left is now closed.

### Page-number convention (and a correction)

**Page numbers below are the document's own printed numbers** (`Page n of 44`),
not PDF page indices. Because of the extra cover sheet, `PDF index = printed
page + 1`.

The three rows filled for #39 cited **PDF indices**, so each was one too high:
Table 9.2 was cited as p. 34 and is on printed **p. 33**; Table 9.4 as p. 37 and
is on printed **p. 36**; Table 9.5 as p. 40 and is on printed **p. 39**. The
table numbers were correct. Corrected throughout this file, and in
[clock-phase-requirement.md](clock-phase-requirement.md), which inherited them.

### Revision of record

This spec now cites **Rev. \*H** — the revision that was actually read, twice,
by two sessions. It previously named Rev. \*C (May 2016) in the `Source` line
while quoting values from Rev. \*H, which is the mismatch the #2 record flagged.
**Rev. \*C has never been read by this repo and is not cited anywhere in it
now**, so there is no undiffed mix left: every value below comes from the single
Rev. \*H copy identified above. Rev. \*C remains unread; if a ratifier wants the
two revisions diffed, that is a separate piece of work and must not be assumed
done.

### URLs that do not work — do not retry

| URL | Result | Probed |
|---|---|---|
| `www.mouser.lt/pdfdocs/cypress_hyperbus_specification.pdf` (the old `Source`, Rev. \*C) | HTTP/2 `INTERNAL_ERROR`; 0 bytes with `--http1.1` | 2026-10-17, 2026-11-14 (×2) |
| `www.mouser.com/pdfdocs/cypress_hyperbus_specification.pdf` | `000`, 0 bytes | 2026-11-14 |
| `www.farnell.com/datasheets/3681666.pdf` | `000`, 0 bytes | 2026-11-14 |
| `www.cypress.com/file/213356/download` | HTTP/2 `INTERNAL_ERROR` | 2026-11-14 |
| Internet Archive availability API, all three distributor URLs | no snapshots. The fuller CDX search could not run: IA was returning "temporarily offline" | 2026-11-14 |

The Infineon locator above also **refuses a plain `curl`** — it answers `202`
with 0 bytes, which is a bot challenge, not a 404. It was retrieved with an
ordinary browser-class fetch. A future session that gets `202`/0 bytes should
change client, not conclude the document is gone.

### Sources deliberately rejected

Several HyperRAM / HyperFlash **part datasheets** are reachable and tabulate
these same parameters. They are **not** used here: CLAUDE.md requires the model
be written from the public *interface definition* and forbids naming or
targeting a particular memory part. Rejected deliberately, not overlooked.

## Reading the tables

Tables 9.4 (read) and 9.5 (write) tabulate columns at **200 / 166 / 133 /
100 MHz only**. 100 MHz is the slowest tabulated clock, so for the 50 MHz target
and 25 MHz fallback the 100 MHz column is carried forward; each row below says
so where it matters. Table 9.2 (clock) is the one exception — it *does* carry a
50 MHz column, with a restriction noted in that row.

Table 9.1 (p. 32) gives the AC **test conditions** these numbers are measured
under: output load `CL` = 20 pF at 100 MHz (15 pF at 200 MHz), input pulse
levels 0.0–VCCQ, timing referenced to VCCQ/2, and — note 1 — **"All AC timings
assume an input slew rate of 2 V/ns"**. The document does *not* state voltage or
temperature conditions for these parameters; §9.3.3 and §9.3.5 defer those to
device datasheets. (An earlier note in `clock-phase-requirement.md` said the
Table 9.1 voltage/temperature conditions "were not transcribed" — they do not
exist to transcribe. The 2 V/ns slew assumption does, and it has consequences:
see [pad-interface.md](pad-interface.md).)

## Parameters

| Parameter (symbol) | Meaning | Model use | Value | Source section |
|---|---|---|---|---|
| CK period (tCK) | clock period | min period check | min 20.00 ns (50 MHz), 10.00 ns (100 MHz), 7.50 (133), 6.00 (166), 5.00 (200). Half period tCKHP 0.45–0.55 tCK (4.50–5.50 ns at 100 MHz, 9.00–11.00 ns at 50 MHz). Jitter: note 1, "Clock jitter of ±5 percent is permitted". **The 50 MHz column exists but note 2 restricts it**: "50-MHz timings are only relevant when a burst write is used to load data during a HyperFlash Word Program command" — so at 50 MHz the tabulated tCK/tCKHP are citable, but the rest of the AC set is not tabulated there. 25 MHz (40 ns) is not tabulated at all; it is slower than every column, so the min-period checks hold | Table 9.2 "Clock Timings", **p. 33** |
| CS# setup to CK (tCSS) | CS# low to first CK rising edge | checks CA start | min **3.00 ns** at 100 MHz (3.00 at 133, 3.00 at 166, 2.00 at 200); no max. Carried to 50 and 25 MHz | Tables 9.4 **p. 36** and 9.5 **p. 39** (identical) |
| CS# hold after CK (tCSH) | last CK falling edge to CS# high | end of burst | min **0 ns** at every column; no max. Table 9.4 note 1 qualifies it: the device works with 0, but the master "must generally remain driven Low (active) … longer, so that data remains valid long enough to account for tCKD, tCKDS, and the master interface phase shifting of RWDS", needing "one or more additional clock periods". **So 0 is not a usable controller target** — the controller's own read-capture delay sets it | Tables 9.4 **p. 36**, 9.5 **p. 39**; note 1 on p. 36 |
| CS# high between transactions (tCSHI) | min CS# high time | rejects short gaps | min **10.00 ns** at 100 MHz (7.50 at 133, 6.00 at 166, 5.00 at 200); no max. Table 8.3 states the same 10 ns min as a generic power-on-reset-related figure. Carried to 50 and 25 MHz | Tables 9.4 **p. 36**, 9.5 **p. 39**; Table 8.3 **p. 30** |
| CS# low max (tCSM) | max time CS# may stay low | flags violation; drives controller row 9 | max **4.00 µs** for *Industrial* temperature and **1.00 µs** for *Industrial Plus*, identical in all four frequency columns. §8.3.1 defines Industrial as −40…+85 °C and Industrial Plus as −40…+105 °C. **This spec's corner set is −40…+125 °C, which §8.3.1 calls *Extended*, and tCSM is not tabulated for Extended.** Note the direction: the two published figures fall **4× for a +20 °C step**, and Table 3.2 note 1 ties the row count to a *"distributed refresh interval for HyperRAM memory"* — a retention limit, which shortens as temperature rises. So this bound **tightens** with temperature, and **1.00 µs is therefore not the conservative choice at +125 °C**; the same trend past +105 °C implies a bound below it, by an amount the source does not publish. The model takes **1.00 µs as a default on an explicitly *Industrial Plus* basis**, and the +125 °C point of this spec's corner set is **not covered for this row** — an open gap (**C3**), owed a decision record before ratification, not a settled choice. At 50 MHz 1.00 µs is 50 clock periods; at 25 MHz, 25 | Tables 9.4 **p. 36**, 9.5 **p. 39**; temperature ranges §8.3.1 **p. 28**; refresh-interval note Table 3.2 note 1 **p. 10** |
| Read-write recovery (tRWR) | CS# high to next access | recovery check | min **40.00 ns** at 100 MHz (37.50 at 133, 36.00 at 166, 35.00 at 200); no max. Carried to 50 and 25 MHz. §3.2 adds the rule: the master "must start driving CS# Low only at a time when the CA1 transfer will complete after tRWR is satisfied" — i.e. tRWR is measured to the *end of CA1*, not to CS# falling | Tables 9.4 **p. 36**, 9.5 **p. 39**; §3.2 **p. 12** |
| CS# low to RWDS valid (tDSV) | RWDS valid after CS# | extra-latency sample | max **12.00 ns** at 100 MHz (12.00 at 133, 12.00 at 166, 5.00 at 200); no min. Carried to 50 and 25 MHz | Tables 9.4 **p. 36**, 9.5 **p. 39** |
| RWDS-to-data skew (tDSS, tDSH) | read data valid/invalid vs the RWDS edge | model drives RWDS edge-aligned with data within this skew | both tDSS and tDSH are **−0.80 … +0.80 ns** at 100 MHz (±0.60 at 133, ±0.45 at 166; at 200 MHz only a `+0.40` max is given, with no min). Read table only — on writes RWDS is a mask, not a strobe. Figure 9.6 note 4: this is "the potential skew between the clock to data delay tCKD, and clock to data strobe delay tCKDS"; aside from it the tCKD/tCKDI/tCKDS values "track together (vary by the same ratio) because RWDS and Data are outputs from the same device under the same voltage and temperature conditions" — **the justification for a tracking, not independent, model of the two paths** | Table 9.4 **p. 36**; tracking rule from Figure 9.6 note 4, **p. 35** |
| CK-to-data/RWDS output delay (tCKD, tCKDS) | read output delay from CK | places data at the pins | tCKD **1.00–5.50 ns** and tCKDS **1.00–5.50 ns** in the 100 MHz column (1.00–5.50 at 133, 1.00–5.50 at 166, 1.20–5.00 at 200). No 50 or 25 MHz column | Table 9.4 **p. 36** |
| DQ setup/hold to CK (tIS, tIH) | write setup/hold | write capture checks | min **1.00 ns** each in the 100 MHz column (0.80 at 133, 0.60 at 166, 0.40 at 200); no max. No 50 or 25 MHz column, so 1.00 ns is carried to 50 and 25 MHz **as an assumption** (see [clock-phase-requirement.md](clock-phase-requirement.md)) | Tables 9.4 **p. 36** and 9.5 **p. 39** (identical) |
| Initial latency count | clocks from CA1 capture to the start of data transfer; doubled when RWDS is high during CA | latency model | **No single number exists, by the document's design.** §3.2: "The initial latency count required for a particular clock frequency is device dependent. Refer to the device data sheet…". What the interface *does* define is the encodable set: CR0[7:4] selects **3, 4, or 5 … 16 clocks** (`1110` = 3, `1111` = 4, `0000`–`1011` = 5–16; `1100`/`1101` reserved), with "the number of initial latency options implemented and the POR or reset default initial value … device dependent". CR0[3] *Fixed Latency Enable* selects variable (0) or fixed (1, the default). RWDS low during CA inserts one latency count, RWDS high inserts an additional one. **The model takes the latency count as a configurable parameter over 3–16, not a constant** — which is what target-spec rows 4 and 7 already assume. Table 5.3 is labelled "**Example** Configuration Register Bit Assignments" and §5.2 says register location and structure are device dependent, so the *encoding* is illustrative; the 3–16 range and the RWDS doubling rule are the normative parts | §3.2 **p. 12**; §5.2 and Table 5.3 **pp. 18–19** |
| Reset / power-up time | time before the first access | power-up checks | HyperRAM **tVCS** max **150 µs** (VCC and VCCQ ≥ minimum to first access); HyperRAM **tRPH** min **400 ns** (RESET# low to CS# low); **tRP** min **200 ns** (RESET# pulse width); HyperRAM **tRH** min **200 ns** (RESET# high to CS# low); **tCSHI** min **10 ns** before the first access. Note 4: bus transactions "are not allowed during the power-up reset time (tVCS)", and the device "requires CS# high for tCSHI before going low for the first access". tVCS is a *maximum* — the controller must wait at least that long, so 150 µs is the figure the configurable power-up interval of target-spec row 8 must be able to cover | Table 8.3 "Power On Reset Parameters" **p. 30** |

### Additional rows transcribed in the same pass

Not among the ten the issue listed, but needed by the same model and cited from
the same copy, so recorded here rather than left to be re-fetched.

| Parameter (symbol) | Meaning | Value (100 MHz column unless stated) | Source section |
|---|---|---|---|
| tACC | HyperRAM read / write initial access time | max **40.00 ns** (37.50 at 133, 36.00 at 166, 35.00 at 200) | Tables 9.4 **p. 36**, 9.5 **p. 39** |
| tDQLZ | clock to DQ low-Z | min **0 ns**, no max | Table 9.4 **p. 36** |
| tCKDI | CK transition to DQ invalid | **0–4.30 ns** (0–4.50 at 133, 0–4.60 at 166, 0.40–4.20 at 200) | Table 9.4 **p. 36** |
| tDV | data valid window | min **3.30 ns** (2.37 at 133, 1.70 at 166, 1.45 at 200). Defined as the lesser of `tCKHP min − tCKD max + tCKDI max` and `tCKHP min − tCKD min + tCKDI min` — **this is the eye the read-capture margin of target-spec row 12 is a fraction of** | Table 9.4 **p. 36** |
| tOZ | CS# inactive to DQ high-Z | max **6.00 ns** (6.00 at 133/166, 5.00 at 200) | Table 9.4 **p. 36** |
| tDSZ | CS# inactive (or clock) to RWDS high-Z | max **6.00 ns** (6.00 at 133/166, 5.00 at 200) | Tables 9.4 **p. 36**, 9.5 **p. 39** |
| tDMV | data mask valid, RWDS setup to end of initial latency | min **0 ns**, no max | Table 9.5 **p. 39** |

### Device-side DC and supply figures that constrain the pads

These are not model timing parameters, but they bound what
[pad-interface.md](pad-interface.md) may ask for, so they are recorded with
their citation rather than restated from memory elsewhere.

| Figure | Value | Source section |
|---|---|---|
| 3.0 V supply range (VCC and VCCQ) | **2.70 V to 3.60 V** | §8.3.3 **p. 28** |
| 1.8 V supply range (VCC and VCCQ) | 1.70 V to 2.00 V | §8.3.2 **p. 28** |
| Input levels | VIL max `0.30 × VCC`; VIH min `0.70 × VCC`, max `VCC + 0.30` | Table 8.2 **p. 28** |
| Input / output leakage | ILI ±2.00 µA, ILO ±1.00 µA | Table 8.2 **p. 28** |
| Required input slew rate | **2 V/ns** assumed by all AC timings; CK/CK# differential ≥ 4 V/ns, and ≥ 1 V/ns for a single-ended CK measured per Table 9.3 note 1 | Table 9.1 note 1 **p. 32**; Table 9.3 note 1 **p. 33** |
| Ambient temperature classes | Industrial −40…+85 °C; Industrial Plus −40…+105 °C; Extended −40…+125 °C; Hot −40…+145 °C | §8.3.1 **p. 28** |

**Two consequences for this spec, both newly visible and neither resolved
here** (a Builder does not get to settle them, and no row is relaxed to absorb
them):

1. **I/O supply tolerance.** This spec's I/O supply is 3.3 V ±10 %, i.e.
   2.97–3.63 V (decision 0002, and io-ring's `SUP.1`). The device's own VCCQ
   range is **2.70–3.60 V**. If the controller and the device share the I/O
   rail — the normal arrangement — then the high corner, **3.63 V, is outside
   the device's permitted supply range** by 0.03 V. The device permits at most
   +9.1 % on a 3.30 V nominal. Either the shared-rail tolerance tightens, or the
   spec must say the device sits on a separate, tighter rail. Raised in
   [pad-interface.md](pad-interface.md) and owed a decision record before
   ratification.
2. **Input slew rate.** All the AC timings above assume **2 V/ns** into the
   device. The pad edge-rate target this spec is comparing against is far
   slower than that over most of its corner space. See
   [pad-interface.md](pad-interface.md) → edge-rate row; it is now a conflict,
   not a fit.

## Model rules

Every check names the parameter above; a violation fails the testbench. The
model has fault-injection knobs for the skew values (tDSS/tDSH, tCKD/tCKDS) so
the read-capture margin can be swept. Per Figure 9.6 note 4 (p. 35) the model varies
tCKD, tCKDI and tCKDS *together* by a common ratio and applies tDSS/tDSH as the
residual independent skew, rather than treating the strobe and data paths as
independent — that is what the source states those paths do.

Nothing in `spec/` makes any claim about conformance to a specific device.
