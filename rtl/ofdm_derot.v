// Gain and derotation of one ADC sample of the OFDM receiver (bit-exact: tutorial/ofdm/ofdm_fixed.py, derotate):
//   g = clip((x G + 128) >> 8, -16384, 16383) (15 bit),  theta = (w m) mod 2^32,  c + j s = table[theta >> 22] (Q15),  y = (g_i + j g_q)(c - j s) rounded >> 15 (16 bit)
// m is the sample index counted from the start of the S&C symbol, w the carrier in turns x 2^32 per sample. Latency 7 clocks, one sample per clock.
`timescale 1ns/1ps
module ofdm_derot (
  input  wire        clk,
  input  wire        in_valid,
  input  wire signed [11:0] xi, xq,
  input  wire [11:0] m,
  input  wire signed [31:0] w,
  input  wire [15:0] gain,
  output wire        out_valid,
  output reg  signed [15:0] yr, yi
);
  reg signed [11:0] a_i, a_q; reg [11:0] a_m; reg signed [31:0] a_w; reg [15:0] a_g; reg v1, v2, v3, v4, v5, v6;
  reg signed [28:0] gp_i, gp_q; reg [31:0] th;
  reg signed [14:0] g_i, g_q; reg [9:0] idx;
  wire signed [15:0] tc, ts;
  reg signed [14:0] h_i, h_q;
  reg signed [31:0] q0, q1, q2, q3;
  qpsk_rx_trig u_trig (.clk(clk), .a(idx), .c(tc), .s(ts));
  wire signed [28:0] r_i = gp_i + 29'sd128, r_q = gp_q + 29'sd128;
  wire signed [28:0] sh_i = r_i >>> 8, sh_q = r_q >>> 8;
  always @(posedge clk) begin
    v1 <= in_valid; v2 <= v1; v3 <= v2; v4 <= v3; v5 <= v4; v6 <= v5;
    // 1: inputs, 2: gain product and phase
    a_i <= xi; a_q <= xq; a_m <= m; a_w <= w; a_g <= gain;
    gp_i <= a_i * $signed({1'b0, a_g}); gp_q <= a_q * $signed({1'b0, a_g}); th <= a_w * $signed({1'b0, a_m});
    // 3: round, shift, clip; the table address
    g_i <= (sh_i > 29'sd16383) ? 15'sd16383 : (sh_i < -29'sd16384) ? -15'sd16384 : sh_i[14:0];
    g_q <= (sh_q > 29'sd16383) ? 15'sd16383 : (sh_q < -29'sd16384) ? -15'sd16384 : sh_q[14:0];
    idx <= th[31:22];
    // 4: the table output is registered with idx: tc, ts valid one clock later; hold the gains
    h_i <= g_i; h_q <= g_q;
    // 5: products
    q0 <= h_i * tc; q1 <= h_q * ts; q2 <= h_q * tc; q3 <= h_i * ts;
    // 6: sums and rounding
    yr <= (q0 + q1 + 32'sd16384) >>> 15;
    yi <= (q2 - q3 + 32'sd16384) >>> 15;
  end
  assign out_valid = v6;
endmodule
