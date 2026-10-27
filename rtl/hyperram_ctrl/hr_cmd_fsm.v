// Transaction engine: power-up interval, CA over three CK cycles (row 3),
// variable latency with RWDS-signalled doubling or fixed latency (rows 4, 10),
// linear bursts split by a CS#-low down-counter (rows 5, 9), RWDS write mask
// (row 6) and register-space access (row 7).
//
// Conventions (all of these are cross-checked against the behavioural model in
// #14; none is a datasheet number):
//  * One core clock cycle moves one 16-bit word (two bytes, DDR). A host
//    32-bit beat is two words: word 0 = dat[15:0], word 1 = dat[31:16]; the
//    first byte of a word on the bus is its upper byte.
//  * CA[47] = 1 for read, CA[46] = 1 for register space, CA[45] = 1 (linear),
//    CA[44:16] = word_addr[31:3], CA[2:0] = word_addr[2:0].
//  * Latency is counted in core clocks from the first CA clock, CA included.
//    cfg_lat is clamped to >= 4 so the RWDS sample fits inside the wait.
//  * RWDS is sampled (core clock, never the delayed strobe) on the cycle the
//    last CA pin cycle but one has completed; high selects 2 x cfg_lat.
//  * Register writes have no latency and a single word; register reads use
//    the normal latency and return a single word.
//  * Write beats cannot be paused mid-burst: an underrun ends the burst and
//    the next beat starts a new transaction. Reads are only streamed while
//    host requests are outstanding (plus HOLD cycles), so the capture ring
//    never wraps over unread data.
//  * CS#-low budget: bud is loaded with cfg_tcsm at CS# assertion and counts
//    every CS#-low cycle. A burst ends when it cannot fit another dword (write)
//    or reaches TAIL (read), after at least one dword of progress; the
//    remainder re-issues as a new transaction. tcsm_small is set when the
//    budget was too small for even that one dword.
`default_nettype none

module hr_cmd_fsm #(
    parameter HOLD = 2,
    parameter TAIL = 2
) (
    input  wire        clk,
    input  wire        rst_n,
    // configuration
    input  wire        cfg_fixed_lat,
    input  wire [3:0]  cfg_lat,
    input  wire [15:0] cfg_tcsm,
    input  wire [15:0] cfg_pu,
    input  wire [3:0]  cfg_cs_hi,
    input  wire        cfg_restart,
    // host request register
    input  wire        rq_valid,
    input  wire        rq_we,
    input  wire        rq_reg,
    input  wire [29:0] rq_adr,
    input  wire [3:0]  rq_sel,
    input  wire [31:0] rq_dat,
    output reg         rq_take,
    output reg         wr_ack,
    output reg         rd_ack,
    output reg  [31:0] rd_dat,
    // capture ring
    output reg         rd_flush,
    output reg         rd_pop1,
    output reg         rd_pop2,
    input  wire [3:0]  rd_avail,
    input  wire [15:0] rd_w0,
    input  wire [15:0] rd_w1,
    input  wire        rwds_in,
    // launch stage drive (functions of the current state only)
    output reg         cs_n_d,
    output reg         ck_en,
    output reg         dq_oe_d,
    output reg         rwds_oe_d,
    output reg  [7:0]  b0,
    output reg  [7:0]  b1,
    output reg         r0,
    output reg         r1,
    output reg         hb_reset_n,
    // status
    output wire        ready,
    output wire        busy,
    output reg         tcsm_small
);
    localparam [2:0] ST_PU = 3'd0, ST_IDLE = 3'd1, ST_CSL = 3'd2, ST_CA = 3'd3,
                     ST_LAT = 3'd4, ST_WR = 3'd5, ST_RD = 3'd6, ST_END = 3'd7;

    reg [2:0]  st;
    reg [4:0]  cnt;
    reg [15:0] pu_cnt;
    reg [3:0]  gap;
    reg [15:0] bud;
    reg        t_we;
    reg        t_reg;
    reg [29:0] t_adr;
    reg [29:0] exp_adr;
    reg [29:0] pop_adr;
    reg [2:0]  outst;
    reg        lat_first;
    reg        dw_ph;
    reg [15:0] hold_dat;
    reg [1:0]  hold_sel;
    reg [3:0]  hold_cnt;
    reg        progress;
    reg        restart_pend;
    reg        rwds_s;

    assign ready = (st != ST_PU);
    assign busy  = (st != ST_PU) && (st != ST_IDLE);

    wire [3:0] lat_eff = (cfg_lat < 4'd4) ? 4'd4 : cfg_lat;
    wire [3:0] gap_eff = (cfg_cs_hi < 4'd4) ? 4'd4 : cfg_cs_hi;

    // 16-bit word address of the transaction base and the 48-bit CA word.
    wire [31:0] w_addr = {1'b0, t_adr, 1'b0};
    wire [47:0] ca     = {~t_we, t_reg, 1'b1, w_addr[31:3], 13'd0, w_addr[2:0]};

    wire idle_start   = (st == ST_IDLE) && (gap == 4'd0) && !restart_pend;
    wire idle_rd_take = idle_start && (outst == 3'd0) && rq_valid && !rq_we;

    wire rd_active = (st == ST_CSL) || (st == ST_CA) || (st == ST_LAT) || (st == ST_RD);
    wire rd_match  = rq_valid && !rq_we && !rq_reg && !t_we && !t_reg && (rq_adr == exp_adr);
    wire rd_cont   = rd_active && rd_match && (outst < 3'd4);
    wire rd_have   = (outst != 3'd0) && (t_reg ? (rd_avail >= 4'd1) : (rd_avail >= 4'd2));
    wire rd_do_pop = (st == ST_RD) && rd_have;

    wire wr_match  = rq_valid && rq_we && (rq_reg == t_reg) && (t_reg || (rq_adr == exp_adr));
    wire wr_fits   = (bud >= 16'd4) || !progress;
    wire wr_can    = (st == ST_WR) && !dw_ph && wr_match && (t_reg || wr_fits);

    wire [2:0] outst_n = outst + {2'b00, (rd_cont || idle_rd_take)} - {2'b00, rd_do_pop};

    // ---- combinational drive and handshakes -------------------------------
    always @(*) begin
        cs_n_d    = 1'b1;
        ck_en     = 1'b0;
        dq_oe_d   = 1'b0;
        rwds_oe_d = 1'b0;
        b0        = 8'h00;
        b1        = 8'h00;
        r0        = 1'b0;
        r1        = 1'b0;
        rq_take   = 1'b0;
        wr_ack    = 1'b0;
        rd_ack    = 1'b0;
        rd_dat    = {rd_w1, rd_w0};
        rd_flush  = 1'b0;
        rd_pop1   = 1'b0;
        rd_pop2   = 1'b0;
        case (st)
            ST_CSL: begin
                cs_n_d   = 1'b0;
                rd_flush = 1'b1;
            end
            ST_CA: begin
                cs_n_d  = 1'b0;
                ck_en   = 1'b1;
                dq_oe_d = 1'b1;
                case (cnt[1:0])
                    2'd0:    begin b0 = ca[47:40]; b1 = ca[39:32]; end
                    2'd1:    begin b0 = ca[31:24]; b1 = ca[23:16]; end
                    default: begin b0 = ca[15:8];  b1 = ca[7:0];   end
                endcase
            end
            ST_LAT: begin
                cs_n_d = 1'b0;
                ck_en  = 1'b1;
            end
            ST_WR: begin
                cs_n_d = 1'b0;
                if (dw_ph) begin
                    ck_en = 1'b1;  dq_oe_d = 1'b1;  rwds_oe_d = 1'b1;
                    b0 = hold_dat[15:8];  b1 = hold_dat[7:0];
                    r0 = ~hold_sel[1];    r1 = ~hold_sel[0];
                end else if (wr_can) begin
                    ck_en = 1'b1;  dq_oe_d = 1'b1;  rwds_oe_d = 1'b1;
                    b0 = rq_dat[15:8];  b1 = rq_dat[7:0];
                    r0 = t_reg ? 1'b0 : ~rq_sel[1];
                    r1 = t_reg ? 1'b0 : ~rq_sel[0];
                    rq_take = 1'b1;
                    wr_ack  = 1'b1;
                end
            end
            ST_RD: begin
                cs_n_d  = 1'b0;
                ck_en   = 1'b1;
                rd_ack  = rd_do_pop;
                rd_pop1 = rd_do_pop && t_reg;
                rd_pop2 = rd_do_pop && !t_reg;
                rd_dat  = t_reg ? {16'h0000, rd_w0} : {rd_w1, rd_w0};
            end
            default: ;
        endcase
        if (rd_cont || idle_rd_take) rq_take = 1'b1;
    end

    // ---- sequential --------------------------------------------------------
    // total clocks from first CA clock to first data clock, minus the 4 spent
    // on the three CA states and this first wait cycle.
    wire [4:0] n_total = (cfg_fixed_lat || rwds_s) ? {lat_eff, 1'b0} : {1'b0, lat_eff};
    wire [4:0] rem_after = n_total - 5'd4;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st           <= ST_PU;
            cnt          <= 5'd0;
            pu_cnt       <= 16'd0;
            gap          <= 4'd0;
            bud          <= 16'd0;
            t_we         <= 1'b0;
            t_reg        <= 1'b0;
            t_adr        <= 30'd0;
            exp_adr      <= 30'd0;
            pop_adr      <= 30'd0;
            outst        <= 3'd0;
            lat_first    <= 1'b0;
            dw_ph        <= 1'b0;
            hold_dat     <= 16'd0;
            hold_sel     <= 2'd0;
            hold_cnt     <= 4'd0;
            progress     <= 1'b0;
            restart_pend <= 1'b0;
            rwds_s       <= 1'b0;
            hb_reset_n   <= 1'b0;
            tcsm_small   <= 1'b0;
        end else begin
            rwds_s     <= rwds_in;
            hb_reset_n <= 1'b1;
            outst      <= outst_n;
            if (cfg_restart) restart_pend <= 1'b1;
            if (rd_cont) exp_adr <= exp_adr + 30'd1;
            if (rd_do_pop) begin
                pop_adr  <= pop_adr + 30'd1;
                progress <= 1'b1;
            end
            if (st != ST_PU && st != ST_IDLE) begin
                if (bud != 16'd0) bud <= bud - 16'd1;
            end

            case (st)
                ST_PU: begin
                    if (pu_cnt >= cfg_pu) st <= ST_IDLE;
                    else                  pu_cnt <= pu_cnt + 16'd1;
                end
                ST_IDLE: begin
                    if (restart_pend) begin
                        restart_pend <= 1'b0;
                        pu_cnt       <= 16'd0;
                        outst        <= 3'd0;
                        st           <= ST_PU;
                    end else if (gap != 4'd0) begin
                        gap <= gap - 4'd1;
                    end else if (outst != 3'd0) begin
                        // read remainder after a CS#-low split
                        t_adr    <= pop_adr;
                        bud      <= cfg_tcsm;
                        progress <= 1'b0;
                        st       <= ST_CSL;
                    end else if (rq_valid) begin
                        t_we     <= rq_we;
                        t_reg    <= rq_reg;
                        t_adr    <= rq_adr;
                        exp_adr  <= rq_we ? rq_adr : rq_adr + 30'd1;
                        pop_adr  <= rq_adr;
                        bud      <= cfg_tcsm;
                        progress <= 1'b0;
                        hold_cnt <= 4'd0;
                        st       <= ST_CSL;
                    end
                end
                ST_CSL: begin
                    cnt      <= 5'd0;
                    hold_cnt <= 4'd0;
                    st       <= ST_CA;
                end
                ST_CA: begin
                    if (cnt[1:0] == 2'd2) begin
                        cnt       <= 5'd0;
                        lat_first <= 1'b1;
                        if (t_we && t_reg) begin
                            dw_ph <= 1'b0;
                            st    <= ST_WR;
                        end else begin
                            st <= ST_LAT;
                        end
                    end else begin
                        cnt <= cnt + 5'd1;
                    end
                end
                ST_LAT: begin
                    if (lat_first) begin
                        lat_first <= 1'b0;
                        if (rem_after == 5'd0) begin
                            dw_ph <= 1'b0;
                            st    <= t_we ? ST_WR : ST_RD;
                        end else begin
                            cnt <= rem_after;
                        end
                    end else if (cnt == 5'd1) begin
                        dw_ph <= 1'b0;
                        st    <= t_we ? ST_WR : ST_RD;
                    end else begin
                        cnt <= cnt - 5'd1;
                    end
                end
                ST_WR: begin
                    if (dw_ph) begin
                        dw_ph <= 1'b0;
                    end else if (wr_can) begin
                        progress <= 1'b1;
                        if (!wr_fits) tcsm_small <= 1'b1;
                        if (t_reg) begin
                            st <= ST_END;
                        end else begin
                            exp_adr  <= exp_adr + 30'd1;
                            hold_dat <= rq_dat[31:16];
                            hold_sel <= rq_sel[3:2];
                            dw_ph    <= 1'b1;
                        end
                    end else begin
                        st <= ST_END;
                    end
                end
                ST_RD: begin
                    if (rd_cont) hold_cnt <= 4'd0;
                    else if (outst_n == 3'd0 && hold_cnt != 4'hF) hold_cnt <= hold_cnt + 4'd1;
                    if ((t_reg && rd_do_pop) ||
                        (!t_reg && outst_n == 3'd0 && !rd_cont && hold_cnt >= HOLD) ||
                        (bud <= TAIL && (progress || rd_do_pop)))
                        st <= ST_END;
                    else if (bud <= TAIL)
                        tcsm_small <= 1'b1;
                end
                ST_END: begin
                    gap <= gap_eff;
                    st  <= ST_IDLE;
                end
                default: st <= ST_PU;
            endcase
            if (cfg_restart && st == ST_PU) pu_cnt <= 16'd0;
        end
    end
endmodule

`default_nettype wire
