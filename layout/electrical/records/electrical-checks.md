# Electrical-limit violation classification (issue #173)

Tool-written record rendered by `layout/electrical/classify.py` from the `klt sta` DEF+SPEF response (`records/sta-response.json`) and each corner's engine stdout (`records/opensta-<corner>.log`). OpenROAD 26Q3-1510-g6cb3f2b704, klt 0.9.2. Limits are the liberty's own, as reported by the tool; nothing here is hand-typed.

Parasitics model: committed SPEF. The place-and-route sweep's counts (global-routing-estimated parasitics) are quoted side by side and are a different measurement of the same routed geometry. The archived P&R pin rows are unavailable for reconciliation. [Evidence gap #179](https://github.com/2AMLogic/sky130-hyperram-ctrl/issues/179).

| Corner | P&R max-tran / max-cap | SPEF max-tran rows (nets) | SPEF max-cap rows (nets) | classes |
|---|---|---|---|---|
| `ff_100C_1v65` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ff_100C_1v95` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ff_n40C_1v56` | 0 / 0 | 109 (3) | 2 (2) | control-fanout:30, reset-distribution:79 |
| `ff_n40C_1v65` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ff_n40C_1v76` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ff_n40C_1v95` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_100C_1v40` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_100C_1v60` | 418 / 12 | 502 (16) | 16 (16) | control-fanout:92, enable-fanout:18, reset-distribution:374, weak-driver:18 |
| `ss_n40C_1v28` | 445 / 13 | 532 (20) | 18 (18) | control-fanout:124, reset-distribution:374, weak-driver:34 |
| `ss_n40C_1v35` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v40` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v44` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v60` | 619 / 22 | 652 (25) | 25 (25) | control-fanout:176, enable-fanout:69, reset-distribution:374, weak-driver:33 |
| `ss_n40C_1v76` | 410 / 10 | 460 (13) | 13 (13) | control-fanout:75, reset-distribution:374, weak-driver:11 |
| `tt_025C_1v80` | 0 / 0 | 29 (1) | 1 (1) | reset-distribution:29 |
| `tt_100C_1v80` | 0 / 0 | 0 (0) | 0 (0) | - |

## Violating nets (union over corners)

| Net | Class | Driver | Origin | Sinks | Worst slew (corner, value/limit ns) | Worst cap (corner, value/limit pF) |
|---|---|---|---|---|---|---|
| `_122_` | control-fanout | nor3b_4 `_168_` | netlist | 17 | `ss_n40C_1v28` 5.301/4.985 | `ss_n40C_1v60` 0.069/0.062 |
| `_148_` | control-fanout | and3_1 `_245_` | netlist | 29 | `ss_n40C_1v28` 6.280/4.971 | `ss_n40C_1v60` 0.136/0.078 |
| `net10` | reset-distribution | buf_2 `fanout10` | pnr-inserted | 50 | `ss_n40C_1v28` 6.852/5.000 | `ss_n40C_1v60` 0.255/0.149 |
| `net11` | reset-distribution | buf_2 `fanout11` | pnr-inserted | 50 | `ss_n40C_1v28` 7.144/5.000 | `ss_n40C_1v60` 0.264/0.149 |
| `net4` | reset-distribution | buf_2 `fanout4` | pnr-inserted | 50 | `ss_n40C_1v28` 7.026/5.000 | `ss_n40C_1v60` 0.258/0.149 |
| `net5` | reset-distribution | buf_2 `fanout5` | pnr-inserted | 50 | `ss_n40C_1v28` 6.961/5.000 | `ss_n40C_1v60` 0.257/0.149 |
| `net6` | reset-distribution | clkdlybuf4s50_1 `fanout6` | pnr-inserted | 28 | `ss_n40C_1v28` 8.118/5.000 | `ss_n40C_1v60` 0.150/0.074 |
| `net8` | reset-distribution | buf_2 `fanout8` | pnr-inserted | 38 | `ss_n40C_1v28` 5.611/5.000 | `ss_n40C_1v60` 0.207/0.149 |
| `net9` | reset-distribution | buf_2 `fanout9` | pnr-inserted | 50 | `ss_n40C_1v28` 6.956/5.000 | `ss_n40C_1v60` 0.256/0.149 |
| `rd_flush` | weak-driver | o21ai_0 `u_fsm/_1623_` | netlist | 6 | `ss_n40C_1v28` 6.353/4.996 | `ss_n40C_1v60` 0.030/0.022 |
| `u_cap/_005_` | enable-fanout | and3_1 `u_cap/_630_` | netlist | 16 | `ss_n40C_1v60` 1.845/1.500 | `ss_n40C_1v60` 0.096/0.078 |
| `u_cap/_006_` | enable-fanout | and3_1 `u_cap/_627_` | netlist | 16 | `ss_n40C_1v60` 1.788/1.500 | `ss_n40C_1v60` 0.093/0.078 |
| `u_cap/_007_` | enable-fanout | and3_1 `u_cap/_629_` | netlist | 16 | `ss_n40C_1v60` 1.770/1.500 | `ss_n40C_1v60` 0.093/0.078 |
| `u_cap/_008_` | enable-fanout | and3_1 `u_cap/_623_` | netlist | 17 | `ss_n40C_1v60` 1.907/1.500 | `ss_n40C_1v60` 0.100/0.078 |
| `u_cap/_255_` | control-fanout | nand2_1 `u_cap/_512_` | netlist | 22 | `ss_n40C_1v60` 1.668/1.498 | `ss_n40C_1v60` 0.090/0.080 |
| `u_fsm/_0635_` | control-fanout | nor2_1 `u_fsm/_1082_` | netlist | 17 | `ss_n40C_1v28` 7.571/4.942 | `ss_n40C_1v60` 0.069/0.038 |
| `u_fsm/_0672_` | control-fanout | nor2_1 `u_fsm/_1133_` | netlist | 16 | `ss_n40C_1v28` 5.476/4.942 | `ss_n40C_1v60` 0.050/0.038 |
| `u_fsm/_0675_` | weak-driver | nor3_1 `u_fsm/_1138_` | netlist | 6 | `ss_n40C_1v28` 5.163/4.959 | `ss_n40C_1v60` 0.023/0.021 |
| `u_fsm/_0697_` | control-fanout | or3_1 `u_fsm/_1161_` | netlist | 28 | `ss_n40C_1v60` 1.759/1.500 | `ss_n40C_1v60` 0.096/0.081 |
| `u_fsm/_0720_` | weak-driver | nor3_1 `u_fsm/_1190_` | netlist | 7 | `ss_n40C_1v28` 5.054/4.959 | `ss_n40C_1v60` 0.023/0.021 |
| `u_fsm/_0765_` | control-fanout | nand2b_1 `u_fsm/_1243_` | netlist | 26 | `ss_n40C_1v28` 5.749/4.974 | `ss_n40C_1v60` 0.104/0.072 |
| `u_fsm/_0790_` | weak-driver | nor4_1 `u_fsm/_1268_` | netlist | 4 | `ss_n40C_1v28` 4.944/4.889 | - |
| `u_fsm/_0799_` | weak-driver | o31ai_1 `u_fsm/_1277_` | netlist | 6 | `ss_n40C_1v28` 7.809/4.929 | `ss_n40C_1v28` 0.026/0.015 |
| `u_fsm/_0832_` | control-fanout | nor2_1 `u_fsm/_1316_` | netlist | 13 | `ss_n40C_1v60` 1.786/1.500 | `ss_n40C_1v60` 0.046/0.038 |
| `u_fsm/_0953_` | weak-driver | a2111oi_1 `u_fsm/_1460_` | netlist | 3 | `ss_n40C_1v28` 8.295/4.800 | `ss_n40C_1v28` 0.016/0.008 |
| `u_fsm/net7` | reset-distribution | buf_2 `u_fsm/fanout7` | pnr-inserted | 50 | `ss_n40C_1v28` 7.338/5.000 | `ss_n40C_1v60` 0.270/0.149 |
