# 0001 Bus clock and clock output

Status: proposed (unratified). Judged at: all corner sets of decision 0004.

## Context
The target is 50 MHz; 25 MHz is the fallback and 100 MHz a stretch. The
interface allows a single-ended or a differential clock.

## Options
1. Single-ended CK only. 2. Differential CK/CK#.

## Decision
Single-ended CK at 50 MHz. CK# is not driven. 100 MHz needs (a calibrated
delay line, a DLL, differential clock) must not drive any v1 architecture
choice.

## Consequences
One fewer output pad and no matched-pair skew requirement. Differential
output remains a stretch row and would need its own record.
