# Electrical-limit violation classification (issue #173)

Tool-written record rendered by `layout/electrical/classify.py` from the `klt sta` DEF+SPEF response (`records/sta-response.json`) and each corner's engine stdout (`records/opensta-<corner>.log`). OpenROAD 26Q3-1510-g6cb3f2b704, klt 0.8.0. Limits are the liberty's own, as reported by the tool; nothing here is hand-typed.

Parasitics model: committed SPEF. The place-and-route sweep's counts (global-routing-estimated parasitics) are quoted side by side and are a different measurement of the same routed geometry.

| Corner | P&R max-tran / max-cap | SPEF max-tran rows (nets) | SPEF max-cap rows (nets) | classes |
|---|---|---|---|---|
| `ff_100C_1v65` | 0 / 0 | 34 (1) | 1 (1) | reset-distribution:34 |
| `ff_100C_1v95` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ff_n40C_1v56` | 34 / 1 | 136 (3) | 3 (3) | reset-distribution:136 |
| `ff_n40C_1v65` | 0 / 0 | 34 (1) | 1 (1) | reset-distribution:34 |
| `ff_n40C_1v76` | 0 / 0 | 34 (1) | 1 (1) | reset-distribution:34 |
| `ff_n40C_1v95` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_100C_1v40` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_100C_1v60` | 474 / 15 | 539 (18) | 18 (18) | control-fanout:129, enable-fanout:18, reset-distribution:380, weak-driver:12 |
| `ss_n40C_1v28` | 503 / 16 | 546 (20) | 19 (19) | control-fanout:147, reset-distribution:380, weak-driver:19 |
| `ss_n40C_1v35` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v40` | 0 / 0 | 0 (0) | 0 (0) | - |
| `ss_n40C_1v44` | 0 / 0 | 34 (1) | 1 (1) | reset-distribution:34 |
| `ss_n40C_1v60` | 609 / 21 | 636 (25) | 24 (24) | control-fanout:170, enable-fanout:69, reset-distribution:380, weak-driver:17 |
| `ss_n40C_1v76` | 442 / 13 | 513 (16) | 16 (16) | control-fanout:129, reset-distribution:380, weak-driver:4 |
| `tt_025C_1v80` | 34 / 1 | 34 (1) | 1 (1) | reset-distribution:34 |
| `tt_100C_1v80` | 0 / 0 | 34 (1) | 1 (1) | reset-distribution:34 |

## Violating nets (union over corners)

