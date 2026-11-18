// Read capture (spec rows 11, 12; decision 0003): RWDS is delayed through a
// chain of sky130_fd_sc_hd delay cells with a static, register-selected tap
// and then clocks the data capture flops on both edges. No calibration.
// The chain is the shared hr_tap_delay module (see its header for the
// named-cell contract and the tap numbering).
//
// Capture domain (clocked by the delayed RWDS): byte 0 is taken on the
// rising edge, byte 1 on the falling edge, and the 16-bit word is written to
// an 8-entry ring with a gray-coded write pointer. The core clock domain reads
// the ring through a 2-flop pointer synchroniser. Ring data are stable for
// several core cycles before the synchronised pointer exposes them, so the
// ring-to-core path is a multi-cycle path (constrain it in STA, do not treat
// it as a single-cycle path). The core side discards stale entries with
// `flush` at the start of each read transaction.
//
// Named cells: u_rwds_dly (the chain, an hr_tap_delay instantiation).
`default_nettype none

module hr_rd_capture (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [2:0]  tap_sel,
    input  wire [7:0]  dq_i,
    input  wire        rwds_i,
    input  wire        flush,
    input  wire        pop1,
    input  wire        pop2,
    output wire [3:0]  avail,
    output wire [15:0] w0,
    output wire [15:0] w1
);
    // ---- delay chain -------------------------------------------------------
    // 16-cell standard-cell chain, static register-selected tap (decision
    // 0003); tap numbering and the STA/SPICE contract live in hr_tap_delay.v.
    wire       rwds_d;
    hr_tap_delay u_rwds_dly (.in_sig(rwds_i), .tap_sel(tap_sel), .out_sig(rwds_d));

    // ---- capture domain ----------------------------------------------------
    reg [7:0]  cap_b0;
    reg [3:0]  wp;
    reg [3:0]  wg;
    reg [15:0] mem [0:7];

    always @(posedge rwds_d or negedge rst_n) begin
        if (!rst_n) cap_b0 <= 8'h00;
        else        cap_b0 <= dq_i;
    end

    wire [3:0] wp_n = wp + 4'd1;
    always @(negedge rwds_d or negedge rst_n) begin
        if (!rst_n) begin
            wp <= 4'd0;
            wg <= 4'd0;
        end else begin
            wp <= wp_n;
            wg <= wp_n ^ {1'b0, wp_n[3:1]};
        end
    end
    always @(negedge rwds_d) mem[wp[2:0]] <= {cap_b0, dq_i};

    // ---- core domain -------------------------------------------------------
    reg [3:0] wg_s1;
    reg [3:0] wg_s2;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wg_s1 <= 4'd0;
            wg_s2 <= 4'd0;
        end else begin
            wg_s1 <= wg;
            wg_s2 <= wg_s1;
        end
    end

    wire [3:0] wp_s = {wg_s2[3], wg_s2[3] ^ wg_s2[2], wg_s2[3] ^ wg_s2[2] ^ wg_s2[1],
                       wg_s2[3] ^ wg_s2[2] ^ wg_s2[1] ^ wg_s2[0]};

    reg [3:0] rp;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)      rp <= 4'd0;
        else if (flush)  rp <= wp_s;
        else if (pop2)   rp <= rp + 4'd2;
        else if (pop1)   rp <= rp + 4'd1;
    end

    assign avail = wp_s - rp;
    assign w0 = mem[rp[2:0]];
    assign w1 = mem[rp[2:0] + 3'd1];
endmodule

`default_nettype wire
