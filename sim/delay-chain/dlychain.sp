* RWDS delay-chain bench (spec open question b, decision 0003): 16
* sky130_fd_sc_hd__dlygate4sd3_1 cells in series -- the g_rwds_dly chain of
* rtl/hyperram_ctrl/hr_rd_capture.v -- loaded exactly as the committed
* controller netlist loads it (sim/hyperram/records/hyperram_ctrl.netlist.v:
* the two mux4_2 tap selectors and their clkbuf_1 buffers).
*
* This is a klt sim circuit BODY, not a standalone deck: no .control block,
* no .end, and no title semantics -- under .include every line here is
* circuit content, which is why the comment lines above all start with '*'.
*
* Deliberately NO .option scale card: the PDK sets its own
* (.option scale = 1.0u, libs.tech/ngspice/parameters/montecarlo.spice),
* which is what makes the cell's w=420000u/l=150000u device cards resolve to
* 0.42 um/0.15 um. A deck-level scale that disagreed would silently rescale
* every device in the chain.
*
* Schematic-level netlist: the PDK cell subckts carry zero parasitics, so
* every delay this bench measures excludes the chain's own layout RC. The
* committed record says so in those words.
.include $PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice

* Core supply. corners.supply_v alters this DC source per corner
* (1.62 / 1.80 / 1.98 V, decision 0004), so the key must name this element,
* not a .param.
Vdd vdd 0 DC 1.80

* Stimulus: one full-rail rising edge at ~2 ns and the matching falling edge
* at ~22 ns (20 ns high), 0.15 ns rise/fall. The levels are rescaled per
* corner by corners.supply_waveforms so the amplitude always equals that
* corner's rail -- the on-chip condition after the pad seam (pad delay and
* its swing budget are open question (a), out of scope here).
Vrwds rwds 0 DC 0 PULSE(0 1.80 2n 0.15n 0.15n 20n 40n)

* The chain. PDK pin order A VGND VNB VPB VPWR X -- NOT the Verilog port
* order (.A/.X); bodies tie VNB -> VGND, VPB -> VPWR.
Xd01 rwds  0 0 vdd vdd dly01 sky130_fd_sc_hd__dlygate4sd3_1
Xd02 dly01 0 0 vdd vdd dly02 sky130_fd_sc_hd__dlygate4sd3_1
Xd03 dly02 0 0 vdd vdd dly03 sky130_fd_sc_hd__dlygate4sd3_1
Xd04 dly03 0 0 vdd vdd dly04 sky130_fd_sc_hd__dlygate4sd3_1
Xd05 dly04 0 0 vdd vdd dly05 sky130_fd_sc_hd__dlygate4sd3_1
Xd06 dly05 0 0 vdd vdd dly06 sky130_fd_sc_hd__dlygate4sd3_1
Xd07 dly06 0 0 vdd vdd dly07 sky130_fd_sc_hd__dlygate4sd3_1
Xd08 dly07 0 0 vdd vdd dly08 sky130_fd_sc_hd__dlygate4sd3_1
Xd09 dly08 0 0 vdd vdd dly09 sky130_fd_sc_hd__dlygate4sd3_1
Xd10 dly09 0 0 vdd vdd dly10 sky130_fd_sc_hd__dlygate4sd3_1
Xd11 dly10 0 0 vdd vdd dly11 sky130_fd_sc_hd__dlygate4sd3_1
Xd12 dly11 0 0 vdd vdd dly12 sky130_fd_sc_hd__dlygate4sd3_1
Xd13 dly12 0 0 vdd vdd dly13 sky130_fd_sc_hd__dlygate4sd3_1
Xd14 dly13 0 0 vdd vdd dly14 sky130_fd_sc_hd__dlygate4sd3_1
Xd15 dly14 0 0 vdd vdd dly15 sky130_fd_sc_hd__dlygate4sd3_1
Xd16 dly15 0 0 vdd vdd dly16 sky130_fd_sc_hd__dlygate4sd3_1

* The tap loads, as the committed netlist instantiates them (cells _0627_,
* _0629_ and their clkbuf_1): an EVEN tap node drives the next delay cell
* PLUS one mux4_2 A pin, an ODD node drives only the next cell, and dly16
* drives only its mux, with no further delay cell after it. The select is
* held static (tap_sel = 0 -> S0 = S1 = low, mux A0 inputs), the condition
* the design holds for a whole burst; the per-tap delay is read at the dly
* nodes, before the mux, so the static select does not gate any tap.
Xmuxa dly02 dly10 dly06 dly14 0 0 0 0 vdd vdd tapmuxa sky130_fd_sc_hd__mux4_2
Xbufa tapmuxa 0 0 vdd vdd tapa sky130_fd_sc_hd__clkbuf_1
Xmuxb dly04 dly12 dly08 dly16 0 0 0 0 vdd vdd tapmuxb sky130_fd_sc_hd__mux4_2
Xbufb tapmuxb 0 0 vdd vdd tapb sky130_fd_sc_hd__clkbuf_1
