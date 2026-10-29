# Clock requirements (DRAFT)

Comparison read at `2AMLogic/sky130-pll` commit
`76a4b68556f83ea0710e9fa16abf44e28f89d3bc` (named in issue #2), file
`spec/target-spec.md`. Its HEAD on 2026-10-17 is
`4c20e8e2e787d2f5d7dc36f3c5928bb4dcb6d4ce`; this comparison reads the pinned
commit, not HEAD. Only rows 0, 1, 9, 19, 20 of that spec are ratified, so
every other PLL figure below is a starting point.

| Requirement | Value needed | sky130-pll at 76a4b68 | Fit / gap |
|---|---|---|---|
| Frequency | 50 MHz (fallback 25, stretch 100) from the core clock | row 2 band 10–200 MHz, DRAFT, not re-derived | **fit if the band holds**; unproven |
| Supply | 1.8 V ±10 % core | row 1 ratified 1.62–1.98 V | **fit** |
| Phase / multi-phase | a 90° version of CK for write data centring, or a 2× clock to derive it | single output `CLK`; no 90° or 2× output in the spec | **gap**: the controller instead derives 90° with a delay element (target-spec row 14); a 4× or quadrature output would remove that. Tolerance: [clock-phase-requirement.md](clock-phase-requirement.md) |
| Duty cycle | 45–55 % | row 14, DRAFT | **fit if ratified** |
| Jitter | period jitter small against the margin in target-spec row 12; proposal ≤ 1 % RMS | row 9 ratified ≤ 1.0 % RMS, DC-quiet supply | **fit**, with caveat: the PLL figure assumes a DC-quiet supply, and an I/O-switching core supply is not |
| Output drive | drives clock tree buffer | row 15, DRAFT; open issue 2AMLogic/sky130-pll#232 reports `CLK` is the raw VCO node | **gap** until an output stage exists |
| Lock indication | a `lock` status to hold the controller in reset | row 16, DRAFT | **fit if ratified** |
| Reference | n/a here | 1–25 MHz | not our concern |

The controller can also take its clock from the chip input directly; the PLL
is not required for 25 or 50 MHz if the board supplies one. Gaps are filed on
`2AMLogic/sky130-pll`.

Gap issue filed: https://github.com/2AMLogic/sky130-pll/issues/332
