# 0006 CLK90 / write-path clock requirement

Status: proposed (unratified). Issue #39.

## Decision
Record the write-path tolerance as [clock-phase-requirement.md](../clock-phase-requirement.md):
the CK-to-data phase window, the write setup/hold it protects (tIS/tIH,
transcribed from the cited interface definition into `device-model-params.md`),
and the CK/CLK90 jitter allowance, at 25, 50 and 100 MHz. Derivation:
window = T/4 ± (T/4 − tIS − pad, skew and jitter terms). At 50 MHz that is
90° ± 72° before the unmeasured terms.

## Consequences
- tIS/tIH are carried from the 100 MHz column to 50 and 25 MHz because the
  source tabulates no lower column; that is a stated assumption.
- The pad, skew and relative-jitter terms are unmeasured. The requirement is
  not a claim that any corner passes; it is the tolerance a clock source and
  the pad characterization are judged against.
- No ratified row is changed or relaxed. The 20 % figure in target-spec row 12
  stays a proposal. `clock-interface.md` row "Phase / multi-phase" gains a
  pointer only; its fit/gap wording is unchanged.
- Rejected: simulating a PLL or pad here (no `consumes:` edge). Rejected:
  filling values from memory where the source could not be read.
- Source revision (Rev. \*H) differs from the Rev. \*C cited earlier; a
  reviewer should confirm Rev. \*C agrees before ratifying.
