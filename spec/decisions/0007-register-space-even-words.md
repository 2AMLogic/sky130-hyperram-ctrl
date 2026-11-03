# 0007 Host-reachable register space is the even words only

Status: operator-ruled (rjwalters, `fleet:decide` round 20261031-r5, question
r5-q59, 2026-11-03), option (a). Issue #49, split from #48.

## Decision
Row 7 of [target-spec.md](../target-spec.md) ("read/write of the device
register space") is narrowed to the **even register words**. The host port
forms the CA word address as `w_addr = {1'b0, t_adr, 1'b0}`
(`rtl/hyperram_ctrl/hr_cmd_fsm.v:107`, verified at `11f68ed`, 2026-11-02), i.e.
`2 * wb_adr[29:0]`, so CA address bit 0 is always 0.

| Register word | CA word address | Host `wb_adr` | Reachable |
|---|---|---|---|
| ID0 | `0x000` | `0x000` | yes |
| CR0 | `0x800` | `0x400` | yes |
| ID1 | `0x001` | none | **no** |
| CR1 | `0x801` | none | **no** |

## Consequences
- No RTL change, so the item-1 attestation and synthesis records stay valid.
- The host cannot read or write ID1 or CR1. Anything that needs them is out
  of scope for v1.
- Rejected: odd-word addressing in RTL (option b). It satisfies row 7 as
  originally written but invalidates the item-1 attestation and synthesis
  records, and adds scope ahead of 50 MHz pin closure.
- This narrows a ratified row; it does so on an explicit operator ruling, not
  an agent decision.
