// HyperBus-class memory controller, top level (v1: 50 MHz target, no DLL, no
// calibration; decisions 0001 to 0005).
//
// Host port: Wishbone-class 32-bit, pipelined (rows 15, 16). A beat is
// accepted when wb_cyc & wb_stb & ~wb_stall; wb_ack returns one cycle per
// beat (write: the beat is committed to the bus; read: data valid on wb_dat_r
// with the ack). Sequential beats (adr+1, same direction) continue one bus
// burst; anything else starts a new transaction. wb_adr[30] selects the
// device register space (single 16-bit word, wb_dat_w[15:0] / wb_dat_r[15:0]);
// wb_adr[29:0] is the 32-bit-word address. Dropping wb_cyc does not cancel an
// accepted beat.
//
// Configuration port (cfg_*): 16-bit registers, read combinationally.
//   0 CTRL    [0] fixed latency, [1] restart power-up interval (self-clearing)
//   1 LAT     [3:0] initial latency in clocks (clamped to >= 4)
//   2 TCSM    CS#-low budget in core clocks (row 9)
//   3 PU      power-up interval in core clocks (row 8)
//   4 CS_HI   [3:0] minimum CS#-high clocks (clamped to >= 4)
//   5 TAPS    [2:0] read-capture tap, [6:4] CK-shift tap (static in operation)
//   6 STATUS  [0] ready, [1] tcsm_small (sticky, cleared by restart), [2] busy
// Reset values are parameters with NO datasheet value behind them; they are
// placeholders to be programmed from spec/device-model-params.md once ratified.
`default_nettype none

module hyperram_ctrl #(
    parameter [3:0]  LAT_DEFAULT    = 4'd6,
    parameter [15:0] TCSM_DEFAULT   = 16'd64,
    parameter [15:0] PU_DEFAULT     = 16'd256,
    parameter [3:0]  CS_HI_DEFAULT  = 4'd4,
    parameter [2:0]  RD_TAP_DEFAULT = 3'd3,
    parameter [2:0]  CK_TAP_DEFAULT = 3'd3
) (
    input  wire        clk,
    input  wire        rst_n,
    // host (Wishbone-class, pipelined)
    input  wire        wb_cyc,
    input  wire        wb_stb,
    input  wire        wb_we,
    input  wire [30:0] wb_adr,
    input  wire [3:0]  wb_sel,
    input  wire [31:0] wb_dat_w,
    output reg         wb_ack,
    output wire        wb_stall,
    output reg  [31:0] wb_dat_r,
    // configuration
    input  wire        cfg_we,
    input  wire [2:0]  cfg_adr,
    input  wire [15:0] cfg_wdata,
    output reg  [15:0] cfg_rdata,
    // bus pins (pad cells are outside this block)
    output wire        hb_ck,
    output wire        hb_cs_n,
    output wire        hb_reset_n,
    output wire [7:0]  hb_dq_o,
    output wire        hb_dq_oe,
    input  wire [7:0]  hb_dq_i,
    output wire        hb_rwds_o,
    output wire        hb_rwds_oe,
    input  wire        hb_rwds_i
);
    // ---- configuration registers ------------------------------------------
    reg        cfg_fixed_lat;
    reg [3:0]  cfg_lat;
    reg [15:0] cfg_tcsm;
    reg [15:0] cfg_pu;
    reg [3:0]  cfg_cs_hi;
    reg [2:0]  cfg_rd_tap;
    reg [2:0]  cfg_ck_tap;
    reg        cfg_restart;

    wire ready, busy, tcsm_small;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cfg_fixed_lat <= 1'b0;
            cfg_lat       <= LAT_DEFAULT;
            cfg_tcsm      <= TCSM_DEFAULT;
            cfg_pu        <= PU_DEFAULT;
            cfg_cs_hi     <= CS_HI_DEFAULT;
            cfg_rd_tap    <= RD_TAP_DEFAULT;
            cfg_ck_tap    <= CK_TAP_DEFAULT;
            cfg_restart   <= 1'b0;
        end else begin
            cfg_restart <= 1'b0;
            if (cfg_we) begin
                case (cfg_adr)
                    3'd0: begin cfg_fixed_lat <= cfg_wdata[0]; cfg_restart <= cfg_wdata[1]; end
                    3'd1: cfg_lat    <= cfg_wdata[3:0];
                    3'd2: cfg_tcsm   <= cfg_wdata;
                    3'd3: cfg_pu     <= cfg_wdata;
                    3'd4: cfg_cs_hi  <= cfg_wdata[3:0];
                    3'd5: begin cfg_rd_tap <= cfg_wdata[2:0]; cfg_ck_tap <= cfg_wdata[6:4]; end
                    default: ;
                endcase
            end
        end
    end

    always @(*) begin
        case (cfg_adr)
            3'd0:    cfg_rdata = {15'd0, cfg_fixed_lat};
            3'd1:    cfg_rdata = {12'd0, cfg_lat};
            3'd2:    cfg_rdata = cfg_tcsm;
            3'd3:    cfg_rdata = cfg_pu;
            3'd4:    cfg_rdata = {12'd0, cfg_cs_hi};
            3'd5:    cfg_rdata = {9'd0, cfg_ck_tap, 1'b0, cfg_rd_tap};
            3'd6:    cfg_rdata = {13'd0, busy, tcsm_small, ready};
            default: cfg_rdata = 16'd0;
        endcase
    end

    // ---- host request register ---------------------------------------------
    reg         rq_valid;
    reg         rq_we;
    reg         rq_reg;
    reg  [29:0] rq_adr;
    reg  [3:0]  rq_sel;
    reg  [31:0] rq_dat;
    wire        rq_take;
    wire        wr_ack;
    wire        rd_ack;
    wire [31:0] rd_dat;

    assign wb_stall = rq_valid & ~rq_take;
    wire accept = wb_cyc & wb_stb & ~wb_stall;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rq_valid <= 1'b0;
            rq_we    <= 1'b0;
            rq_reg   <= 1'b0;
            rq_adr   <= 30'd0;
            rq_sel   <= 4'd0;
            rq_dat   <= 32'd0;
            wb_ack   <= 1'b0;
            wb_dat_r <= 32'd0;
        end else begin
            wb_ack   <= wr_ack | rd_ack;
            wb_dat_r <= rd_ack ? rd_dat : 32'd0;
            if (accept) begin
                rq_valid <= 1'b1;
                rq_we    <= wb_we;
                rq_reg   <= wb_adr[30];
                rq_adr   <= wb_adr[29:0];
                rq_sel   <= wb_sel;
                rq_dat   <= wb_dat_w;
            end else if (rq_take) begin
                rq_valid <= 1'b0;
            end
        end
    end

    // ---- engine, launch stage, capture -------------------------------------
    wire        rd_flush, rd_pop1, rd_pop2;
    wire [3:0]  rd_avail;
    wire [15:0] rd_w0, rd_w1;
    wire        cs_n_d, ck_en, dq_oe_d, rwds_oe_d, r0, r1;
    wire [7:0]  b0, b1;

    hr_cmd_fsm u_fsm (
        .clk(clk), .rst_n(rst_n),
        .cfg_fixed_lat(cfg_fixed_lat), .cfg_lat(cfg_lat), .cfg_tcsm(cfg_tcsm),
        .cfg_pu(cfg_pu), .cfg_cs_hi(cfg_cs_hi), .cfg_restart(cfg_restart),
        .rq_valid(rq_valid), .rq_we(rq_we), .rq_reg(rq_reg), .rq_adr(rq_adr),
        .rq_sel(rq_sel), .rq_dat(rq_dat),
        .rq_take(rq_take), .wr_ack(wr_ack), .rd_ack(rd_ack), .rd_dat(rd_dat),
        .rd_flush(rd_flush), .rd_pop1(rd_pop1), .rd_pop2(rd_pop2),
        .rd_avail(rd_avail), .rd_w0(rd_w0), .rd_w1(rd_w1), .rwds_in(hb_rwds_i),
        .cs_n_d(cs_n_d), .ck_en(ck_en), .dq_oe_d(dq_oe_d), .rwds_oe_d(rwds_oe_d),
        .b0(b0), .b1(b1), .r0(r0), .r1(r1), .hb_reset_n(hb_reset_n),
        .ready(ready), .busy(busy), .tcsm_small(tcsm_small)
    );

    hr_dq_out u_out (
        .clk(clk), .rst_n(rst_n),
        .cs_n_d(cs_n_d), .ck_en(ck_en), .dq_oe_d(dq_oe_d), .rwds_oe_d(rwds_oe_d),
        .b0(b0), .b1(b1), .r0(r0), .r1(r1), .ck_tap(cfg_ck_tap),
        .hb_ck(hb_ck), .hb_cs_n(hb_cs_n), .hb_dq_o(hb_dq_o), .hb_dq_oe(hb_dq_oe),
        .hb_rwds_o(hb_rwds_o), .hb_rwds_oe(hb_rwds_oe)
    );

    hr_rd_capture u_cap (
        .clk(clk), .rst_n(rst_n), .tap_sel(cfg_rd_tap),
        .dq_i(hb_dq_i), .rwds_i(hb_rwds_i),
        .flush(rd_flush), .pop1(rd_pop1), .pop2(rd_pop2),
        .avail(rd_avail), .w0(rd_w0), .w1(rd_w1)
    );
endmodule

`default_nettype wire
