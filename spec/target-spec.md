# Target specification (DRAFT)

Status: **DRAFT, unratified.** "Proof" names the testbench or analysis that
will establish the row; none of them exists yet, so no row is met.

## Corner sets (see decision 0004)

- **Core STA**: every `sky130_fd_sc_hd` liberty corner shipped by the pinned
  PDK (tt/ff/ss at the shipped voltage and temperature points).
- **ngspice** (pads, delay element): process tt/ff/ss/fs/sf, temperature
  −40 … +125 °C (proposed in #2; recorded here as a decision, not an
  assumption), sampled −40/27/125 °C.
- **Supply**: core 1.8 V ±10 % (1.62–1.98 V); I/O supply per decision 0002,
  ±10 % (the I/O ring draft figure; its tolerance is not yet ratified there).

Abbreviations: **STA** = static timing, **SPICE** = ngspice campaign,
**CT** = cocotb testbench against the behavioural model, **REV** = review of a
written analysis.

| # | Parameter | Target | Fallback | Stretch | Proof | Corners |
|---|---|---|---|---|---|---|
| 1 | Bus clock | 50 MHz (100 MB/s) | 25 MHz | 100 MHz | STA + SPICE pad timing | all core + all ngspice |
| 1a | Clock output | single-ended CK, CK# not driven (decision 0001) | same | differential CK/CK# | REV + pad table | n/a |
| 2 | I/O voltage class | 3.3 V-class I/O (decision 0002) | — | 1.8 V-class devices | REV of pad cells vs [pad-interface.md](pad-interface.md) | I/O supply ±10 % |
| 3 | Command/address | 48-bit CA over 3 CK cycles (6 bytes, DDR) | same | same | CT | n/a (functional) |
| 4 | Latency | variable latency with RWDS-signalled extra latency (initial latency ×2 when RWDS high during CA); fixed latency selectable by configuration | fixed latency only | same | CT | functional + STA at 25/50 MHz |
| 5 | Bursts | linear, any length up to the CS-low limit | single word | wrapped bursts | CT | functional |
| 6 | Write mask | RWDS as per-byte mask on writes | whole-word writes only | same | CT | functional |
| 7 | Register space | read/write of the device register space via the CA address-space bit | read only | same | CT | functional |
| 8 | Reset / power-up | controller holds RESET# and CS# deasserted for a configured power-up interval before the first access; interval is a register, not hardcoded | fixed interval | same | CT | functional |
| 9 | Max CS-low time | controller splits or terminates transactions so CS# never stays low longer than the model's `tCSM`; enforced by a down-counter that ends the burst and re-issues the remainder | same | same | CT with model that flags violation | functional + clock period corners |
| 10 | RWDS extra latency | controller samples RWDS during CA and doubles latency when asserted; sampling point is tied to CK, not the delayed strobe | same | same | CT | functional |
| 11 | Read capture | fixed, PVT-margined strobe delay; decision 0003 | 25 MHz with wider eye | calibrated delay line | SPICE + STA (see below) | all ngspice |
| 12 | Read-capture margin | ≥ 20 % of the half-period (2 ns at 50 MHz) setup and hold at the capturing flop after worst-corner delay spread; the 20 % figure is a proposal for ratification | ≥ 20 % at 25 MHz (4 ns) | n/a | SPICE pad+delay sweep, then STA | all ngspice, all liberty |
| 13 | Calibration failure | not applicable in v1 (no calibration). If a later calibrated mode is added: fall back to the fixed tap and raise a status bit | same | status bit + interrupt | CT | functional |
| 14 | Write path | DDR outputs from the core clock; CK output is data-launch clock delayed by a quarter period (90°) so CK edges centre in the data eye, as the device interface requires for writes | CK = data launch clock, shift by one inverter chain | n/a | SPICE pad output timing + STA | all |
| 15 | Host interface | Wishbone-class 32-bit, pipelined, with ack-based back-pressure | same | AXI-class | CT | functional |
| 16 | Host bursts | burst via incrementing address cycles; back-pressure by stall of ack, controller never drops data | single beat | AXI bursts | CT | functional |
| 17 | Area | ≤ 0.10 mm² core (budget, proposal) | none | none | OpenROAD report | typ |
| 18 | Power | budget set at first synthesis, recorded as a decision then; no number is claimed now | — | — | OpenROAD / ngspice | typ + ff hot |
| 19 | Timing at the pins | setup/hold met at pins incl. pads | — | — | STA where it sees pads; SPICE otherwise | all |
| 20 | Signoff | DRC + LVS clean | — | — | `klt` | n/a |

## Open questions (answers or experiments)

**(a) Does OpenROAD STA see through the pad cells?** *Unresolved, evidence
needed.* Experiment: load the I/O library's shipped liberty views (if any
exist for the pinned PDK) with the pad netlist in OpenSTA, and check that a
path from core flop to pad and from pad to core flop reports arcs. If arcs
are absent or only at a corner subset, pad delay and spread come from the
ngspice characterization in row 11/14, and the assumption (pad delay taken
from SPICE as a fixed min/max budget applied to STA I/O constraints) must be
stated in each timing result. Filing a tool gap on `2AMLogic/klayout-tools`
is conditional on the experiment showing `klt` cannot drive it; none is
filed yet because nothing has been tried.

**(b) Delay-chain monotonicity across PVT.** *Unresolved, evidence needed.*
Experiment: ngspice transient of a standard-cell chain, per tap, across all
corners; pass if tap delay is monotonic in tap count and the min/max ratio
at the chosen tap leaves the row 12 margin. Decision 0003 holds until this is
shown; if it fails the record is superseded, not the margin relaxed.

**(c) Device timing parameters**: see [device-model-params.md](device-model-params.md).
