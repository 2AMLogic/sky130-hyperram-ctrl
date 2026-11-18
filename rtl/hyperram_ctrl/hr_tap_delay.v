// Shared tap-selectable delay line: 16 sky130_fd_sc_hd__dlygate4sd3_1 cells in
// series, tap k selecting 2*(k+1) cells (taps at 2,4,..16). Instantiated twice
// on the repo's highest-risk path: hr_rd_capture shifts RWDS into the data eye
// (decision 0003), hr_dq_out delays the gated bus clock by a quarter period
// (decision 0001). One shared module means a change to the delay primitive --
// cell swap, chain length, tap spacing -- is made once and cannot silently
// diverge between the CK and RWDS chains.
//
// Named cells (kept for STA / SPICE): the chain cells of each instantiation.
// The chain lives under generate block g_dly as u_dly[i]; each instantiation
// keeps the contract name of the chain it replaces -- u_ck_dly in hr_dq_out,
// u_rwds_dly in hr_rd_capture -- so the netlist hierarchy still names them
// (e.g. u_ck_dly.g_dly[0].u_dly). The tap mux select is static during
// operation.
//
// Tap k selects 2*(k+1) cells: taps[0] is taken after 2 cells, taps[7] after
// all 16.
`default_nettype none

module hr_tap_delay (
    input  wire       in_sig,
    input  wire [2:0] tap_sel,
    output wire       out_sig
);
    wire [16:0] dly;
    assign dly[0] = in_sig;
    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : g_dly
            sky130_fd_sc_hd__dlygate4sd3_1 u_dly (.A(dly[i]), .X(dly[i+1]));
        end
    endgenerate

    wire [7:0] taps = {dly[16], dly[14], dly[12], dly[10], dly[8], dly[6], dly[4], dly[2]};
    assign out_sig = taps[tap_sel];
endmodule

`default_nettype wire
