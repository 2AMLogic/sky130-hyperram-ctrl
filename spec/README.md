# spec

**Status: DRAFT — not ratified.** Ratification is a human/Champion act after
review of the PR that lands these files (issue #2). Agents do not relax a row
to make later results pass; a change to a row is a new decision record.

| File | Content |
|---|---|
| [target-spec.md](target-spec.md) | Every parameter: target / fallback / stretch, verification, corners |
| [pad-interface.md](pad-interface.md) | What the pads must provide; comparison with `2AMLogic/sky130-io-ring` |
| [clock-interface.md](clock-interface.md) | What the clock must be; comparison with `2AMLogic/sky130-pll` |
| [device-model-params.md](device-model-params.md) | Behavioural device-model timing parameters and their sources |
| [decisions/](decisions/) | One record per choice |

Decision records: 0001 bus clock and clock output, 0002 I/O voltage class,
0003 read capture, 0004 PVT corner set, 0005 protocol coverage.

HyperBus and HyperRAM only name the interface. Nothing here claims
conformance to any device.
