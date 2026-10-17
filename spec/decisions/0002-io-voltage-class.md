# 0002 I/O voltage class

Status: proposed (unratified). Judged at: I/O supply ±10 %.

## Context
Options are 3.0/3.3 V-class I/O or 1.8 V-class devices.

## Options
1. 3.3 V-class pads from the sky130 I/O library family (`sky130_fd_io`),
   core at 1.8 V with in-pad level shifting. 2. 1.8 V-class devices.

## Decision
Option 1. The controller core stays on 1.8 V `sky130_fd_sc_hd` cells; the
boundary is the pad's level shifter. The pad cell names are *not* fixed here:
`2AMLogic/sky130-io-ring` draws its own cells and has not ratified a cell
list (its `spec/` was empty at `9cf5d41`). The supplies implied are a 3.3 V
I/O supply (±10 %) and the 1.8 V core supply, plus their grounds.

## Consequences
Pad delay and its spread dominate the read-capture budget (decision 0003).
1.8 V-class devices stay a stretch row. This record must be revisited if the
sibling ratifies a different cell set.
