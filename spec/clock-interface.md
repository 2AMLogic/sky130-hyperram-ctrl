# Clock requirements (DRAFT)

Comparison read at `2AMLogic/sky130-pll` commit
`37484b328e16a4afddf4e96d3647ec191be902eb`, which was that repo's HEAD on
2026-11-13 and was re-confirmed as HEAD on 2026-11-14 when this comparison was
written. Files read: `spec/target-spec.md` and the decision records
`DR-003`, `DR-006` … `DR-010`.

This supersedes the earlier comparison against `76a4b68556f83ea0710e9fa16abf44e28f89d3bc`
(the commit named in issue #2, read 2026-10-17). Since that pin the sibling has
**answered this repo's own gap filing** (`2AMLogic/sky130-pll#332`), so several
rows below change verdict rather than merely changing commit.

Ratified rows in that spec are **0, 1, 9, 19, 20** (by `DR-001`, `DR-002`,
`DR-006`, `DR-003`). Every other figure quoted below is DRAFT in the sibling and
is a starting point, not a commitment — including the output band this
controller depends on.

| Requirement | Value needed | sky130-pll at `37484b32` | Fit / gap |
|---|---|---|---|
| Frequency | 50 MHz (fallback 25, stretch 100) from the core clock | row 2 band 10–200 MHz, **still DRAFT and still not re-derived on sky130** ("NOT assumed to hold"). `DR-009` gap 3 records 25 / 50 / 100 MHz as **required in-band operating points** for the tuning-range campaign that will ratify row 2, each to be reported as a pass or a recorded miss | **fit if the band holds; still unproven.** Improvement since `76a4b68`: this controller's three operating points are now named campaign inputs upstream rather than merely lying inside a draft band. No number changed |
| Supply | 1.8 V ±10 % core | row 1 **ratified** 1.62–1.98 V, single supply domain | **fit** |
| Phase / multi-phase | a 90° version of CK for write-data centring, or a 2× clock to derive it | **an open upstream proposal, no longer a bare gap.** `DR-009` (proposed, 2026-10-17) disposed of our gap as "not in v1": keep a single `CLK`, consumer derives the quarter-period clock with a delay element — i.e. it endorses what [target-spec.md](target-spec.md) row 14 already does. The **operator declined that default on 2026-10-19**, and `DR-010` (proposed 2026-10-19, amended 2026-10-20 by their #344) now proposes `CLK` + `CLK90` from a 2× ring with a reset-defined I/Q ÷2, against a multiplied-clock alternative; analysis in their `docs/phase-output-proposal.md`. Their #332 is **open and `loom:operator`** — the ruling has not been made | **gap, with a named fallback.** Our row 14 delay-element derivation stands whether or not `DR-010` is adopted, so nothing here blocks on the ruling. See the note below on what `DR-010` says it is missing from us |
| Duty cycle | 45–55 %. **Now cited, not asserted**: the device interface specifies tCKHP = 0.45–0.55 tCK (Table 9.2, p. 33 — see [device-model-params.md](device-model-params.md)), so this requirement comes from the device, and the 45–55 % figure is the device's own | row 14, DRAFT; `DR-008` left it DRAFT deliberately and gave it a provisional characterization load (next row) | **fit if ratified.** The two specs' numbers are identical, and they now have a common source rather than coinciding by chance |
| Jitter | period jitter small against the margin in target-spec row 12; proposal ≤ 1 % RMS | row 9 **ratified** ≤ 1.0 % of the output period, RMS, at `CLK` in lock — **under a DC-quiet supply only** (ideal DC source, no applied AC ripple) | **fit for the DC-quiet condition.** The caveat this file used to assert on its own is now backed by the sibling's own record: `DR-006` states the **ripple-inclusive form is explicitly not ratified**, because ratified row 1 binds a *single* supply domain and so there is no dedicated VCO rail to write a ripple condition against. It is owed at row 13, which `DR-006` also leaves DRAFT by explicit decision. An I/O-switching core supply is therefore an **unquantified** condition upstream, not merely an unmentioned one |
| Output drive | drives a clock-tree buffer | row 15, DRAFT. `DR-008` (2026-10-15) authorized a **provisional 1 pF lumped characterization load** on `CLK` and a merged two-inverter output stage (`design/clk-buf`, their PR #302); their #232 is **still open** | **gap, narrowed.** `CLK` is no longer the raw VCO node and there is now a named load to write our requirement against — but 1 pF is a characterization contract, explicitly *not* a measured receiver and *not* a pad/package model (no bond-wire L, no ESD, no series R). Rows 14/15 stay DRAFT; their #304 (clk_buf layout) is open |
| Lock indication | a `lock` status to hold the controller in reset | row 16, DRAFT; `DR-007` proposes a numeric contract and the row stays DRAFT | **fit if ratified** |
| Reference | n/a here | rows 3: 1–25 MHz CMOS | not our concern |

The controller can also take its clock from the chip input directly; the PLL is
not required for 25 or 50 MHz if the board supplies one. That remains the
reason none of the gaps above blocks this spec.

## What `DR-010` says it is missing, and that this repo already holds

`DR-010`'s 2026-10-20 amendment (their #344) corrects the proposed topology in a
way that matters to us: the quarter-cycle relationship is **conditional, not
exact by construction**. `CLK90` lags `CLK` by `180·D` degrees of the output
period (`D` = the 2× clock's high fraction) plus `180·δ/T2` for a flop
clock-to-output difference `δ` — so it is 90° only at 50 % input duty with
matched paths. The record then states that the interface "depends on a consumer
phase window that is not recorded in `DR-009`".

**This repo records that window.** [clock-phase-requirement.md](clock-phase-requirement.md)
bounds it: at 50 MHz the write path tolerates `d` anywhere in 1.0–9.0 ns
(18°–162°, i.e. 90° ± 72°) before the pad, core-skew and jitter terms are
subtracted, losing 18° per ns of those terms; 9°–171° at 25 MHz and 36°–144° at
100 MHz. It also works the `180·D` case directly: at D = 45 % the phase is 81°,
which lies inside the window at all three clocks and costs 1.0 / 0.5 / 0.25 ns
of budget at 25 / 50 / 100 MHz. So the `180·D` dependence `DR-010` flags is
**tolerable at 25 and 50 MHz** and is where accuracy starts to matter only at
the 100 MHz stretch.

Two consequences for this spec, neither of which relaxes a row:

1. Our requirement on a phase source is a **window, not a 90° point**. A source
   that is only roughly a quarter period satisfies the 50 MHz target.
2. The term that cannot be bounded yet is the **pad** term `e_pad`, not the
   clock term — see [pad-interface.md](pad-interface.md).

Supplied upstream on their #332 so the proposal has the input it says it lacks.

## Gap filings

- `2AMLogic/sky130-pll#332` — the three clock-interface gaps from this repo.
  **Open, `loom:operator`**: awaiting the operator ruling that `DR-009` /
  `DR-010` are proposed against. Updated with the phase window above.
- `2AMLogic/sky130-pll#232` — `CLK` was the raw VCO node. Open; materially
  progressed by `DR-008` and their PR #302.
