// padwrap.v -- minimal two-pad wrapper for the sky130 pad-liberty STA probe
// (sim/pad-sta; answers spec/target-spec.md open question (a)).
//
// One core flop (sky130_fd_sc_hd__dfxtp_1) drives an output pad's OUT; one
// input pad's IN drives a second core flop; both flops share the ideal
// `clk`. Both PAD nodes are top-level ports so set_input_delay /
// set_output_delay can anchor the pin-level paths.
//
// Pad cell: sky130_fd_io__top_gpiov2 -- an experiment-local choice.
// Decision 0002 deliberately fixes no cell list ("The pad cell names are
// *not* fixed here"); see sim/pad-sta/records/RECORD.md for the rationale
// and for why this pick does not pre-empt the sibling I/O-ring repo.
//
// Control-pin ties (all stated in RECORD.md; changing them changes the
// measured arcs):
//   output pad u_opad: OE_N=0 (active-low output enable), INP_DIS=1
//     (receiver off), DM=3'b110, SLOW=0 (fast output table -- the liberty
//     indexes OUT->PAD delay by `!OE_N & DM & SLOW` per-mode `when`
//     conditions), IB_MODE_SEL=0, VTRIP_SEL=0 (receiver config, moot while
//     INP_DIS=1 but tied anyway), HLD_H_N=1, HLD_OVR=0 (bus hold off),
//     ENABLE_H=1, ENABLE_INP_H=0, ENABLE_VDDA_H=1, ENABLE_VDDIO=1,
//     ENABLE_VSWITCH_H=1 (enabled domains), ANALOG_EN=0, ANALOG_SEL=0,
//     ANALOG_POL=0 (analog mux off).
//   input pad u_ipad: OE_N=1 (output driver off), INP_DIS=0 (receiver on),
//     DM=3'b001 (input mode; the PAD->IN liberty arcs are conditioned only
//     on IB_MODE_SEL/VTRIP_SEL, so this tie does not gate the measured
//     arc), IB_MODE_SEL=0, VTRIP_SEL=0 (normal CMOS input, low trip
//     point), remaining controls as for u_opad.
//   Analog access nodes (PAD_A_NOESD_H, PAD_A_ESD_0_H, PAD_A_ESD_1_H) and
//   the pad's ESD tie outputs (TIE_HI_ESD, TIE_LO_ESD) carry no timing
//   arcs; they are left unconnected at this wrapper's boundary (documented
//   here, not silently dropped). AMUXBUS_A/B are tied to VSS (analog mux
//   buses at ground when unused).
//   Power pins are tied to the wrapper rails for completeness (pg_pin
//   entries in the liberty; STA-irrelevant).
module padwrap (
  input  wire clk,
  inout  wire pad_opad,
  inout  wire pad_ipad
);
  wire       vdd;
  wire       vss;
  wire [2:0] dm_out;
  wire [2:0] dm_in;
  wire       tx_q;
  wire       rx_d;
  wire       opad_in;

  assign vdd    = 1'b1;
  assign vss    = 1'b0;
  assign dm_out = 3'b110;
  assign dm_in  = 3'b001;

  // output direction: u_tx/CLK -> u_tx/Q -> u_opad/OUT -> u_opad/PAD
  sky130_fd_sc_hd__dfxtp_1 u_tx (
    .D(1'b0), .CLK(clk), .Q(tx_q)
  );

  sky130_fd_io__top_gpiov2 u_opad (
    .PAD(pad_opad),
    .OUT(tx_q),
    .OE_N(1'b0),
    .INP_DIS(1'b1),
    .DM(dm_out),
    .SLOW(1'b0),
    .HLD_H_N(1'b1),
    .HLD_OVR(1'b0),
    .IB_MODE_SEL(1'b0),
    .VTRIP_SEL(1'b0),
    .ANALOG_EN(1'b0),
    .ANALOG_SEL(1'b0),
    .ANALOG_POL(1'b0),
    .ENABLE_H(1'b1),
    .ENABLE_INP_H(1'b0),
    .ENABLE_VDDA_H(1'b1),
    .ENABLE_VDDIO(1'b1),
    .ENABLE_VSWITCH_H(1'b1),
    .IN(opad_in),
    .IN_H(),
    .PAD_A_NOESD_H(),
    .PAD_A_ESD_0_H(),
    .PAD_A_ESD_1_H(),
    .AMUXBUS_A(vss),
    .AMUXBUS_B(vss),
    .TIE_HI_ESD(),
    .TIE_LO_ESD(),
    .VDDIO(vdd),
    .VDDIO_Q(vdd),
    .VDDA(vdd),
    .VCCD(vdd),
    .VSWITCH(vdd),
    .VCCHIB(vdd),
    .VSSIO(vss),
    .VSSIO_Q(vss),
    .VSSD(vss),
    .VSSA(vss)
  );

  // input direction: u_ipad/PAD -> u_ipad/IN -> u_rx/D
  sky130_fd_io__top_gpiov2 u_ipad (
    .PAD(pad_ipad),
    .OUT(),
    .OE_N(1'b1),
    .INP_DIS(1'b0),
    .DM(dm_in),
    .SLOW(1'b0),
    .HLD_H_N(1'b1),
    .HLD_OVR(1'b0),
    .IB_MODE_SEL(1'b0),
    .VTRIP_SEL(1'b0),
    .ANALOG_EN(1'b0),
    .ANALOG_SEL(1'b0),
    .ANALOG_POL(1'b0),
    .ENABLE_H(1'b1),
    .ENABLE_INP_H(1'b0),
    .ENABLE_VDDA_H(1'b1),
    .ENABLE_VDDIO(1'b1),
    .ENABLE_VSWITCH_H(1'b1),
    .IN(rx_d),
    .IN_H(),
    .PAD_A_NOESD_H(),
    .PAD_A_ESD_0_H(),
    .PAD_A_ESD_1_H(),
    .AMUXBUS_A(vss),
    .AMUXBUS_B(vss),
    .TIE_HI_ESD(),
    .TIE_LO_ESD(),
    .VDDIO(vdd),
    .VDDIO_Q(vdd),
    .VDDA(vdd),
    .VCCD(vdd),
    .VSWITCH(vdd),
    .VCCHIB(vdd),
    .VSSIO(vss),
    .VSSIO_Q(vss),
    .VSSD(vss),
    .VSSA(vss)
  );

  sky130_fd_sc_hd__dfxtp_1 u_rx (
    .D(rx_d), .CLK(clk), .Q()
  );

endmodule
