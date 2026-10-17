# 0005 Protocol coverage

Status: proposed (unratified). Judged functionally; STA at 25 and 50 MHz.

## Decision
v1 covers: 48-bit CA over three CK cycles; variable latency with RWDS-
signalled extra latency (and a configured fixed-latency mode as the fallback);
linear bursts; byte write masking via RWDS; register-space access; reset and
power-up sequencing with a configurable interval; enforcement of the maximum
CS-low time by a down-counter that ends the burst before the limit and
re-issues the remainder (the limit value comes from device-model-params.md).
Wrapped bursts are a stretch.

## Consequences
Values for each limit are taken from the cited interface definition once
transcribed. Rejected: leaving CS-low enforcement to the host, since a host
stall would then violate the limit.
