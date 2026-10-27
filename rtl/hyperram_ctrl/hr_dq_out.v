// Pad-facing launch stage: DDR data/RWDS outputs, CS#, output enables and the
// CK output (gated core clock delayed by a tap-selected standard-cell chain).
//
// Timing contract (spec rows 14, 3): every drive input describes one core-clock
// cycle k. At edge k+1 the byte pair is launched: b0 at the rising edge, b1 at
// the falling edge half a cycle later. CK for that cycle is the gated clock
// pulse of edge k+1 delayed by the selected tap (design target: a quarter
// period, so CK edges centre in each byte). ck_en is NOT registered here: it
// is consumed by the clock gate in the low phase of cycle k, so it must be a
// function of the cycle-k state, exactly like the other drive inputs.
//
// Named cells (kept for STA / SPICE): u_ddr_dq[i], u_ddr_rwds, u_ck_icg,
// u_ck_dly[i]. The tap mux select is static during operation.
`default_nettype none

module hr_dq_out (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       cs_n_d,
    input  wire       ck_en,
    input  wire       dq_oe_d,
    input  wire       rwds_oe_d,
    input  wire [7:0] b0,
    input  wire [7:0] b1,
    input  wire       r0,
    input  wire       r1,
    input  wire [2:0] ck_tap,
    output wire       hb_ck,
    output reg        hb_cs_n,
    output wire [7:0] hb_dq_o,
    output reg        hb_dq_oe,
    output wire       hb_rwds_o,
    output reg        hb_rwds_oe
);
    reg [7:0] b0_r;
    reg [7:0] b1_r;
    reg [7:0] b1_n;
    reg       r0_r;
    reg       r1_r;
    reg       r1_n;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            hb_cs_n    <= 1'b1;
            hb_dq_oe   <= 1'b0;
            hb_rwds_oe <= 1'b0;
            b0_r       <= 8'h00;
            b1_r       <= 8'h00;
            r0_r       <= 1'b0;
            r1_r       <= 1'b0;
        end else begin
            hb_cs_n    <= cs_n_d;
            hb_dq_oe   <= dq_oe_d;
            hb_rwds_oe <= rwds_oe_d;
            b0_r       <= b0;
            b1_r       <= b1;
            r0_r       <= r0;
            r1_r       <= r1;
        end
    end

    // Second byte of the pair launches half a cycle after the first.
    always @(negedge clk) begin
        b1_n <= b1_r;
        r1_n <= r1_r;
    end

    // DDR output mux: clk high shows the rising-edge byte, clk low the other.
    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : g_ddr_dq
            sky130_fd_sc_hd__mux2_1 u_ddr_dq (.A0(b1_n[i]), .A1(b0_r[i]), .S(clk), .X(hb_dq_o[i]));
        end
    endgenerate
    sky130_fd_sc_hd__mux2_1 u_ddr_rwds (.A0(r1_n), .A1(r0_r), .S(clk), .X(hb_rwds_o));

    // CK: gated core clock, then tap-selected delay (taps at 2,4,..16 cells).
    wire ck_g;
    sky130_fd_sc_hd__dlclkp_1 u_ck_icg (.CLK(clk), .GATE(ck_en), .GCLK(ck_g));

    wire [16:0] ck_c;
    assign ck_c[0] = ck_g;
    generate
        for (i = 0; i < 16; i = i + 1) begin : g_ck_dly
            sky130_fd_sc_hd__dlygate4sd3_1 u_ck_dly (.A(ck_c[i]), .X(ck_c[i+1]));
        end
    endgenerate

    wire [7:0] ck_taps = {ck_c[16], ck_c[14], ck_c[12], ck_c[10], ck_c[8], ck_c[6], ck_c[4], ck_c[2]};
    assign hb_ck = ck_taps[ck_tap];
endmodule

`default_nettype wire
