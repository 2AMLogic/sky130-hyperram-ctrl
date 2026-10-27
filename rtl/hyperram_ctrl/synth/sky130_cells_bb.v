// Port-only blackbox declarations for the sky130_fd_sc_hd cells the controller
// instantiates by name, so `klt synthesize` keeps them as instances (it reads
// no liberty cells as blackboxes by itself). Synthesis input ONLY; the cells
// are mapped from the liberty by later flow steps. Lint/simulation use
// ../sim/sky130_cells_behav.v instead. Their area is not in the synthesis
// area figure (blackbox_modules in the klt envelope).
`default_nettype none

(* blackbox *)
module sky130_fd_sc_hd__mux2_1 (input wire A0, input wire A1, input wire S, output wire X);
endmodule

(* blackbox *)
module sky130_fd_sc_hd__dlygate4sd3_1 (input wire A, output wire X);
endmodule

(* blackbox *)
module sky130_fd_sc_hd__dlclkp_1 (input wire CLK, input wire GATE, output wire GCLK);
endmodule

`default_nettype wire
