// OFDM frame transmitter (companion of rtl/ofdm_rx.v), 3840 samples = 1 ms at 3.84 MS/s, repeated back to back. Two frames, the ones of the two variants of the receiver (parameter STS):
//   STS = 0 (overlay p501_ofdm_rx_sc):  48 slots of 80 samples: slot 0 the Schmidl-and-Cox symbol (even subcarriers) | 1, 2 the training symbol twice | 3 .. 46 the 44 data symbols | 47 idle
//   STS = 1 (overlay p501_ofdm_rx_sts): 47 slots: slot 0 the short training field (128 samples: the 64-sample IFFT of every 4th subcarrier twice, period 16) | 1 the long training field (160 samples: the last 32 samples of the
//               training symbol, then the symbol twice) | 2 .. 45 the 44 data symbols (80 samples) | 46 idle (32 samples)
// A data symbol is 24 x 16-QAM from the PRBS-15 (restarted in every frame, 4 bits per subcarrier, Gray 00 -3, 01 -1, 10 +3, 11 +1) and 4 QPSK pilots x the polarity of IEEE 802.11, with a prefix of 16 samples.
// Same ports as qpsk_tx_fr.v / qam16_tx_fr.v (it replaces them in the block design) plus the AXI clock: the DAC side (clk = l_clk, ce = dac_valid of axi_ad9361, one sample per ce, at least 2 clocks apart) only reads a
// buffer of 4 banks of 64 samples; the symbols are made in the other clock domain (fclk = the AXI clock, 100 MHz): the 28 loaded subcarrier values of a slot, the 64-point IFFT (the FFT of rtl/ofdm_fft.v of the receiver on the
// conjugated values, conjugated again: 64 + 768 clocks = 9 us, a slot lasts 8.3 .. 33 us), the 64 samples into a bank. The player reads a slot from its bank as the pattern of the slot says (prefix = the last samples).
// Handshake: the player toggles `free_tog` when it has taken the last sample of a bank, the generator toggles `rdy_tog` when a bank is written (2-flop synchronisers, events by edge detection); the generator may fill a bank
// while it has a credit (4 at the start, +1 per free event), so it works up to three slots ahead. The idle slot needs no bank content: the player outputs zeros.
// Integer values (a loaded subcarrier of unit power = 1518 counts): QPSK / pilot +-1073 on I and Q, S&C +-1518, STS +-2319, 16-QAM levels +-480, +-1440. Bit-exact model: tutorial/ofdm/ofdm_tx_fixed.py.
// DAC value = clip((x * amp) >> 15) (amp Q15, bits 14:0), 2 ce after the buffer address. `enable` low holds the output at zero and the generator at the start of the frame; enable high starts slot 0.
// status: [0] the player is playing, [1] an underrun (a slot was not ready: sticky until enable low), [2] FFT overflow (sticky), [3] 0.
`timescale 1ns/1ps
module ofdm_tx #(parameter STS = 0) (
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_RESET resetn" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
  input  wire        clk,                 // l_clk
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input  wire        resetn,
  input  wire        ce,
  input  wire        enable,
  input  wire [15:0] amp,                 // Q15, 0 .. 32767
  input  wire [31:0] cfg,                 // not used
  output reg  [15:0] dac_i,
  output reg  [15:0] dac_q,
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_RESET fresetn" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 fclk CLK" *)
  input  wire        fclk,                // the AXI clock
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 fresetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input  wire        fresetn,
  output wire [3:0]  status
);
  // ---- constants (bit = 1: negative) ----
  localparam [27:0] TR_RE = 28'b1111000000101000101000110010;     // training symbol, subcarrier index u = k + 14 (k < 0), k + 13 (k > 0)
  localparam [27:0] TR_IM = 28'b1010100011100101100101101111;
  localparam [13:0] SC_RE = 14'b11110001101111;                   // Schmidl and Cox, even subcarriers e = (k + 14) / 2 (k < 0), k / 2 + 6 (k > 0)
  localparam [13:0] SC_IM = 14'b01011001101101;
  localparam [5:0]  ST_RE = 6'b110100;                            // short training field, k = -12, -8, -4, 4, 8, 12: index (k + 12) / 4 (k < 0), k / 4 + 2 (k > 0)
  localparam [5:0]  ST_IM = 6'b100001;
  localparam [3:0]  PL_RE = 4'b1100;                              // pilots k = -11, -4, 4, 11
  localparam [3:0]  PL_IM = 4'b1010;
  localparam [43:0] POLN  = 44'b10100010011110001010000110000010000001111111;     // pilot polarity of data symbol l (bit l)
  localparam signed [15:0] A_Q = 16'sd1073, A_SC = 16'sd1518, A_ST = 16'sd2319, L1 = 16'sd480, L3 = 16'sd1440;
  localparam [5:0] NSEG = STS ? 6'd47 : 6'd48;                    // slots of a frame
  localparam [5:0] FD   = STS ? 6'd2 : 6'd3;                      // the first data slot
  localparam [5:0] IDLE = NSEG - 6'd1;                            // the last slot is idle

  // ---- the buffer: 4 banks x 64 samples {q, i}; written in fclk, read in clk ----
  (* ram_style = "block" *) reg [31:0] ram [0:255];
  reg         wr_r;
  reg  [7:0]  wa_r;
  reg  [31:0] wd_r;
  always @(posedge fclk) if (wr_r) ram[wa_r] <= wd_r;
  reg  [7:0]  ra;
  reg  [31:0] ram_q;
  always @(posedge clk) ram_q <= ram[ra];

  // ======================= generator (fclk) =======================
  (* ASYNC_REG = "TRUE" *) reg [1:0] en_s; wire en_f = en_s[1];
  always @(posedge fclk) en_s <= {en_s[0], enable};
  (* ASYNC_REG = "TRUE" *) reg [1:0] fr_s; reg fr_p;                                      // free_tog of the player, synchronised
  reg        free_tog;
  reg        rdy_tog;
  wire       free_ev = fr_s[1] ^ fr_p;

  localparam [2:0] S_IDLE = 3'd0, S_NIB = 3'd1, S_START = 3'd2, S_LOAD = 3'd3, S_WAIT = 3'd4, S_COPY = 3'd5, S_DONE = 3'd6;
  reg  [2:0]  st;
  reg  [5:0]  slot;
  reg  [1:0]  bank;
  reg  [2:0]  credit, credit_n;
  reg  [6:0]  c;
  reg  [14:0] lfsr;
  reg  [3:0]  nib [0:23];
  reg         f_start, f_valid;
  reg  signed [15:0] f_re, f_im;
  wire        f_done, f_busy, f_ovf;
  wire signed [19:0] rd_re, rd_im;
  ofdm_fft u_fft (.clk(fclk), .start(f_start), .in_valid(f_valid), .in_re(f_re), .in_im(f_im), .busy(f_busy), .done(f_done), .ovf(f_ovf), .rd_addr(c[5:0]), .rd_re(rd_re), .rd_im(rd_im));

  function [14:0] lfsr4(input [14:0] s);
    reg [14:0] t; integer k;
    begin t = s; for (k = 0; k < 4; k = k + 1) t = {t[13:0], t[14] ^ t[13]}; lfsr4 = t; end
  endfunction
  function [3:0] ref4(input [14:0] s);
    reg [14:0] t; reg [3:0] b; integer k;
    begin t = s; for (k = 0; k < 4; k = k + 1) begin b[3 - k] = t[14]; t = {t[13:0], t[14] ^ t[13]}; end ref4 = b; end
  endfunction
  function signed [15:0] lev(input [1:0] ix);
    lev = (ix == 2'd0) ? -L3 : (ix == 2'd1) ? -L1 : (ix == 2'd2) ? L3 : L1;
  endfunction
  function signed [15:0] sat16(input signed [20:0] v);
    sat16 = (v > 21'sd32767) ? 16'sd32767 : (v < -21'sd32767) ? -16'sd32767 : v[15:0];
  endfunction

  // the value of bin c (the subcarrier k = c, or c - 64) of the slot, conjugated (the IFFT is made with the forward FFT)
  integer kk, uu, dd, ee, pj, sj, ll;
  reg isused, ispil, iseven, isst4;
  reg signed [15:0] vr, vi;
  reg [3:0] nb;
  wire is_pre  = (slot == 6'd0);
  wire is_trn  = STS ? (slot == 6'd1) : (slot == 6'd1 || slot == 6'd2);
  wire is_data = (slot >= FD) && (slot < FD + 6'd44);
  always @* begin
    kk = (c[5:0] < 6'd32) ? c[5:0] : (c[5:0] - 64);
    isused = (kk >= 1 && kk <= 14) || (kk <= -1 && kk >= -14);
    uu = (kk < 0) ? (kk + 14) : (kk + 13);
    ispil = (kk == -11) || (kk == -4) || (kk == 4) || (kk == 11);
    pj = (kk == -11) ? 0 : (kk == -4) ? 1 : (kk == 4) ? 2 : 3;
    dd = uu - ((kk < -11) ? 0 : (kk < -4) ? 1 : (kk < 4) ? 2 : (kk < 11) ? 3 : 4);
    iseven = isused && ((kk % 2) == 0);
    ee = (kk < 0) ? ((kk + 14) / 2) : (kk / 2 + 6);
    isst4 = (kk == -12) || (kk == -8) || (kk == -4) || (kk == 4) || (kk == 8) || (kk == 12);
    sj = (kk < 0) ? ((kk + 12) / 4) : (kk / 4 + 2);
    ll = slot - FD;
    nb = nib[(dd < 0 || dd > 23) ? 0 : dd];
    vr = 16'sd0; vi = 16'sd0;
    if (is_pre) begin
      if (STS) begin if (isst4) begin vr = ST_RE[sj] ? -A_ST : A_ST; vi = ST_IM[sj] ? -A_ST : A_ST; end end
      else     begin if (iseven) begin vr = SC_RE[ee] ? -A_SC : A_SC; vi = SC_IM[ee] ? -A_SC : A_SC; end end
    end else if (is_trn) begin
      if (isused) begin vr = TR_RE[uu] ? -A_Q : A_Q; vi = TR_IM[uu] ? -A_Q : A_Q; end
    end else if (is_data) begin
      if (ispil) begin vr = (PL_RE[pj] ^ POLN[ll]) ? -A_Q : A_Q; vi = (PL_IM[pj] ^ POLN[ll]) ? -A_Q : A_Q; end
      else if (isused) begin vr = lev(nb[3:2]); vi = lev(nb[1:0]); end
    end
  end

  wire signed [20:0] wq = -{rd_im[19], rd_im};
  wire signed [20:0] wi_ = {rd_re[19], rd_re};

  always @(posedge fclk) begin
    f_start <= 1'b0; wr_r <= 1'b0;
    fr_s <= {fr_s[0], free_tog};
    if (!fresetn || !en_f) begin
      st <= S_IDLE; slot <= 6'd0; bank <= 2'd0; credit <= 3'd4; c <= 7'd0; lfsr <= 15'h7FFF; rdy_tog <= 1'b0; fr_p <= fr_s[1]; f_valid <= 1'b0;
    end else begin
      fr_p <= fr_s[1];
      credit_n = credit + (free_ev ? 3'd1 : 3'd0);
      case (st)
        S_IDLE: if (credit != 3'd0) begin                                      // a bank is free: make the next slot
                  credit_n = credit_n - 3'd1; c <= 7'd0;
                  st <= (slot == IDLE) ? S_DONE : is_data ? S_NIB : S_START;   // the idle slot needs no samples
                end
        S_NIB: begin                                                           // 24 PRBS nibbles in the order of the data subcarriers
                  nib[c[4:0]] <= ref4(lfsr); lfsr <= lfsr4(lfsr);
                  if (c == 7'd23) begin c <= 7'd0; st <= S_START; end else c <= c + 7'd1;
                end
        S_START: begin f_start <= 1'b1; c <= 7'd0; st <= S_LOAD; end
        S_LOAD: begin
                  f_valid <= 1'b1; f_re <= vr; f_im <= -vi;
                  if (c == 7'd63) begin c <= 7'd0; st <= S_WAIT; end else c <= c + 7'd1;
                end
        S_WAIT: begin f_valid <= 1'b0; if (f_done) begin c <= 7'd0; st <= S_COPY; end end
        S_COPY: begin                                                          // 64 samples: x = conj(FFT(conj X))
                  wr_r <= 1'b1; wa_r <= {bank, c[5:0]}; wd_r <= {sat16(wq), sat16(wi_)};
                  if (c == 7'd63) begin c <= 7'd0; st <= S_DONE; end else c <= c + 7'd1;
                end
        S_DONE: begin
                  rdy_tog <= ~rdy_tog; bank <= bank + 2'd1;
                  slot <= (slot == IDLE) ? 6'd0 : slot + 6'd1;
                  if (slot == IDLE) lfsr <= 15'h7FFF;
                  st <= S_IDLE;
                end
        default: st <= S_IDLE;
      endcase
      credit <= credit_n;
    end
  end
  reg f_ovf_s; always @(posedge fclk) if (!en_f) f_ovf_s <= 1'b0; else if (f_ovf && st != S_IDLE) f_ovf_s <= 1'b1;

  // ======================= player (clk) =======================
  (* ASYNC_REG = "TRUE" *) reg [1:0] rd_s; reg rd_p;
  wire       rdy_ev = rd_s[1] ^ rd_p;
  reg  [2:0] avail, avail_n;
  reg  [7:0] cnt;                                                           // sample of the slot whose address is `ra`
  reg  [5:0] pslot;
  reg        playing, rv, ever, underrun;
  reg  [1:0] bank_p;
  reg signed [15:0] s_i, s_q;
  wire signed [31:0] pi_ = s_i * $signed({1'b0, amp[14:0]});
  wire signed [31:0] pq_ = s_q * $signed({1'b0, amp[14:0]});
  wire signed [31:0] hi_ = pi_ >>> 15, hq_ = pq_ >>> 15;
  // length and read pattern of a slot (the sample n of the slot comes from sample addr_of(n) of the 64 in its bank)
  function [7:0] len_of(input [5:0] sl);
    len_of = STS ? ((sl == 6'd0) ? 8'd128 : (sl == 6'd1) ? 8'd160 : (sl == 6'd46) ? 8'd32 : 8'd80) : 8'd80;
  endfunction
  function [5:0] addr_of(input [5:0] sl, input [7:0] n);
    reg [7:0] m;
    begin
      if (STS && sl == 6'd0) addr_of = n[5:0];                                              // 64 twice
      else if (STS && sl == 6'd1) begin m = n - 8'd32; addr_of = (n < 8'd32) ? (6'd32 + n[4:0]) : m[5:0]; end    // the last 32, then 64 twice
      else begin m = n - 8'd16; addr_of = (n < 8'd16) ? (6'd48 + n[3:0]) : m[5:0]; end             // the last 16, then the 64
    end
  endfunction
  function is_idle_slot(input [5:0] sl);
    is_idle_slot = (sl == IDLE);
  endfunction
  wire [5:0] nslot = (pslot == IDLE) ? 6'd0 : pslot + 6'd1;
  always @(posedge clk) begin
    rd_s <= {rd_s[0], rdy_tog};
    if (!resetn || !enable) begin
      playing <= 1'b0; bank_p <= 2'd0; cnt <= 8'd0; pslot <= 6'd0; avail <= 3'd0; free_tog <= 1'b0; rv <= 1'b0; ra <= 8'd0; ever <= 1'b0; underrun <= 1'b0;
      rd_p <= rd_s[1]; s_i <= 16'sd0; s_q <= 16'sd0; dac_i <= 16'd0; dac_q <= 16'd0;
    end else begin
      rd_p <= rd_s[1];
      avail_n = avail + (rdy_ev ? 3'd1 : 3'd0);
      if (ce) begin
        s_i <= rv ? ram_q[15:0] : 16'sd0; s_q <= rv ? ram_q[31:16] : 16'sd0;
        dac_i <= (hi_ > 32'sd32767) ? 16'sd32767 : (hi_ < -32'sd32767) ? -16'sd32767 : hi_[15:0];
        dac_q <= (hq_ > 32'sd32767) ? 16'sd32767 : (hq_ < -32'sd32767) ? -16'sd32767 : hq_[15:0];
        if (!playing) begin
          if (avail_n != 3'd0) begin
            playing <= 1'b1; ever <= 1'b1; cnt <= 8'd0; ra <= {bank_p, addr_of(pslot, 8'd0)}; rv <= !is_idle_slot(pslot); avail_n = avail_n - 3'd1;
          end else rv <= 1'b0;
        end else if (cnt == len_of(pslot) - 8'd1) begin                                    // the slot is over: free its bank, go on with the next
          free_tog <= ~free_tog; bank_p <= bank_p + 2'd1; pslot <= nslot;
          if (avail_n != 3'd0) begin
            cnt <= 8'd0; ra <= {bank_p + 2'd1, addr_of(nslot, 8'd0)}; rv <= !is_idle_slot(nslot); avail_n = avail_n - 3'd1;
          end else begin playing <= 1'b0; rv <= 1'b0; underrun <= 1'b1; end
        end else begin
          cnt <= cnt + 8'd1; ra <= {bank_p, addr_of(pslot, cnt + 8'd1)}; rv <= !is_idle_slot(pslot);
        end
      end
      avail <= avail_n;
    end
  end
  assign status = {1'b0, f_ovf_s, underrun, playing};
endmodule
