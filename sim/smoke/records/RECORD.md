# Smoke flow record (toolchain bring-up; module is NOT part of the design)

- PDK: open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7
- Tool versions:
  - klt: klt 0.7.1.dev1765+gb61f753d0369
  - yosys (klt synthesize): yosys 0.68
  - yosys binary on PATH: Yosys 0.68 (git sha1 38e001a6f, Release, Clang /workspace/YoWASP/yosys/wasi-sdk-33.0-x86_64-linux/share/cmake/../..//bin/clang++ 22.1.0)
  - iverilog: Icarus Verilog version 13.0 (stable) (v13_0)
  - verilator: Verilator 5.050 2026-07-01 rev vUNKNOWN-built20260924
  - cocotb: 2.0.1
  - openroad (klt sta): 26Q3-1510-g6cb3f2b704

## Synthesis
- 22 cells, 296.5344 um2

## STA (clk 20 ns, ideal clock, no wire load)

| corner | setup slack (ns) | hold slack (ns) |
|---|---|---|
| tt_025C_1v80 | 19.002 | 0.42447 |
| ss_100C_1v60 | 17.8458 | 0.87226 |
| ff_n40C_1v95 | 19.3942 | 0.26641 |
