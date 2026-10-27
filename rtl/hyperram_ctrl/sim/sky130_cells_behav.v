// Zero-delay behavioural stand-ins for the sky130_fd_sc_hd cells the
// controller instantiates by name. For lint and RTL simulation ONLY: they are
// not synthesis sources (synthesis maps the real cells from the liberty) and
// they carry no timing, so they say nothing about delay-chain or DDR timing.
`default_nettype none
/* verilator lint_off DECLFILENAME */
/* verilator lint_off LATCH */

module sky130_fd_sc_hd__mux2_1 (input wire A0, input wire A1, input wire S, output wire X);
    assign X = S ? A1 : A0;
endmodule

module sky130_fd_sc_hd__dlygate4sd3_1 (input wire A, output wire X);
    assign X = A;
endmodule

// Latch-based clock gate: GATE is sampled while CLK is low.
module sky130_fd_sc_hd__dlclkp_1 (input wire CLK, input wire GATE, output wire GCLK);
    reg gate_l;
    always @(*) if (!CLK) gate_l = GATE;
    assign GCLK = CLK & gate_l;
endmodule

`default_nettype wire