| Net | Class | Driver | Origin | Sinks | Worst slew (corner, value/limit ns) | Worst cap (corner, value/limit pF) |
|---|---|---|---|---|---|---|
| `_122_` | control-fanout | nor3b_4 `_168_` | netlist | 17 | `ss_n40C_1v28` 5.448/4.985 | `ss_n40C_1v60` 0.071/0.062 |
| `net10` | reset-distribution | buf_2 `fanout10` | pnr-inserted | 50 | `ss_n40C_1v28` 6.872/5.000 | `ss_n40C_1v60` 0.253/0.149 |
| `net11` | reset-distribution | buf_2 `fanout11` | pnr-inserted | 50 | `ss_n40C_1v28` 7.532/5.000 | `ss_n40C_1v60` 0.277/0.149 |
| `net5` | reset-distribution | buf_2 `fanout5` | pnr-inserted | 50 | `ss_n40C_1v28` 7.275/5.000 | `ss_n40C_1v60` 0.268/0.149 |
| `net6` | reset-distribution | buf_2 `fanout6` | pnr-inserted | 50 | `ss_n40C_1v28` 7.120/5.000 | `ss_n40C_1v60` 0.261/0.149 |
| `net7` | reset-distribution | clkdlybuf4s50_1 `fanout7` | pnr-inserted | 33 | `ss_n40C_1v28` 9.631/5.000 | `ss_n40C_1v60` 0.178/0.074 |
| `net8` | reset-distribution | buf_2 `fanout8` | pnr-inserted | 39 | `ss_n40C_1v28` 5.770/5.000 | `ss_n40C_1v60` 0.213/0.149 |
| `net9` | reset-distribution | buf_2 `fanout9` | pnr-inserted | 50 | `ss_n40C_1v28` 7.128/5.000 | `ss_n40C_1v60` 0.262/0.149 |
| `rd_flush` | weak-driver | o21ai_0 `u_fsm/_1703_` | pnr-inserted | 7 | `ss_n40C_1v28` 6.019/4.996 | `ss_n40C_1v60` 0.029/0.022 |
| `u_cap/_005_` | enable-fanout | and3_1 `u_cap/_630_` | pnr-inserted | 16 | `ss_n40C_1v60` 1.734/1.500 | `ss_n40C_1v60` 0.090/0.078 |
| `u_cap/_006_` | enable-fanout | and3_1 `u_cap/_627_` | pnr-inserted | 16 | `ss_n40C_1v60` 1.775/1.500 | `ss_n40C_1v60` 0.093/0.078 |
| `u_cap/_007_` | enable-fanout | and3_1 `u_cap/_629_` | pnr-inserted | 16 | `ss_n40C_1v60` 1.737/1.500 | `ss_n40C_1v60` 0.091/0.078 |
| `u_cap/_008_` | enable-fanout | and3_1 `u_cap/_623_` | pnr-inserted | 17 | `ss_n40C_1v60` 1.902/1.500 | `ss_n40C_1v60` 0.100/0.078 |
| `u_cap/_152_` | control-fanout | nor2b_1 `u_cap/_394_` | pnr-inserted | 17 | `ss_n40C_1v28` 7.077/5.000 | `ss_n40C_1v60` 0.059/0.036 |
| `u_cap/_156_` | control-fanout | nor2b_1 `u_cap/_398_` | pnr-inserted | 18 | `ss_n40C_1v28` 7.588/5.000 | `ss_n40C_1v60` 0.064/0.036 |
| `u_cap/_255_` | control-fanout | nand2_1 `u_cap/_512_` | pnr-inserted | 22 | `ss_n40C_1v60` 1.586/1.498 | `ss_n40C_1v60` 0.085/0.080 |
| `u_fsm/_0121_` | weak-driver | a2111oi_0 `u_fsm/_1538_` | pnr-inserted | 3 | `ss_n40C_1v28` 9.049/4.670 | `ss_n40C_1v60` 0.017/0.008 |
| `u_fsm/_0530_` | weak-driver | o21ai_0 `u_fsm/_2063_` | pnr-inserted | 2 | `ss_n40C_1v60` 1.468/1.463 | - |
| `u_fsm/_0552_` | control-fanout | o21ai_1 `u_fsm/_2088_` | pnr-inserted | 15 | `ss_n40C_1v28` 6.954/4.996 | `ss_n40C_1v60` 0.053/0.035 |
| `u_fsm/_0613_` | weak-driver | nor4_1 `u_fsm/_1064_` | pnr-inserted | 2 | `ss_n40C_1v28` 5.027/4.889 | - |
| `u_fsm/_0659_` | weak-driver | nor4_1 `u_fsm/_1110_` | pnr-inserted | 3 | `ss_n40C_1v28` 5.882/4.889 | `ss_n40C_1v28` 0.015/0.012 |
| `u_fsm/_0680_` | control-fanout | nor2_1 `u_fsm/_1133_` | pnr-inserted | 15 | `ss_n40C_1v28` 6.742/4.942 | `ss_n40C_1v60` 0.061/0.038 |
| `u_fsm/_0689_` | control-fanout | nor3_1 `u_fsm/_1145_` | pnr-inserted | 10 | `ss_n40C_1v28` 7.681/4.959 | `ss_n40C_1v60` 0.036/0.021 |
| `u_fsm/_0713_` | control-fanout | nor2_1 `u_fsm/_1180_` | pnr-inserted | 15 | `ss_n40C_1v28` 6.070/4.942 | `ss_n40C_1v60` 0.055/0.038 |
| `u_fsm/_0716_` | control-fanout | or3_1 `u_fsm/_1185_` | pnr-inserted | 32 | `ss_n40C_1v60` 2.180/1.500 | `ss_n40C_1v60` 0.119/0.081 |
| `u_fsm/net4` | reset-distribution | buf_2 `u_fsm/fanout4` | pnr-inserted | 50 | `ss_n40C_1v28` 7.507/5.000 | `ss_n40C_1v60` 0.276/0.149 |
