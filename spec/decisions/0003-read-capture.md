# 0003 Read capture

Status: proposed (unratified). Judged at: all ngspice corners plus the
supply range of decision 0004.

## Context
RWDS arrives edge-aligned with read data. It must be delayed into the data
eye through the pads, across PVT, with no DLL in v1. At 50 MHz one bit time
(half period) is 10 ns.

## Options
1. Fixed delay from a standard-cell chain, tap chosen at design time.
2. Fixed delay from a custom cell.
3. Calibrated delay line.

## Decision
Option 1. A chain of `sky130_fd_sc_hd` delay cells with a small number of
selectable taps (selected by a configuration register, static during
operation). Option 3 is a stretch for 100 MHz and does not influence v1.
Option 2 is taken only if the monotonicity experiment (target-spec open
question b) fails; that would supersede this record.

Margin: setup and hold at the capturing flop each at least 20 % of the half
period (1 ns at 50 MHz) at the worst corner after adding the full pad delay
spread on both RWDS and DQ paths. The 20 % is a proposal; ratification may
change it, agents may not.

Calibration failure: v1 has no calibration, so none can fail. The tap
register powers up at a mid tap, and an out-of-margin result found in
characterization is a spec failure, not a runtime condition.

## Consequences
Everything rests on ngspice pad+chain characterization; the result must name
each corner and state the assumption if STA cannot see the pads (open
question a). If the worst-corner spread exceeds the eye at 50 MHz, the
response is the 25 MHz fallback, not a calibrated line.
