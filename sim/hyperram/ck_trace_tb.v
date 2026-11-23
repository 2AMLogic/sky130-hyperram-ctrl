// Post-route CK/CA pin-waveform trace bench (issue #187; item 7 follow-up).
//
// Not a pass/fail functional bench: it drives exactly one CR0 register write
// (the `ca_spans_three_ck_cycles` stimulus, host address 0x400 -> device word
// 0x800) and one memory-space read at host address 0x155 on the routed
// netlist, and $monitor-logs the pad pins plus the CK launch path internals
// (ICG local clock, GCLK, first tap cells, selected tap net, output muxes).
// Timestamps carry the run's effective time precision -- 1 ns for the
// committed routed netlist, which carries no `timescale of its own -- so
// sub-ns numbers in the record come from SDF typ sums, not the transcript.
// The transcript is the evidence `sim/hyperram/records/CK-TRACE.md` is
// derived from; run it through `make ck-trace` (SDF-annotated) or
// `make ck-trace-gl0` (zero-delay stand-ins, the PR #188 configuration).
//
// The expected six CA bytes of the register write, in wire order, are
// 60 00 01 00 00 00 (CA[47]=0 write, CA[46]=1 register, CA[45]=1 linear,
// word address 0x800 -- see verification/ctrl/test_row03_command_address.py).
`timescale 1ns/1ps
module ck_trace_tb;
    reg clk = 0;
    reg rst_n = 0;
    reg wb_cyc = 0, wb_stb = 0, wb_we = 0;
    reg [30:0] wb_adr = 0;
    reg [3:0]  wb_sel = 0;
    reg [31:0] wb_dat_w = 0;
    wire wb_ack, wb_stall;
    wire [31:0] wb_dat_r;
    reg cfg_we = 0;
    reg [2:0] cfg_adr = 0;
    reg [15:0] cfg_wdata = 0;
    wire [15:0] cfg_rdata;
    wire hb_ck, hb_cs_n, hb_reset_n, hb_rwds_o, hb_rwds_oe, hb_dq_oe;
    wire [7:0] hb_dq_o;
    reg [7:0] hb_dq_i = 0;
    reg hb_rwds_i = 0;

    always #10 clk = ~clk;   // 50 MHz target (spec row 1)

    hyperram_ctrl dut (
        .cfg_we(cfg_we), .clk(clk), .hb_ck(hb_ck), .hb_cs_n(hb_cs_n),
        .hb_dq_oe(hb_dq_oe), .hb_reset_n(hb_reset_n), .hb_rwds_i(hb_rwds_i),
        .hb_rwds_o(hb_rwds_o), .hb_rwds_oe(hb_rwds_oe), .rst_n(rst_n),
        .wb_ack(wb_ack), .wb_cyc(wb_cyc), .wb_stall(wb_stall), .wb_stb(wb_stb),
        .wb_we(wb_we), .cfg_adr(cfg_adr), .cfg_rdata(cfg_rdata),
        .cfg_wdata(cfg_wdata), .hb_dq_i(hb_dq_i), .hb_dq_o(hb_dq_o),
        .wb_adr(wb_adr), .wb_dat_r(wb_dat_r), .wb_dat_w(wb_dat_w),
        .wb_sel(wb_sel));

    // CK launch path internals (flattened routed-netlist net names).
    wire i_icg_clk = dut.clknet_leaf_2_clk;                 // ICG local CLK (CTS leaf)
    wire i_ck_g    = dut.\u_out/ck_g ;                      // ICG GCLK = tap chain input
    wire i_dly1    = dut.\u_out/u_ck_dly/dly [1];           // after 1 delay cell
    wire i_dly8    = dut.\u_out/u_ck_dly/dly [8];           // tap-3 output (8 cells)
    wire i_mux0    = dut.\u_out/u_ck_dly/_0_ ;              // tap mux stage 1 (low taps)
    wire i_mux1    = dut.\u_out/u_ck_dly/_1_ ;              // tap mux stage 1 (high taps)
    wire i_regsclk = dut.clknet_leaf_18_clk_regs;           // a state-flop CTS leaf

    initial $timeformat(-9, 3, " ns", 12);
    always @(*)
        $monitor("EV %0t icgclk=%b rclk=%b ck_en=%b ck_g=%b dly1=%b dly8=%b m0=%b m1=%b CK=%b CS=%b OE=%b ROE=%b DQ=%h RWDS=%b tap=%b",
                 $time, i_icg_clk, i_regsclk, dut.ck_en, i_ck_g,
                 i_dly1, i_dly8, i_mux0, i_mux1, hb_ck, hb_cs_n,
                 hb_dq_oe, hb_rwds_oe, hb_dq_o, hb_rwds_o, dut.cfg_ck_tap);

    task wait_ready_;
        integer i;
        begin
            cfg_adr = 3'd6;
            for (i = 0; i < 20000; i = i + 1) begin
                #1;
                if (cfg_rdata[0] === 1'b1) i = 20000;
                else @(posedge clk);
            end
            if (cfg_rdata[0] !== 1'b1) begin
                $display("TRACE_FAIL: never ready"); $finish;
            end
        end
    endtask

    task xfer_(input we, input [30:0] adr, input [31:0] dat);
        integer i;
        begin
            @(posedge clk);
            wb_cyc <= 1; wb_stb <= 1; wb_we <= we;
            wb_adr <= adr; wb_dat_w <= dat; wb_sel <= 4'b0011;
            // single-beat: deassert stb one cycle after the accept window opens
            // (holding it to the ack would re-accept the same beat after rq_take)
            @(posedge clk);
            if (wb_stall !== 1'b1) begin
                @(posedge clk);
                wb_stb <= 0;
            end
            for (i = 0; i < 100; i = i + 1) begin
                @(posedge clk);
                if (wb_ack === 1'b1) i = 100;
            end
            wb_stb <= 0; wb_cyc <= 0; wb_we <= 0;
        end
    endtask

    initial begin
        // reset: 3 cycles, release on a rising edge (as hrbench.start does)
        @(posedge clk); @(posedge clk); @(posedge clk);
        rst_n <= 1;
        wait_ready_;
        xfer_(1'b1, {1'b1, 30'h400}, 32'h0000);   // CR0 <- 0 (register write)
        repeat (8) @(posedge clk);
        xfer_(1'b0, 31'h155, 32'h0);              // memory read at 0x155
        repeat (80) @(posedge clk);               // let the read play out at the pins
        $display("TRACE_OK");
        $finish;
    end
endmodule
