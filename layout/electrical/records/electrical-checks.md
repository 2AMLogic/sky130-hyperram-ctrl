# Electrical-limit violation classification (issue #173)

Tool-written record rendered by `layout/electrical/classify.py` from the `klt sta` DEF+SPEF response (`records/sta-response.json`) and each corner's engine stdout (`records/opensta-<corner>.log`). OpenROAD 26Q3-1510-g6cb3f2b704, klt 0.8.0. Limits are the liberty's own, as reported by the tool; nothing here is hand-typed.

Parasitics model: committed SPEF. The place-and-route sweep's counts (global-routing-estimated parasitics) are quoted side by side and are a different measurement of the same routed geometry. The archived P&R pin rows are unavailable for reconciliation. [Evidence gap #179](https://github.com/2AMLogic/sky130-hyperram-ctrl/issues/179).

| Corner | P&R max-tran / max-cap | SPEF max-tran rows (nets) | SPEF max-cap rows (nets) | classes |
|---|---|---|---|---|
| `ff_100C_1v65` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ff_100C_1v95` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ff_n40C_1v56` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ff_n40C_1v65` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ff_n40C_1v76` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ff_n40C_1v95` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_100C_1v40` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_100C_1v60` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v28` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v35` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v40` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v44` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v60` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v76` | 0 / 0 | 0 (0) | 0 (0) | - |
| `tt_025C_1v80` | 0 / 0 | 0 (0) | 0 (0) | - |
| `tt_100C_1v80` | 0 / 0 | 0 (0) | 0 (0) | - |

## Violating nets (union over corners)

| Net | Class | Driver | Origin | Sinks | Worst slew (corner, value/limit ns) | Worst cap (corner, value/limit pF) |
|---|---|---|---|---|---|---|
