// SMOKE MODULE -- NOT PART OF THE HYPERRAM CONTROLLER DESIGN.
//
// A registered 8-bit counter whose only job is to exercise the toolchain
// (lint, cocotb + Icarus, synthesis to sky130_fd_sc_hd, three-corner STA)
// before any real RTL exists. Never instantiate it from design RTL and never
// cite its results as evidence about the controller.
`default_nettype none

module smoke_counter (
    input  wire       clk,
    input  wire       rst_n,  // asynchronous, active low
    output reg  [7:0] count
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) count <= 8'd0;
        else        count <= count + 8'd1;
    end
endmodule

`default_nettype wire
