# 0004 PVT corner set

Status: proposed (unratified).

## Decision
Core STA: all `sky130_fd_sc_hd` liberty corners in the pinned PDK. ngspice:
tt/ff/ss/fs/sf, temperature −40 … +125 °C sampled at −40/27/125 °C. Supplies:
core 1.8 V ±10 %, I/O supply ±10 % around its nominal (decision 0002).

## Context
The −40 … +125 °C range is the one proposed in issue #2; this record
makes it a decision rather than an assumption. `2AMLogic/sky130-pll`
ratified the same process and temperature sets at `76a4b68` (its rows 19, 20).

## Consequences
Each result records its corner in its name; recorded results are append-only.
