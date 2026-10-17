// Scales the DDS output (cos in [15:0], sin in [31:16]) and drives the DAC input of axi_ad9361:
//   dac_i = cos * amp, dac_q = sin * amp  (amp in Q15), or zeros when `enable` is low.
// Everything advances only on `ce` (= dac_valid of axi_ad9361): exactly one new sample per DAC request,
// and the outputs hold their value in between (same behaviour as the FIFO this block replaces).
`timescale 1ns/1ps
module dds_scale (
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_RESET resetn" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
  input  wire        clk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input  wire        resetn,
  input  wire        ce,

  input  wire [31:0] dds_tdata,      // {sin[15:0], cos[15:0]}, signed
  input  wire [15:0] amp,            // Q15, 0..32767
  input  wire        enable,

  output reg  [15:0] dac_i,
  output reg  [15:0] dac_q
);
  wire signed [15:0] c = dds_tdata[15:0];
  wire signed [15:0] s = dds_tdata[31:16];
  wire signed [16:0] a = {1'b0, amp};

  reg signed [32:0] pc, ps;
  reg               en_q;

  always @(posedge clk) begin
    if (!resetn) begin
      pc <= 33'sd0; ps <= 33'sd0; en_q <= 1'b0;
      dac_i <= 16'd0; dac_q <= 16'd0;
    end else if (ce) begin
      pc    <= c * a;
      ps    <= s * a;
      en_q  <= enable;
      dac_i <= en_q ? pc[30:15] : 16'd0;
      dac_q <= en_q ? ps[30:15] : 16'd0;
    end
  end
endmodule
