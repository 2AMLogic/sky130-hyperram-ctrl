# Behavioural device-model timing parameters (DRAFT)

The model is written in `verification/` from the public interface
definition. No vendor model is imported and no part is named or targeted.

**Source** (public interface definition): *HyperBus Specification*, Cypress
Semiconductor (now Infineon), document 001-99253, Rev. *C, May 2016,
<https://www.mouser.lt/pdfdocs/cypress_hyperbus_specification.pdf>.

**Verification status of this draft: partly transcribed (issue #39).** The
first draft could not fetch the document, so nothing was entered from memory.
For issue #39 a copy was read on 2026-10-29 from the Infineon-hosted file
(document 001-99253 **Rev. \*H**, 2019-02-06, 44 pages). It is a later
revision than the Rev. \*C named above; Rev. \*C itself was not read, so a
difference between the two revisions in these rows is unchecked. Only the
rows needed by [clock-phase-requirement.md](clock-phase-requirement.md) (tCK,
tIS/tIH, tCKD/tCKDS) are filled, each with the table number and page of the
Rev. \*H copy. Every other row stays `TBD(src)` and must be filled from the
document with its table number before this file is ratified.

Where the source tabulates columns only at 200/166/133/100 MHz (Tables 9.4,
9.5), the 100 MHz column is the slowest tabulated clock. Values for 50 and
25 MHz are **not published in those tables**; the rows below say which column
is used.

| Parameter (symbol) | Meaning | Model use | Value | Source section |
|---|---|---|---|---|
| CK period (tCK) | clock period | min period check | min 20.00 ns (50 MHz), 10.00 ns (100 MHz); half-period tCKHP 0.45–0.55 tCK; jitter ±5 % of tCK permitted (Table 9.2 note 1). 25 MHz (40 ns) is not tabulated: it is slower than the slowest listed column, so min tCK holds | Table 9.2 "Clock Timings", p. 34 |
| CS# setup to CK (tCSS) | CS# low to first CK | checks CA start | TBD(src) | AC timing table |
| CS# hold after CK (tCSH) | last CK to CS# high | end of burst | TBD(src) | AC timing table |
| CS# high between transactions (tCSHI) | min CS# high time | rejects short gaps | TBD(src) | AC timing table |
| CS# low max (tCSM) | max time CS# may stay low | flags violation; drives controller row 9 | TBD(src) | AC timing table |
| Read-write recovery (tRWR) | CS# high to next access | recovery check | TBD(src) | AC timing table |
| CS# low to RWDS valid (tDSV) | RWDS valid after CS# | extra-latency sample | TBD(src) | AC timing table |
| RWDS-to-data skew (tDSS, tDSH) | read data vs RWDS edge | model drives RWDS edge-aligned with data within this skew | TBD(src) | AC timing table |
| CK-to-data/RWDS output delay (tCKD, tCKDS) | read output delay from CK | places data at the pins | 100 MHz column: tCKD 1.00–5.50 ns, tCKDS 1.00–5.50 ns (200 MHz column: 1.20–5.00 ns). No 50 or 25 MHz column | Table 9.4, p. 37 |
| DQ setup/hold to CK (tIS, tIH) | write setup/hold | write capture checks | min 1.00 ns each in the 100 MHz column (0.80 at 133, 0.60 at 166, 0.40 ns at 200 MHz); no max. No 50 or 25 MHz column: 1.00 ns is carried to 50 and 25 MHz as an assumption (see clock-phase-requirement.md) | Table 9.5 "Write Timing Parameters", p. 40 (same values in Table 9.4, p. 37) |
| Initial latency count | clocks from CA to data; doubled when RWDS high in CA | latency model | TBD(src) | latency section |
| Reset / power-up time | time before first access | power-up checks | TBD(src) | reset section |

Model rules: every check names the parameter above; a violation fails the
testbench. The model has fault-injection knobs for the skew values so the
read-capture margin can be swept.

Nothing in `spec/` makes any claim about conformance to a specific device.
