# Pad-liberty STA record — spec open question (a)

**Question** (`spec/target-spec.md`, open question (a)): do the pinned PDK's
`sky130_fd_io` liberty views give OpenSTA arcs through the pad cells — i.e.
can static timing see from a core flop to the pad pin and from the pad pin to
a core flop — and at which corners?

**Answer: yes for the delay arcs** — `OUT -> PAD` and `PAD -> IN` are real
combinational arcs in the shipped `sky130_fd_io__top_gpiov2` liberty, and
OpenROAD's embedded OpenSTA reports full path tables through the pad
instance (named, not black-boxed) at the corners tried. **But the corner
coverage is the real result**: of the 21 `top_gpiov2` liberty corners the
pinned PDK ships, **exactly two** fall inside decision 0002's 3.3 V ±10 %
I/O-supply window (2.97–3.63 V) — a typical and a slow one — and **there is
no fast-corner pad liberty anywhere in that window**. Liberty therefore
yields a slow/max pad delay at the ratified supply but no fast/min
counterpart, so a min/max pad-delay spread (what table row 12 needs) still
requires the ngspice characterization; this is spec open question (a)'s own
"arcs … only at a corner subset" branch.

This record is the committed, reproducible form of that experiment. Tool
output per session is committed next to this file (`opensta-*.log`), and the
failed attempt to drive the experiment through the pinned `klt sta` is
committed under `klt-0.8.0-attempt/` (see [Tool gap](#tool-gap-klt-080)).

## Provenance

| Item | Value |
|---|---|
| Repo | `2AMLogic/sky130-hyperram-ctrl`, worktree for issue #98 off `origin/main` @ `00633b1` |
| PDK | open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` at `~/.ciel/sky130A` (the `CIEL_SKY130_VERSION` pin in `scripts/setup-env.sh`) |
| Engine | `openroad 26Q3-1510-g6cb3f2b704` (its embedded OpenSTA; there is no standalone `sta` binary and the host rules forbid installing one) |
| klt pin | `0.8.0` (`scripts/klt.sh`) |
| Date | 2026-11-14 |
| Inventory | `inventory.tsv` (regenerable; command in [Reproducing](#reproducing)) |

Numbers below are from the committed logs. They are evidence that the
*method* works and what the *coverage* is; they are **not** design figures —
see [Assumptions](#assumptions-stated) for what they depend on.

## Assumptions stated

1. **Pad cell: `sky130_fd_io__top_gpiov2`** — an experiment-local choice.
   Decision 0002 deliberately fixes no cell list ("The pad cell names are
   *not* fixed here: `2AMLogic/sky130-io-ring` draws its own cells and has
   not ratified a cell list (its `spec/` was empty at `9cf5d41`)"). This cell
   is the general-purpose bidirectional 3.3 V-class pad, it carries all
   three arc families this question needs (`OUT -> PAD`, `PAD -> IN`, and
   `OE_N` three-state arcs — the last being what row 14's output-enable
   timing will eventually need), and it is the `fd_io` cell behind the
   efabless wrapper `sky130_ef_io__gpiov2_pad` / `sky130_ef_io__gpiov2_pad_wrapped`
   (both shipped by the pinned PDK with the same 21-corner set —
   `inventory.tsv` rows for cells `gpiov2_pad` and `gpiov2_pad_wrapped`;
   the wrapper choice does not change the arc answer). Nothing here infers a
   cell list for the sibling.
2. **Control-pin ties** (in `padwrap.v`, identical in spirit for both pads;
   changing them changes the measured arcs):
   - Output pad `u_opad`: `OE_N=0` (active-low output enable), `INP_DIS=1`
     (receiver off), `DM=3'b110`, `SLOW=0` — the liberty indexes `OUT -> PAD`
     delay by per-mode `when` conditions (`!OE_N & DM & SLOW`), so this tie
     selects the `DM[2]&DM[1]&!DM[0] & !SLOW` output table; the six
     output-enabled codes the liberty models are `010`…`111` and `001` is
     input-only, which is what pins DM's role here (drive-strength semantics
     beyond that are the pad cell's own domain, not this experiment's).
   - Input pad `u_ipad`: `OE_N=1` (output driver off), `INP_DIS=0` (receiver
     on), `DM=3'b001` (input mode; the `PAD -> IN` arcs are conditioned only
     on `IB_MODE_SEL`/`VTRIP_SEL`, so this tie does not gate the measured
     arc), `IB_MODE_SEL=0`, `VTRIP_SEL=0` (normal CMOS input, low trip
     point).
   - Both: `HLD_H_N=1`, `HLD_OVR=0` (bus hold off), `ENABLE_H=1`,
     `ENABLE_INP_H=0`, `ENABLE_VDDA_H=1`, `ENABLE_VDDIO=1`,
     `ENABLE_VSWITCH_H=1` (enabled domains), `ANALOG_EN=0`, `ANALOG_SEL=0`,
     `ANALOG_POL=0` (analog mux off), `AMUXBUS_A/B` tied to VSS.
   - The analog access nodes (`PAD_A_NOESD_H`, `PAD_A_ESD_0_H`,
     `PAD_A_ESD_1_H`) and the ESD tie outputs (`TIE_HI_ESD`, `TIE_LO_ESD`)
     carry no timing arcs and are left unconnected at the wrapper boundary —
     stated, not silently dropped.
3. **Output load: 10.0 pF primary** on the output pad's `PAD` net, with 5.0
   and 20.0 pF runs to show the output-side delay moves with load (so no
   reader mistakes one load's number for a pad property). A board-level
   HyperRAM-class load is the eventual operating condition; picking its
   production value belongs to the sibling I/O ring, not to this tool
   experiment. The input-side `PAD -> IN` arc is load-independent at these
   loads (receiver input only).
4. **Core/pad corner pairing** (an explicit stated choice, because a `klt`-style
   `lib` map would be keyed on the *core* corner name while the pad liberty
   carries its own): each session pairs a `sky130_fd_sc_hd` core liberty
   with the `top_gpiov2` pad liberty whose process/temp/core-voltage fields
   match it and whose `vddio` field is the pad's own operating supply:
   `tt_025C_1v80` ↔ `tt_tt_025C_1v80_3v30`, `ss_100C_1v60` ↔
   `ss_ss_100C_1v60_3v00`. Constraints: ideal 20 ns clock on `clk`
   (clock-mode `ideal`; no wire parasitics — netlist-only session, no SPEF),
   `set_input_delay 0.0` on `pad_ipad`, `set_output_delay 0.0` on
   `pad_opad`, `set_load` on the output `PAD` net.

## Liberty inventory (AC 1)

`inventory.tsv` lists every `sky130_fd_io` liberty file the pinned revision
ships — **649 `.lib` files** across 26 cell names (plus the two
corner-less stub files `sky130_ef_io__analog_stubs.lib` and
`slices_stubs.lib`), with sha256 for each. Summary:

| Cell (family) | Corners | | Cell (family) | Corners |
|---|---|---|---|---|
| `fd_io top_analog_pad` | 34 | | `fd_io top_amuxsplitv2` | 23 |
| `fd_io top_lvclamp` | 31 | | `fd_io top_gpiovrefv2` | 23 |
| `ef_io vssd_lvc_clamped3_pad` | 28 | | `fd_io top_vrefcapv2` | 23 |
| `ef_io vssd_lvc_clamped_pad` | 28 | | `fd_io top_sio_macro` | 22 |
| `fd_io top_ground_lvc_wpad` | 28 | | `ef_io gpiov2_pad` | 21 |
| `ef_io vccd_lvc_clamped3_pad` | 27 | | `ef_io gpiov2_pad_wrapped` | 21 |
| `ef_io vccd_lvc_clamped_pad` | 27 | | `fd_io top_gpiov2` | 21 |
| `ef_io vdda_hvc_clamped_pad` | 27 | | `fd_io top_xres4v2` | 19 |
| `ef_io vddio_hvc_clamped_pad` | 27 | | `fd_io top_pwrdetv2` | 18 |
| `ef_io vssa_hvc_clamped_pad` | 27 | | `fd_io top_hvclamp` | 11 |
| `ef_io vssio_hvc_clamped_pad` | 27 | | `ef_io analog_stubs` (no corner) | 1 |
| `fd_io top_ground_hvc_wpad` | 27 | | `fd_io top_hvclampv2` | 27 |
| `fd_io top_power_hvc_wpad` | 27 | | `slices_stubs` (no prefix, no corner) | 1 |
| `fd_io top_power_lvc_wpad` | 27 | | `fd_io top_lvc_b2b` | 26 |

The `sky130_fd_io` library also ships `lef/` (incl. `sky130_fd_io.lef`,
32 library cells created from it), `spice/`, `cdl/`, `gds/` and `verilog/`.

**The `top_gpiov2` corner set (21 files)** — naming is
`<core-proc>_<io-proc>_<temp>_<vccd>_<vddio>`:

| File (suffix) | vddio | In decision-0002 window (2.97–3.63 V)? |
|---|---|---|
| `tt_tt_025C_1v80_3v30` | 3.30 V | **yes (typical)** |
| `ss_ss_100C_1v60_3v00` | 3.00 V | **yes (slow)** |
| `ff_ff_100C_1v95_5v50` | 5.50 V | no (5 V-class) |
| `ff_ff_n40C_1v95_5v50` | 5.50 V | no (5 V-class) |
| `ff_ff_n40C_1v95_5v50_nointpwr` | 5.50 V | no (5 V-class) |
| `ss_ff_100C_1v40_5v50` | 5.50 V | no (5 V-class) |
| `ss_ff_100C_1v60_5v50` | 5.50 V | no (5 V-class) |
| `ss_ff_n40C_1v35_5v50` | 5.50 V | no (5 V-class) |
| `ss_ff_n40C_1v60_5v50` | 5.50 V | no (5 V-class) |
| `ff_ss_100C_1v65_1v65` | 1.65 V | no (1.8 V-class) |
| `ff_ss_100C_1v95_1v65` | 1.65 V | no (1.8 V-class) |
| `ff_ss_100C_1v95_1v95` | 1.95 V | no (1.8 V-class) |
| `ff_ss_n40C_1v65_1v65` | 1.65 V | no (1.8 V-class) |
| `ff_ss_n40C_1v95_1v65` | 1.65 V | no (1.8 V-class) |
| `ff_ss_n40C_1v95_1v95` | 1.95 V | no (1.8 V-class) |
| `ss_ss_100C_1v40_1v65` | 1.65 V | no (1.8 V-class) |
| `ss_ss_100C_1v60_1v65` | 1.65 V | no (1.8 V-class) |
| `ss_ss_n40C_1v35_1v65` | 1.65 V | no (1.8 V-class) |
| `ss_ss_n40C_1v40_1v65` | 1.65 V | no (1.8 V-class) |
| `ss_ss_n40C_1v60_1v65` | 1.65 V | no (1.8 V-class) |
| `ss_ss_n40C_1v60_1v65_nointpwr` | 1.65 V | no (1.8 V-class) |

vddio distribution: 1.65 V ×10, 1.95 V ×2, 3.00 V ×1, 3.30 V ×1, 5.50 V ×7
(the two `_nointpwr` variants included).

## Corner coverage vs the ratified decisions (AC 3)

Decision 0002 ratifies a 3.3 V-class I/O supply; decision 0004 takes it
±10 % → **2.97–3.63 V**, with temperatures sampled at −40/27/125 °C. Against
that window the shipped pad liberty set gives:

- **Exactly two** `top_gpiov2` corners in-window:
  `tt_tt_025C_1v80_3v30` (typical) and `ss_ss_100C_1v60_3v00` (slow).
- **No `ff`, `fs` or `sf` pad liberty anywhere in the window** — every fast
  corner shipped is 5.5 V-class (`5v50`) or ≤1.95 V (`1v95`/`1v65`).
- Neither in-window corner lands on a decision-0004 temperature sample
  (25 °C vs 27 °C; 100 °C vs 125 °C) — near but not exact samples.

**Consequence (stated explicitly, per the AC):** liberty yields a
**slow/max** pad delay at the ratified supply but **no fast/min
counterpart**. The min/max pad-delay spread that row 12 depends on cannot be
closed from liberty alone; rows 11/12/14/19 still need the ngspice fast
edge. Pairing an out-of-window pad liberty with an in-window core corner
would be a substitution, not a corner (see the labelled comparison below).

## Arc results per direction per corner (AC 2)

All sessions: `padwrap.v` (one flop → output pad, input pad → one flop),
pads read from `sky130_fd_io.lef` + liberty, core from
`sky130_fd_sc_hd`, ideal 20 ns clock, delays in ns. Full path tables in the
committed logs.

| Log | Core corner | Pad liberty | Load | `OUT → PAD` rise/fall | `PAD → IN` rise/fall | Arcs reported? |
|---|---|---|---|---|---|---|
| `opensta-tt-5pf.log` | `tt_025C_1v80` | `tt_tt_025C_1v80_3v30` | 5.0 pF | 4.0995 / 4.1883 | 1.1423 / 1.2983 | **yes, both directions** |
| `opensta-tt-10pf.log` | `tt_025C_1v80` | `tt_tt_025C_1v80_3v30` | 10.0 pF | 4.5840 / 4.8057 | 1.1423 / 1.2983 | **yes, both directions** |
| `opensta-tt-20pf.log` | `tt_025C_1v80` | `tt_tt_025C_1v80_3v30` | 20.0 pF | 5.4200 / 5.6857 | 1.1423 / 1.2983 | **yes, both directions** |
| `opensta-ss-10pf.log` | `ss_100C_1v60` | `ss_ss_100C_1v60_3v00` | 10.0 pF | 7.1329 / 7.2719 | 1.7975 / 2.0770 | **yes, both directions** |
| `opensta-ff-oow-10pf.log` | `ff_n40C_1v95` | `ff_ff_n40C_1v95_5v50` | 10.0 pF | 2.8312 / 2.7229 | 0.6421 / 0.7716 | yes — **labelled out-of-window comparison** |

The `ff` row is **not a decision-0002 corner**: it pairs the decision-0004
core corner `ff_n40C_1v95` with the 5.5 V-class pad liberty
`ff_ff_n40C_1v95_5v50`, an out-of-window substitution committed only to show
what a fast edge looks like (roughly 2×–3× faster than the in-window corners
here). It must not be read as an in-window min bound.

Load sensitivity (the AC's edge case): `OUT → PAD` rises monotonically with
load — 4.10/4.19 ns at 5 pF → 4.58/4.81 ns at 10 pF → 5.42/5.69 ns at 20 pF
(rise/fall, tt) — while `PAD → IN` is unchanged. The output-side numbers are
a pad-plus-load system, not a pad property. Note also that the liberty's own
output-slew tables return very large slews at board-scale loads (e.g.
50.7 ns at 5 pF, 87.7 ns at 10 pF, rise) — those slew figures are the
liberty's table behaviour at an arbitrary load, and any future row-11/14 use
must pick its load deliberately with the sibling I/O ring.

## Negative controls

1. **No pad liberty (pad LEF read)** — `opensta-nolib.log`: OpenROAD warns
   `[WARNING ORD-2011] LEF master sky130_fd_io__top_gpiov2 has no liberty
   cell.` (the pad is black-boxed), `report_checks` finds **`No paths
   found.`**, and `report_worst_slack` returns **INF for both max and min** —
   no arc through the pad in either direction. A "pass" that still passed
   here would have been proving nothing; this control fails as it must.
2. **No pad liberty and no pad LEF** — `opensta-nolib-nolef.log`: the
   literal wording the issue's test plan names appears —
   `[WARNING STA-0198] module sky130_fd_io__top_gpiov2 not found. Creating
   black box for u_opad.` — and the session then hard-errors on the second
   instance (`[ERROR ORD-2013] instance u_ipad LEF master
   sky130_fd_io__top_gpiov2 not found`, exit 1). Both dispositions of a
   pad-less session (silent INF, or hard error) are recorded so neither is
   ever mistaken for a timing result.
3. **Unpairable corner** (`ff_n40C_1v95` has no in-window pad liberty):
   the mechanism that was supposed to reject it — a per-corner `macros.lib`
   map keyed on the core corner with a missing key erroring out — **does not
   exist in the pinned `klt` 0.8.0** (see Tool gap), so there is no rejection
   to observe at the pin; the request in `sta-request.json` deliberately
   includes `ff_n40C_1v95` in `pdk.corners` with no `lib` entry for it. What
   actually happens is worse than a substitution: the tool never reaches
   timing at all (it fails at link, and it would silently ignore the whole
   `macros` field if link had passed). The labelled `ff` comparison above is
   the honest stand-in for "what a fast edge would look like".

## Tool gap: `klt sta` 0.8.0

**The pinned `klt sta` cannot drive this experiment, and the gap is worse
than a clean refusal — the unsupported field is silently ignored.** Committed
evidence: `sta-request.json` (the request as written, using the documented
`macros: [{name, lef, lib: {<core-corner>: <pad-liberty>}}]` shape) and
`klt-0.8.0-attempt/` (the generated engine script, the engine stderr, and
the invocation record).

Observed on the pinned wheel (checked in the 0.8.0 wheel contents
themselves, not inferred from the failure alone):

1. `klt sta` 0.8.0 reads **exactly one liberty** per session
   (`pdk.cell_library` at `pdk.corner`/`pdk.corners`) — there is no field to
   load a second (macro/IP) liberty, and no field to read an additional LEF.
   The `macros` field this request carries is **not rejected** — request
   validation checks only the required fields, so unknown top-level fields
   pass through silently and would have black-boxed the pad with no
   diagnostic.
2. Because the I/O LEF cannot be loaded, `link_design` hard-fails on the pad
   instances: `[ERROR ORD-2013] instance u_ipad LEF master
   sky130_fd_io__top_gpiov2 not found` (exit 1, no response document —
   which is why there is no `sta.json` in this record: the committed engine
   artifacts in `klt-0.8.0-attempt/` are the tool output there is).
3. The per-corner `lib` map's documented property — "a `lib` map with no
   entry for the corner being analysed is a request error, not a silent
   fallback" — cannot hold at this pin, because the map itself is ignored;
   the missing-entry rejection (and any per-corner pairing) arrives only
   with a version that implements the field. (`macros[].lib` does exist in
   `klt` 0.9.2-dev builds; the repo pin is 0.8.0 and `scripts/klt.sh` is the
   one pin.)

**A `2AMLogic/klayout-tools` issue has been filed for this gap**
([klayout-tools#5748](https://github.com/2AMLogic/klayout-tools/issues/5748),
generic form: "`klt sta` cannot load a second liberty/LEF for a macro/IP
cell, and unknown top-level request fields are silently ignored instead of
rejected"), so consumers of this record know the pin cannot run it and the
tool can close the gap. Until the pin moves, `sim/pad-sta/run-opensta.sh` (the
committed OpenROAD session driver, exactly the fallback the issue named) is
this record's reproduction path.

## Why not the other paths

- *Hand-written OpenROAD Tcl* — is what `run-opensta.sh` now is, by
  necessity; it produces committed per-session logs, though not `klt`'s
  response schema/provenance envelope.
- *Standalone OpenSTA* — not installed; host rules forbid installing it.
  "Loaded in OpenSTA" here means OpenROAD's embedded OpenSTA.
- *`klt place-and-route` then STA* — N placements for N corners is a sweep
  of N designs, not a characterization of one; this experiment needs no
  geometry at all.

## Provisioning note (AC 4)

`sky130_fd_io` must be named in `scripts/setup-env.sh`'s `ciel enable`:
verified on a **fresh provision** into a scratch `--pdk-root` with exactly
`-l sky130_fd_pr -l sky130_fd_sc_hd`, `libs.ref/` contains **only** those two
libraries — `sky130_fd_io` ships in the PDK but is not linked unless named.
(A host whose tree already carries `sky130_fd_io` was provisioned differently
and proves nothing about a clean provision.) `scripts/setup-env.sh` now
enables all three libraries and fails loudly if the `top_gpiov2` tt liberty
or the I/O LEF is missing; `docs/environment.md` records the same.

## Reproducing

From a clean checkout with the pinned environment (`scripts/setup-env.sh`,
then `openroad` on `$PATH`):

```sh
PDK_ROOT=~/.ciel sim/pad-sta/run-opensta.sh
```

regenerates every `opensta-*.log` next to this file. Logs embed the absolute
PDK/netlist paths of the machine that produced them; the arc numbers and the
warning/no-path lines, not byte-identical logs, are what must reproduce.
Regenerate the inventory (adjust the two path variables at the top) and diff
against `inventory.tsv`:

```sh
python3 - <<'PY'
import hashlib, os
d = os.path.expanduser("~/.ciel/sky130A/libs.ref/sky130_fd_io/lib")
for f in sorted(os.listdir(d)):
    if f.endswith(".lib"):
        print(f, hashlib.sha256(open(os.path.join(d, f), "rb").read()).hexdigest())
PY
```
