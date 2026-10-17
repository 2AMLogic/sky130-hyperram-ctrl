# Pad requirements (DRAFT)

Compared with `2AMLogic/sky130-io-ring` at commit
`9cf5d41503b5566935da2bc0b74ccb50a00fcfab` (HEAD on 2026-10-17; its `spec/`
is still the empty placeholder and its README holds a DRAFT table only). The
sky130 foundry I/O library (`sky130_fd_io`) was not re-read for this draft;
rows marked "unchecked" need that read before ratification.

| Requirement | Value needed | io-ring at 9cf5d41 | Fit / gap |
|---|---|---|---|
| I/O supply | 3.3 V-class, ±10 % | README draft: 3.3 V ±10 % | **fit** (draft only, not ratified) |
| Core-side level | 1.8 V core, shifted in pad | README draft: level-shifted in pad | **fit** (draft) |
| Bidirectional DQ[7:0], RWDS | output enable, input enable per pin | draft GPIO has OE and IE | **fit** (draft) |
| CK output | output-only pad | "output + input only" fallback exists | **fit** |
| CS#, RESET# | output-only pads | as above | **fit** |
| Drive strength | enough for a short board trace at 50 MHz; value to be fixed by SPICE with a stated load (placeholder: 10 pF, to be replaced) | selectable drive is a *stretch* row | **gap**: only one fixed strength guaranteed; no figure given |
| Output delay and spread | pad-to-pin min/max over all ngspice corners, rise and fall, stated per cell | none | **gap**: no data |
| Input delay and spread | pin-to-core min/max, same corners; must be tracked on RWDS and DQ separately | none | **gap**: no data |
| Output-enable timing | OE-to-pin-valid and OE-to-Hi-Z min/max, needed to turnaround DQ without contention | none | **gap**: no data |
| Rise/fall skew | RWDS vs DQ input path skew within 0.2 ns (proposal) | none | **gap** |
| Pull-up/down | not required in v1 | draft has them | **fit** |
| Pin mapping | pad cells for DQ/RWDS/CK/CS#/RESET# physically adjacent so delays match | ring-level, not specified | **gap** |

Gaps are filed on `2AMLogic/sky130-io-ring` (see the issue link
below). Pad delay figures must be matched between
input and output sides: the controller assumes DQ and RWDS pads are the same
cell.

Gap issue filed: https://github.com/2AMLogic/sky130-io-ring/issues/7
