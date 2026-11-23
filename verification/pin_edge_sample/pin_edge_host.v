`timescale 1ps/1ps
// Stand-in HyperBus host for the bench's pin-edge sample test: one CK edge
// per `step`, with DQ, RWDS and their output enables taking the `*_in`
// values where `skew` places that change relative to the CK edge:
//   0  in the CK edge's own timestep, CK's update queued first
//   1  in the CK edge's own timestep, the other pins' updates queued first
//   2  1 ps before the CK edge
//   3  1 ps after the CK edge
// hb_cs_n is this host's own select (the test drives it); hb_dq_i and
// hb_rwds_i are the device pins hrbench.Bench drives back.
module pin_edge_host (
    input  wire        step,
    input  wire [1:0]  skew,
    input  wire [7:0]  dq_in,
    input  wire        dq_oe_in,
    input  wire        rwds_in,
    input  wire        rwds_oe_in,
    input  wire        hb_cs_n,
    input  wire [7:0]  hb_dq_i,
    input  wire        hb_rwds_i,
    output reg         hb_ck,
    output reg  [7:0]  hb_dq_o,
    output reg         hb_dq_oe,
    output reg         hb_rwds_o,
    output reg         hb_rwds_oe
);
  localparam [1:0] CK_FIRST = 2'd0, PINS_FIRST = 2'd1, PINS_BEFORE = 2'd2,
                   PINS_AFTER = 2'd3;

  initial begin
    hb_ck = 1'b0;
    hb_dq_o = 8'h00;
    hb_dq_oe = 1'b0;
    hb_rwds_o = 1'b0;
    hb_rwds_oe = 1'b0;
  end

  always @(posedge step) begin
    case (skew)
      CK_FIRST: begin
        hb_ck <= ~hb_ck;
        {hb_dq_o, hb_rwds_o, hb_dq_oe, hb_rwds_oe} <= {dq_in, rwds_in, dq_oe_in, rwds_oe_in};
      end
      PINS_FIRST: begin
        {hb_dq_o, hb_rwds_o, hb_dq_oe, hb_rwds_oe} <= {dq_in, rwds_in, dq_oe_in, rwds_oe_in};
        hb_ck <= ~hb_ck;
      end
      PINS_BEFORE: begin
        {hb_dq_o, hb_rwds_o, hb_dq_oe, hb_rwds_oe} <= {dq_in, rwds_in, dq_oe_in, rwds_oe_in};
        hb_ck <= #1 ~hb_ck;
      end
      default: begin
        hb_ck <= ~hb_ck;
        {hb_dq_o, hb_rwds_o, hb_dq_oe, hb_rwds_oe} <= #1 {dq_in, rwds_in, dq_oe_in, rwds_oe_in};
      end
    endcase
  end
endmodule
