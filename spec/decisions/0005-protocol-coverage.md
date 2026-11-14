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
Values for each limit are taken from the cited interface definition. As of
2026-11-14 they are transcribed: see [../device-model-params.md](../device-model-params.md),
which now carries the full Rev. \*H table with a recorded locator. The CS-low
limit this record defers to is **tCSM = 1.00 µs** (the *Industrial Plus* bound;
not published for the −40…+125 °C *Extended* range these corners use, so the
tighter published value is taken deliberately), i.e. 50 CK periods at 50 MHz and
25 at 25 MHz. The down-counter is sized from that.

Rejected: leaving CS-low enforcement to the host, since a host stall would then
violate the limit.

One consequence of the transcription worth recording here, because it changes
what "initial latency" means for this decision: the interface definition
**publishes no single initial-latency count**. It defines an encodable range of
3–16 clocks in a configuration register and leaves the implemented options and
the reset default device-dependent. So the variable/fixed latency coverage this
record decides must be *configurable over that range*, not built against a
constant.
