# CLK90 / write-path clock requirement (DRAFT)

Status: **DRAFT, unratified** (issue #39, decision [0006](decisions/0006-clk90-requirement.md)).
It states how far the clock that launches the write-path CK may sit from a
quarter period behind the data-launch clock, and how much jitter is allowed. It
does not design a clock source, and it does not touch any ratified row. The
read-capture margin of [target-spec.md](target-spec.md) row 12 (20 %) is a
separate proposal and is not used here.

## Source values (from [device-model-params.md](device-model-params.md))

Document 001-99253, Rev. \*H copy (the repo cites Rev. \*C; not read, see that
file). tIS = tIH = **1.00 ns** minimum, taken from the 100 MHz column of
Table 9.5, p. 40. The source tabulates no 50 or 25 MHz column for tIS/tIH, so
**1.00 ns is an assumption at 50 and 25 MHz**: it is the slowest tabulated
column, the tabulated minima grow as the clock slows (0.40, 0.60, 0.80, 1.00 ns
at 200, 166, 133, 100 MHz), and nothing read says a slower clock needs more. If
a device datasheet lists a larger 50 MHz value, the numbers below shrink by
that difference. tCK min is 10.00 ns (100 MHz) and 20.00 ns (50 MHz), Table 9.2,
p. 34; 40 ns at 25 MHz is the nominal period. Jitter: Table 9.2 note 1 says
"Clock jitter of ±5 percent is permitted"; the text read does not define
whether this is period, cycle-to-cycle or absolute jitter, so the reading below
is an assumption.

## Definitions

Write data is launched by the core clock CLK. CK at the device is CLK delayed by
`d` (the quarter-period delay, i.e. CLK90 through its pad). Data changes at
time 0 and is held for T/2 (DDR). The device samples on each CK edge, so the
data around the edge must be stable for tIS before it and tIH after it:

```
tIS + e_total  <=  d  <=  T/2 - tIH - e_total          (all at the pins)
```

`e_total` is the one-sided uncertainty of `d` (terms below). With
tIS = tIH the window is centred on `d = T/4` (90°). Writing `d = T/4 + e_nom`
(`e_nom` = nominal phase error, positive = late):

```
|e_nom| + e_pad + e_skew + e_jit  <=  B  =  T/4 - tIS
phase window (degrees, CK relative to the data launch) = 90° ± 360·(B - e_pad - e_skew - e_jit)/T
```

| Term | Meaning | Source | Status |
|---|---|---|---|
| `e_nom` | nominal CLK90–CLK phase error (incl. duty-cycle effect, see worked check) | the clock source | the quantity this document bounds |
| `e_pad` | spread of (CK output-pad delay − DQ output-pad delay) over all corners | [pad-interface.md](pad-interface.md) "Output delay and spread" | **UNMEASURED**: no ngspice result exists, io-ring gives no figure |
| `e_skew` | core-side skew between the CLK90-launched CK path and the CLK-launched DQ path (clock tree, flop clk→Q) | STA, once the design exists | **UNMEASURED** |
| `e_jit` | peak relative jitter between the CK edge and the data edge | the clock source | **UNMEASURED**; only an upper bound is stated below |

Every term is added linearly in the worst direction (no root-sum-square), so the
requirement is conservative. No design margin beyond the datasheet minimum is
added here; a margin policy is a ratification choice.

## (a) Allowed phase window and (b) the setup/hold it protects

With `e_pad = e_skew = e_jit = 0` (the best case; every unmeasured term only
narrows this):

| Bus clock | T | B = T/4 − tIS | Window for d (tIS ≤ d ≤ T/2 − tIH) | Phase window | Allowed `\|e_nom\|` | Per 1 ns of uncertainty the window loses |
|---|---|---|---|---|---|---|
| 25 MHz (fallback) | 40 ns | 9.0 ns | 1.0 – 19.0 ns | 9° – 171° (90° ± 81°) | 9000 ps | 9° each side |
| 50 MHz (target) | 20 ns | 4.0 ns | 1.0 – 9.0 ns | 18° – 162° (90° ± 72°) | 4000 ps | 18° each side |
| 100 MHz (stretch) | 10 ns | 1.5 ns | 1.0 – 4.0 ns | 36° – 144° (90° ± 54°) | 1500 ps | 36° each side |

Corner: tIS/tIH are datasheet minima, not process corners, so (a) and (b) are
the same number at every PVT point. The window must hold at **every** corner of
decision 0004 (all ngspice corners tt/ff/ss/fs/sf, −40 … +125 °C, core 1.8 V
±10 %, I/O supply per decision 0002), because `e_pad`, `e_skew` and `e_jit` vary
over them. The device-side voltage and temperature conditions of the tIS/tIH
rows (Table 9.1) were not transcribed. Recorded evidence for the three
uncertainty terms does not exist yet, so **no corner has been shown to meet
this requirement**.

Phase is quoted at the pins: a clock source only gets what is left after
`e_pad`, `e_skew` and `e_jit`. Example at 50 MHz: if those three sum to 1.5 ns,
the source's nominal phase must be within ±2.5 ns (±45°) of 90°.

## (c) CLK and CLK90 jitter allowance

| Bus clock | Device allowance on CK, ±5 % of tCK (assumed reading) | Share of B used if all of it were relative CK-to-data jitter |
|---|---|---|
| 25 MHz | ±2.0 ns | 22 % |
| 50 MHz | ±1.0 ns | 25 % |
| 100 MHz | ±0.5 ns | 33 % |

Two separate limits follow. (1) The CK seen by the device must stay within the
±5 % allowance. (2) The part of that jitter that is *relative* to the data edge
is `e_jit`, and it comes out of the same budget B as the phase error; it has no
separate limit here. Jitter common to CLK and CLK90 (same source, same supply
noise) cancels in `e_jit`; jitter that is independent between the two does not.

Cross-check with [clock-interface.md](clock-interface.md): the ratified PLL
period-jitter figure is ≤ 1.0 % RMS, so 5 % is five sigma. For illustration
only, assuming Gaussian jitter, a 3σ peak at 50 MHz is 0.6 ns of the 4.0 ns
budget. That is an arithmetic illustration of a ratified spec figure, not a
measurement of any block.

## Worked check: 45 % duty, 180·D° phase

If CLK90 is obtained by delaying CLK by half its high time, the phase is 180·D°;
at D = 45 % that is 81° (the example in the issue). `d = 81/360·T`. How a
particular clock source would make this edge was not read here.

| Bus clock | d at 81° | Setup slack d − tIS | Hold slack T/2 − d − tIH | Left for `e_pad + e_skew + e_jit` (smaller slack) | Best case at 90° |
|---|---|---|---|---|---|
| 25 MHz | 9.00 ns | 8.00 ns | 10.00 ns | 8.00 ns | 9.0 ns |
| 50 MHz | 4.50 ns | 3.50 ns | 4.50 ns | 3.50 ns | 4.0 ns |
| 100 MHz | 2.25 ns | 1.25 ns | 1.75 ns | 1.25 ns | 1.5 ns |

At D = 55 % (99°) setup and hold slack swap, so the residual is the same across
the 45–55 % duty band in the duty row of [clock-interface.md](clock-interface.md). Result: 81° lies inside the window at all three clocks, and the
duty-cycle effect costs 1.0 / 0.5 / 0.25 ns (25 / 50 / 100 MHz) of the budget.
Whether the design *meets* the requirement depends on the three unmeasured
terms; at 50 MHz they must total ≤ 3.5 ns, at 100 MHz ≤ 1.25 ns.

## Answer for the consumer

At 50 MHz the write path tolerates a CLK90 phase anywhere in 18°–162° before
pad, skew and jitter terms are subtracted (18° lost per ns of those terms). A
90° that is only roughly a quarter period, including the 180·D° case, is
sufficient at 25 and 50 MHz; the 100 MHz stretch is where the phase accuracy
starts to matter (36°–144°, 1.5 ns total budget). The pad term is the one that
cannot be bounded until the ngspice pad characterization exists.

## Assumptions (all of them)

1. tIS = tIH = 1.00 ns at 25, 50 and 100 MHz (100 MHz column; 50/25 not tabulated).
2. Data valid window is T/2 per beat; CK edge samples centre-aligned data; single-ended CK (decision 0001).
3. Uncertainty terms add linearly and in the worst direction.
4. The ±5 % jitter allowance is read as a bound on CK jitter relative to the nominal clock (definition not in the text read).
5. Source is Rev. \*H of the interface definition, not the Rev. \*C cited elsewhere.
6. `e_pad`, `e_skew`, `e_jit` are unmeasured; no claim is made that any corner passes.
