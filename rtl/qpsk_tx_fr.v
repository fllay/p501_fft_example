// QPSK transmitter with FRAMES (chapter 4e): rtl/qpsk_tx.v plus a frame generator. cfg[31] = 1 sends frames: a 64-symbol m-sequence PREAMBLE (symbol 0: the reference, phase step 0; symbols 1..63: the phase
// steps are the chips of the m-sequence x^6 + x + 1: step 0 for a chip +1, 180 degrees for a chip -1) followed by cfg[15:0] = PL symbols of PRBS-15 restarted in every frame; the frame is 64 + PL symbols and repeats
// back to back. cfg[31] = 0: the PRBS-15 runs continuously as in qpsk_tx.v. cfg is the FTW register of the register block (unused by the QPSK transmitter); change it only while `enable` is low.
// Model: tutorial/qpsk/p501_sync/qpsk_frame.py + tutorial/qpsk/p501_tx/qpsk_model.py (model(bits = frames_bits(pl, n))), bit-exact. The receiver that finds the frames: rtl/qpsk_rx_sync.v.
//
// (the header of qpsk_tx.v follows)
// QPSK transmitter with a PRBS-15 source, differential encoding and a root-raised-cosine pulse, 4 samples per symbol.
// It replaces the DAC DMA path for TX1 (like the DDS): every step happens on `ce` (= dac_valid of axi_ad9361), one sample per DAC request.
//
//   PRBS-15 (x^15 + x^14 + 1, seed 0x7FFF) -> 2-bit chunks (first bit = MSB) -> pre-differential map [0,1,3,2] -> differential encoder
//   -> constellation_dqpsk point (+,+) (-,+) (-,-) (+,-) -> polyphase RRC FIR (45 taps, roll-off 0.35, 12 taps per phase) -> x amp (Q15)
//
// It is the transmitter chain of GNU Radio's `digital.generic_mod` (differential QPSK): GNU Radio's `generic_demod` decodes it.
// The symbols are +-1, so the FIR needs adders only. `enable` low holds the state at the start of the pattern and the output at zero;
// `enable` high starts the pattern from its first bit. tutorial/qpsk/p501_tx/qpsk_model.py is the bit-exact NumPy model.
`timescale 1ns/1ps
module qpsk_tx_fr (
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_RESET resetn" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
  input  wire        clk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input  wire        resetn,
  input  wire        ce,
  input  wire        enable,
  input  wire [15:0] amp,                 // Q15, 0..32767
  input  wire [31:0] cfg,                 // bit 31: frames; bits 15:0: payload symbols per frame
  output reg  [15:0] dac_i,
  output reg  [15:0] dac_q
);
  // ---- state after the first symbol has been prepared (constants) ----
  localparam [14:0] S0 = 15'h7FFF;
  localparam        B0 = S0[14];
  localparam [14:0] S1 = {S0[13:0], S0[14] ^ S0[13]};
  localparam        B1 = S1[14];
  localparam [14:0] S2 = {S1[13:0], S1[14] ^ S1[13]};
  localparam [1:0]  C0 = {B0, B1};
  localparam [1:0]  P0 = (C0 == 2'd2) ? 2'd3 : (C0 == 2'd3) ? 2'd2 : C0;       // pre-differential map [0,1,3,2]
  localparam [1:0]  D0 = P0;                                                    // differential encoder, previous output 0
  localparam        NI0 = D0[1] ^ D0[0];                                        // 1 = negative I
  localparam        NQ0 = D0[1];                                                // 1 = negative Q

  localparam [62:0] MSEQ = 63'b111110101011001101110110100100111000101111001010001100001000001;   // m-sequence bit k = 1: chip k = -1 (phase step 180 degrees)
  wire        fr_on = cfg[31];
  wire [16:0] fl = 17'd64 + {1'b0, cfg[15:0]};                                  // frame length in symbols
  reg  [16:0] sc;                          // index in the frame of the symbol that is computed next
  wire        is_pre = (sc < 17'd64);
  wire [5:0]  mi = sc[5:0] - 6'd1;
  wire [1:0]  pre_p = (sc == 17'd0) ? 2'd0 : (MSEQ[mi] ? 2'd2 : 2'd0);           // the phase step of the preamble symbol
  reg  [1:0]  ph;                          // sample within the symbol, 0..3
  reg  [14:0] lfsr;
  reg  [1:0]  d;
  reg  [11:0] hist_i, hist_q;              // sign of the last 12 symbols, bit 0 = newest, 1 = negative
  reg  signed [16:0] ysum_i, ysum_q;       // stage 1
  wire [191:0] h;
  qpsk_rrc_coef u_coef (.ph(ph), .h(h));

  // sum of the 12 taps, sign by the symbol
  reg signed [16:0] sum_i, sum_q;
  integer j;
  always @* begin
    sum_i = 17'sd0; sum_q = 17'sd0;
    for (j = 0; j < 12; j = j + 1) begin
      sum_i = sum_i + (hist_i[j] ? -$signed(h[16*j +: 16]) : $signed(h[16*j +: 16]));
      sum_q = sum_q + (hist_q[j] ? -$signed(h[16*j +: 16]) : $signed(h[16*j +: 16]));
    end
  end

  // next symbol
  wire [14:0] l1 = {lfsr[13:0], lfsr[14] ^ lfsr[13]};
  wire [14:0] l2 = {l1[13:0], l1[14] ^ l1[13]};
  wire [1:0]  c  = {lfsr[14], l1[14]};
  wire [1:0]  pm = (c == 2'd2) ? 2'd3 : (c == 2'd3) ? 2'd2 : c;
  wire [1:0]  p  = (fr_on && is_pre) ? pre_p : pm;
  wire [1:0]  dn = d + p;
  wire        ni = dn[1] ^ dn[0];
  wire        nq = dn[1];

  wire signed [32:0] prod_i = ysum_i * $signed({1'b0, amp[14:0]});
  wire signed [32:0] prod_q = ysum_q * $signed({1'b0, amp[14:0]});

  always @(posedge clk) begin
    if (!resetn || !enable) begin
      ph <= 2'd0; lfsr <= fr_on ? S0 : S2; d <= fr_on ? 2'd0 : D0; sc <= 17'd1;
      hist_i <= fr_on ? 12'd0 : {11'd0, NI0}; hist_q <= fr_on ? 12'd0 : {11'd0, NQ0};
      ysum_i <= 17'sd0; ysum_q <= 17'sd0; dac_i <= 16'd0; dac_q <= 16'd0;
    end else if (ce) begin
      ysum_i <= sum_i; ysum_q <= sum_q;
      dac_i <= prod_i[30:15]; dac_q <= prod_q[30:15];                          // |y| < 2^15 and amp < 2^15: no overflow
      ph <= ph + 2'd1;
      if (ph == 2'd3) begin
        lfsr <= (fr_on && is_pre) ? S0 : l2; d <= dn;
        if (fr_on) sc <= ((sc + 17'd1) >= fl) ? 17'd0 : (sc + 17'd1);
        hist_i <= {hist_i[10:0], ni}; hist_q <= {hist_q[10:0], nq};
      end
    end
  end
endmodule
