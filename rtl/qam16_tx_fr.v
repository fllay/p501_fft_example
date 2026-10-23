// 16-QAM frame transmitter (companion of rtl/qam16_rx.v): frames of 967 symbols = CP 8 | ZC word 63 | 14 x (63 16-QAM + 1 pilot), repeated back to back, root-raised-cosine pulse, 4 samples per symbol.
// Same ports as qpsk_tx_fr.v (it replaces it in the block design); every step happens on `ce` (= dac_valid of axi_ad9361, one sample per DAC request). `cfg` is not used.
//
//   symbol values are integers in units of 1/64 of a 16-QAM level: data +-64, +-192 (Gray 00 -192, 01 -64, 10 +192, 11 +64), pilot +-202, ZC word 202 x ZC[k] (qam16_tx_zc); the payload is the PRBS-15
//   (x^15 + x^14 + 1, seed 0x7FFF, 4 bits per symbol, first bit = MSB, restarted in every frame) as the receiver's checker expects.
//   FIR: the 12 taps of the polyphase phase (qpsk_rrc_coef) x the last 12 symbols (24 multipliers, registered, summed in the next clock; ce at most every second clock), ysum = (sum + 32) >> 6;  dac = clip((ysum(previous sample) x amp) >> 15).
//   Bit-exact model: tutorial/qam16/qam16_tx_model.py. `enable` low holds the start of the first frame and the output at zero.
`timescale 1ns/1ps
module qam16_tx_fr (
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_RESET resetn" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
  input  wire        clk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input  wire        resetn,
  input  wire        ce,
  input  wire        enable,
  input  wire [15:0] amp,                 // Q15, 0..32767
  input  wire [31:0] cfg,                 // not used
  output reg  [15:0] dac_i,
  output reg  [15:0] dac_q
);
  localparam [9:0] FRAME = 10'd967;
  localparam signed [9:0] PA = 10'sd202;
  reg  [1:0]  ph;
  reg  [9:0]  pos;                        // index in the frame of the newest symbol (hist[0])
  reg  [14:0] lfsr;                       // PRBS-15 state for the next data symbol
  reg  signed [9:0] hi [0:11];
  reg  signed [9:0] hq [0:11];
  reg  signed [17:0] ysum_i, ysum_q;
  wire [191:0] h;
  qpsk_rrc_coef u_coef (.ph(ph), .h(h));

  // ---- FIR sums (24 products). The products are registered every clock and summed in the next one: ce comes at most every second clock (3.84 MSPS on a 7.68 MHz l_clk), so the sum captured at
  //      the ce edge is that of the history / phase of the previous edge, exactly as without the register stage (the single-clock chain of 12 DSPs was 10.09 ns at the 10 ns limit of l_clk).
  reg signed [31:0] pi_r [0:11];
  reg signed [31:0] pq_r [0:11];
  integer j;
  always @(posedge clk) begin
    for (j = 0; j < 12; j = j + 1) begin
      pi_r[j] <= $signed(h[16*j +: 16]) * hi[j];
      pq_r[j] <= $signed(h[16*j +: 16]) * hq[j];
    end
  end
  reg signed [31:0] acc_i, acc_q;
  always @* begin
    acc_i = 32'sd0; acc_q = 32'sd0;
    for (j = 0; j < 12; j = j + 1) begin
      acc_i = acc_i + pi_r[j];
      acc_q = acc_q + pq_r[j];
    end
  end
  wire signed [31:0] sum_i = (acc_i + 32'sd32) >>> 6, sum_q = (acc_q + 32'sd32) >>> 6;

  // ---- the next symbol (position q)
  wire [9:0] q = (pos == 10'd966) ? 10'd0 : pos + 10'd1;
  wire [9:0] o = q - 10'd71;
  wire       pay = (q >= 10'd71);
  wire       is_pil = pay && (o[5:0] == 6'd63);
  wire [5:0] kz = (q < 10'd8) ? (6'd55 + q[5:0]) : (q[5:0] - 6'd8);
  wire signed [9:0] zr, zi;
  qam16_tx_zc u_zc (.k(kz), .zr(zr), .zi(zi));
  function pilot_neg(input [3:0] b);
    case (b) 4'd2, 4'd4, 4'd5, 4'd9, 4'd10, 4'd12: pilot_neg = 1'b1; default: pilot_neg = 1'b0; endcase
  endfunction
  function [14:0] lfsr4(input [14:0] s);
    reg [14:0] t; integer k;
    begin t = s; for (k = 0; k < 4; k = k + 1) t = {t[13:0], t[14] ^ t[13]}; lfsr4 = t; end
  endfunction
  function [3:0] ref4(input [14:0] s);
    reg [14:0] t; reg [3:0] b; integer k;
    begin t = s; for (k = 0; k < 4; k = k + 1) begin b[3 - k] = t[14]; t = {t[13:0], t[14] ^ t[13]}; end ref4 = b; end
  endfunction
  function signed [9:0] lev(input [1:0] ix);
    lev = (ix == 2'd0) ? -10'sd192 : (ix == 2'd1) ? -10'sd64 : (ix == 2'd2) ? 10'sd192 : 10'sd64;
  endfunction
  wire [14:0] lcur = (q == 10'd71) ? 15'h7FFF : lfsr;
  wire [3:0]  bits = ref4(lcur);
  wire signed [9:0] nsi = pay ? (is_pil ? (pilot_neg(o[9:6]) ? -PA : PA) : lev(bits[3:2])) : zr;
  wire signed [9:0] nsq = pay ? (is_pil ? 10'sd0 : lev(bits[1:0])) : zi;

  wire signed [35:0] prod_i = ysum_i * $signed({1'b0, amp[14:0]});
  wire signed [35:0] prod_q = ysum_q * $signed({1'b0, amp[14:0]});
  wire signed [35:0] sh_i = prod_i >>> 15, sh_q = prod_q >>> 15;

  // the first symbol of a frame (position 0 = CP[0] = ZC[55])
  wire signed [9:0] zr0, zi0;
  qam16_tx_zc u_zc0 (.k(6'd55), .zr(zr0), .zi(zi0));

  integer m;
  always @(posedge clk) begin
    if (!resetn || !enable) begin
      ph <= 2'd0; pos <= 10'd0; lfsr <= 15'h7FFF;
      for (m = 1; m < 12; m = m + 1) begin hi[m] <= 10'sd0; hq[m] <= 10'sd0; end
      hi[0] <= zr0; hq[0] <= zi0;
      ysum_i <= 18'sd0; ysum_q <= 18'sd0; dac_i <= 16'd0; dac_q <= 16'd0;
    end else if (ce) begin
      ysum_i <= sum_i[17:0]; ysum_q <= sum_q[17:0];
      dac_i <= (sh_i > 36'sd32767) ? 16'sd32767 : (sh_i < -36'sd32767) ? -16'sd32767 : sh_i[15:0];
      dac_q <= (sh_q > 36'sd32767) ? 16'sd32767 : (sh_q < -36'sd32767) ? -16'sd32767 : sh_q[15:0];
      ph <= ph + 2'd1;
      if (ph == 2'd3) begin
        pos <= q;
        if (pay && !is_pil) lfsr <= lfsr4(lcur);
        for (m = 1; m < 12; m = m + 1) begin hi[m] <= hi[m - 1]; hq[m] <= hq[m - 1]; end
        hi[0] <= nsi; hq[0] <= nsq;
      end
    end
  end
endmodule
