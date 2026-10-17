# Behavioural device-model timing parameters (DRAFT)

The model is written in `verification/` from the public interface
definition. No vendor model is imported and no part is named or targeted.

**Source** (public interface definition): *HyperBus Specification*, Cypress
Semiconductor (now Infineon), document 001-99253, Rev. *C, May 2016,
<https://www.mouser.lt/pdfdocs/cypress_hyperbus_specification.pdf>.

**Verification status of this draft: the numeric values are NOT yet
transcribed.** The document fetch timed out while drafting this change, so no
value is entered from memory. Each row below must be filled from the cited
document's AC timing table with its table number before this file is
ratified; until then the row reads `TBD(src)`.

| Parameter (symbol) | Meaning | Model use | Value | Source section |
|---|---|---|---|---|
| CK period (tCK) | clock period | min period check | TBD(src) | AC timing table |
| CS# setup to CK (tCSS) | CS# low to first CK | checks CA start | TBD(src) | AC timing table |
| CS# hold after CK (tCSH) | last CK to CS# high | end of burst | TBD(src) | AC timing table |
| CS# high between transactions (tCSHI) | min CS# high time | rejects short gaps | TBD(src) | AC timing table |
| CS# low max (tCSM) | max time CS# may stay low | flags violation; drives controller row 9 | TBD(src) | AC timing table |
| Read-write recovery (tRWR) | CS# high to next access | recovery check | TBD(src) | AC timing table |
| CS# low to RWDS valid (tDSV) | RWDS valid after CS# | extra-latency sample | TBD(src) | AC timing table |
| RWDS-to-data skew (tDSS, tDSH) | read data vs RWDS edge | model drives RWDS edge-aligned with data within this skew | TBD(src) | AC timing table |
| CK-to-data/RWDS output delay (tCKD, tCKDS) | read output delay from CK | places data at the pins | TBD(src) | AC timing table |
| DQ setup/hold to CK (tIS, tIH) | write setup/hold | write capture checks | TBD(src) | AC timing table |
| Initial latency count | clocks from CA to data; doubled when RWDS high in CA | latency model | TBD(src) | latency section |
| Reset / power-up time | time before first access | power-up checks | TBD(src) | reset section |

Model rules: every check names the parameter above; a violation fails the
testbench. The model has fault-injection knobs for the skew values so the
read-capture margin can be swept.

Nothing in `spec/` makes any claim about conformance to a specific device.
