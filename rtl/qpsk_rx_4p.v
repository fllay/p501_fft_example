// QPSK receiver, chain 3: polyphase matched filter -> 4th-power frequency estimator -> Costas loop, with NO software in the loop (ID 0xDD520004).
// This is rtl/qpsk_rx.v (the receiver of chapter 4d: no FLL) plus the estimator qpsk_fe.v and its controller qpsk_fe_auto.v: the estimator looks at the symbols m after the polyphase filter, the timing loop and
// the AGC (before the Costas derotation) and accumulates exp(j 4 arg(m_n conj(m_n-1))) over a window of N symbols; a CORDIC takes the atan2 and the hardware writes the result into the Costas loop's frequency
// (OMEGA) at the next symbol. Once (FE_AUTO = 1): windows repeat until one passes the quality gate, that one loads OMEGA, then the Costas loop tracks alone. Continuous (FE_AUTO = 3): every window that passes loads OMEGA.
//   0x74 FE_CTRL: rising edge of bit 0 arms ONE manual window (for measurements)   0x78 FE_N window length in symbols (1 .. 65535, default 1024)   0x7C FE_STATUS (R): bit0 active, bit1 done
//   0x80 FE_CNT (R)   0x84 ACC_RE (R, signed)   0x88 ACC_IM (R, signed)   0x8C ACC_ABS (R, saturating at 2^31-1)   0x90 FE_FIRST (R) index of the first symbol of the window
//   0x94 FE_AUTO: bit 0 enable, bit 1 continuous (write 0, then 1 or 3)   0x98 FE_WEST (R) last frequency loaded (turns/symbol x 2^32, signed)   0x9C FE_NLOAD (R) loads done
//   0xA0 FE_QMIN (gate: q_min x 32767 x 1.6468; default 16000 = q 0.30)   0xA4 FE_NWIN (R) windows evaluated   0xA8 FE_WLAST (R) the last window's frequency, gate or not
// Model: tutorial/qpsk/p501_rx_4p/qpsk_fe_auto_fixed.py (bit-exact), on top of tutorial/qpsk/p501_rx/qpsk_rx_fixed.py.
//
// (the header of qpsk_rx.v follows)
// QPSK receiver for the differential QPSK signal of chapters 4a-4c (960 ksym/s, 4 samples per symbol, RRC 0.35, 3.84 MSPS), adjustable loops.
//
//   ADC samples (adc_clk) -> 256-entry dual-clock RAM + Gray-coded write counter
//   engine (aclk = the 100 MHz clock of the AXI-Lite registers), once per symbol (about 65 of the 104 clock cycles of a symbol):
//     44-tap MAC on arm k of 16: matched filter + derivative filter, I and Q      -> symbol-rate AGC -> timing error -> timing loop
//     -> derotation by the Costas NCO (1024-entry table) -> Costas error -> phase/frequency loop -> decision -> differential decoder -> 2 bits
//     -> self-synchronising PRBS-15 checker (counters) and a capture RAM of 1024 soft symbols
//
// tutorial/qpsk/p501_rx/qpsk_rx_fixed.py is the bit-exact integer model of this file; every width and shift below comes from it.
//
// Registers (32 bit, byte offsets):
//   0x00 ID (R) 0xDD520001     0x04 CTRL: bit0 run (0 resets the engine and the counters), bit1 capture arm (0 -> 1 arms)
//   0x08 TA  0x0C TB  timing loop proportional / integral gain      (gain x 2^24)
//   0x10 CA  0x14 CB  Costas loop proportional / integral gain      (gain_rad x 2^27 / 2 pi)
//   0x18 MU  AGC speed        0x1C REF  AGC reference |z| (16384 = 2.0)   0x20 G0  initial AGC gain (Q10)
//   0x24 W0  initial Costas frequency (turns/symbol x 2^32)         0x28 MAXR  limit of the timing rate (Q16 arms per symbol)
//   0x30 STATUS (R): bit0 running, bit1 capture done, bit2 overrun seen      0x34 SYMBOLS   0x38 BITS (checked)   0x3C MISMATCH (3 per isolated bit error)
//   0x40 OMEGA (R, Costas frequency, signed, turns/symbol x 2^32)   0x44 RATE (R, signed, Q16 arms per symbol)   0x48 GAIN (R)   0x4C WRCNT (R)   0x50 OVERRUNS (R)
//   0x1000 .. 0x1FFC: capture RAM (R), 1024 words {zq[15:0], zi[15:0]}
`timescale 1ns/1ps
module qpsk_rx_4p (
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axi, ASSOCIATED_RESET aresetn" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 aclk CLK" *)
  input  wire        aclk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input  wire        aresetn,

  input  wire [13:0] s_axi_awaddr,
  input  wire        s_axi_awvalid,
  output wire        s_axi_awready,
  input  wire [31:0] s_axi_wdata,
  input  wire [3:0]  s_axi_wstrb,
  input  wire        s_axi_wvalid,
  output wire        s_axi_wready,
  output reg  [1:0]  s_axi_bresp,
  output reg         s_axi_bvalid,
  input  wire        s_axi_bready,
  input  wire [13:0] s_axi_araddr,
  input  wire        s_axi_arvalid,
  output wire        s_axi_arready,
  output reg  [31:0] s_axi_rdata,
  output reg  [1:0]  s_axi_rresp,
  output reg         s_axi_rvalid,
  input  wire        s_axi_rready,

  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 adc_clk CLK" *)
  input  wire        adc_clk,                 // l_clk of axi_ad9361
  input  wire        adc_valid,               // adc_valid_i0
  input  wire [15:0] adc_i,
  input  wire [15:0] adc_q
);
  // ======================= registers =======================
  reg [31:0] r_ctrl, r_ta, r_tb, r_ca, r_cb, r_mu, r_ref, r_g0, r_w0, r_maxr;
  reg [31:0] r_fe_ctrl, r_fe_n, r_fe_auto, r_fe_qmin;
  wire do_write = s_axi_awvalid & s_axi_wvalid & ~s_axi_bvalid;
  assign s_axi_awready = do_write;
  assign s_axi_wready  = do_write;
  always @(posedge aclk) begin
    if (!aresetn) begin
      r_ctrl <= 32'd0; r_ta <= 32'd729017; r_tb <= 32'd16195; r_ca <= 32'd928214; r_cb <= 32'd20620;
      r_mu <= 32'd40; r_ref <= 32'd16384; r_g0 <= 32'd1024; r_w0 <= 32'd0; r_maxr <= 32'd52429; r_fe_ctrl <= 32'd0; r_fe_n <= 32'd1024; r_fe_auto <= 32'd0; r_fe_qmin <= 32'd16000;
      s_axi_bvalid <= 1'b0; s_axi_bresp <= 2'b00;
    end else begin
      if (do_write) begin
        case (s_axi_awaddr[7:2])
          6'h01: r_ctrl <= s_axi_wdata;
          6'h02: r_ta   <= s_axi_wdata;
          6'h03: r_tb   <= s_axi_wdata;
          6'h04: r_ca   <= s_axi_wdata;
          6'h05: r_cb   <= s_axi_wdata;
          6'h06: r_mu   <= s_axi_wdata;
          6'h07: r_ref  <= s_axi_wdata;
          6'h08: r_g0   <= s_axi_wdata;
          6'h09: r_w0   <= s_axi_wdata;
          6'h0A: r_maxr <= s_axi_wdata;
          6'h1D: r_fe_ctrl  <= s_axi_wdata;
          6'h1E: r_fe_n     <= s_axi_wdata;
          6'h25: r_fe_auto  <= s_axi_wdata;
          6'h28: r_fe_qmin  <= s_axi_wdata;
          default: ;
        endcase
        s_axi_bvalid <= 1'b1;
      end else if (s_axi_bvalid & s_axi_bready) s_axi_bvalid <= 1'b0;
    end
  end

  // ======================= sample RAM, adc_clk side =======================
  reg [31:0] sram [0:255];
  reg [31:0] wr_cnt = 32'd0;
  reg [31:0] wr_gray = 32'd0;
  always @(posedge adc_clk) begin
    if (adc_valid) begin
      sram[wr_cnt[7:0]] <= {adc_q, adc_i};
      wr_cnt <= wr_cnt + 32'd1;
    end
    wr_gray <= wr_cnt ^ (wr_cnt >> 1);
  end
  // Gray counter -> aclk (two flops), binary again
  (* ASYNC_REG = "TRUE" *) reg [31:0] g_s1 = 32'd0, g_s2 = 32'd0;
  always @(posedge aclk) begin g_s1 <= wr_gray; g_s2 <= g_s1; end
  function [31:0] gray2bin(input [31:0] gg);
    integer gi;
    begin
      gray2bin[31] = gg[31];
      for (gi = 30; gi >= 0; gi = gi - 1) gray2bin[gi] = gray2bin[gi + 1] ^ gg[gi];
    end
  endfunction
  wire [31:0] wr_sync = gray2bin(g_s2);

  // ======================= engine =======================
  localparam [4:0] ST_IDLE = 5'd0, ST_WAIT = 5'd1, ST_MAC = 5'd2, S0 = 5'd3, S1 = 5'd4, S2 = 5'd5, S3 = 5'd6, S4 = 5'd7, S5 = 5'd8, S6 = 5'd9, S7 = 5'd10, S8 = 5'd11, S9 = 5'd12;
  reg [4:0]  st;
  reg [31:0] base;
  reg [51:0] p;                                   // [51:20] sample index t, [19:16] arm, [15:0] fraction
  reg [6:0]  ic;
  reg signed [31:0] rate, omega;
  reg [31:0] theta;
  reg [16:0] g;
  reg [1:0]  prev;
  wire [31:0] t32 = p[51:20];
  wire [3:0]  arm = p[19:16];
  wire [31:0] diff = wr_sync - base - t32;
  wire        avail = (diff != 32'd0) && !diff[31];

  // memories and the MAC pipeline
  reg  [31:0] x_word;
  wire [7:0]  ram_raddr = base[7:0] + t32[7:0] - {1'b0, ic};
  always @(posedge aclk) x_word <= sram[ram_raddr];
  wire signed [15:0] cm, cd;
  qpsk_rx_rom u_rom (.clk(aclk), .addr({arm, ic[5:0]}), .cm(cm), .cd(cd));
  wire signed [15:0] xi = x_word[15:0], xq = x_word[31:16];
  reg v1, v2;
  reg signed [31:0] pmi, pmq, pdi, pdq;
  reg signed [39:0] a_mi, a_mq, a_di, a_dq;
  always @(posedge aclk) begin
    v1 <= (st == ST_MAC) && (ic < 7'd44);
    v2 <= v1;
    pmi <= xi * cm; pmq <= xq * cm; pdi <= xi * cd; pdq <= xq * cd;
    if (st != ST_MAC) begin a_mi <= 40'sd0; a_mq <= 40'sd0; a_di <= 40'sd0; a_dq <= 40'sd0; end
    else if (v2) begin a_mi <= a_mi + pmi; a_mq <= a_mq + pmq; a_di <= a_di + pdi; a_dq <= a_dq + pdq; end
  end

  // arithmetic helpers
  function signed [23:0] clip24(input signed [47:0] v);
    clip24 = (v > 48'sd8388607) ? 24'sd8388607 : (v < -48'sd8388608) ? -24'sd8388608 : v[23:0];
  endfunction
  function signed [15:0] clip16(input signed [47:0] v);
    clip16 = (v > 48'sd32767) ? 16'sd32767 : (v < -48'sd32768) ? -16'sd32768 : v[15:0];
  endfunction
  function signed [13:0] clip13(input signed [47:0] v);                  // +-8191
    clip13 = (v > 48'sd8191) ? 14'sd8191 : (v < -48'sd8191) ? -14'sd8191 : v[13:0];
  endfunction

  reg signed [23:0] mi_r, mq_r, di_r, dq_r;
  reg signed [15:0] mi2, mq2, di2, dq2;
  reg signed [13:0] e_t, e_c;
  reg signed [15:0] zi, zq;
  reg [16:0] a_est;
  wire signed [15:0] trig_c, trig_s;
  qpsk_rx_trig u_trig (.clk(aclk), .a(theta[31:22]), .c(trig_c), .s(trig_s));

  // PRBS checker and counters
  reg [14:0] prbs_sr;
  reg [4:0]  prbs_n;
  reg [31:0] n_sym, n_bits, n_mism, n_over;
  reg [1:0]  bits2;
  reg        sym_pulse;
  reg        run_q;
  wire       run = r_ctrl[0];
  reg        cap_arm_q, cap_active, cap_done;
  reg [10:0] cap_cnt;
  reg [31:0] cap_mem [0:1023];

  // ---- the frequency estimator: one pulse per symbol when mi2, mq2 are valid (state S2) ----
  reg  fe_arm_q;
  always @(posedge aclk) fe_arm_q <= r_fe_ctrl[0];
  wire fe_active, fe_done; wire [31:0] fe_cnt, fe_first, fe_abs; wire signed [31:0] fe_re, fe_im;
  wire fe_ld_pend; wire [31:0] fe_ld_w, fe_west, fe_nload, fe_nwin, fe_wlast; reg fe_ld_ack;
  qpsk_fe_auto u_fe (.aclk(aclk), .run(r_ctrl[0] & aresetn), .go(st == S2), .mi(mi2), .mq(mq2), .sym_idx(n_sym), .arm_man(r_fe_ctrl[0] & ~fe_arm_q), .r_n(r_fe_n), .r_auto(r_fe_auto), .r_qmin(r_fe_qmin),
                .active(fe_active), .done(fe_done), .cnt(fe_cnt), .first(fe_first), .acc_re(fe_re), .acc_im(fe_im), .acc_abs(fe_abs),
                .ld_pend(fe_ld_pend), .ld_w(fe_ld_w), .ld_ack(fe_ld_ack), .w_last(fe_wlast), .w_est(fe_west), .n_load(fe_nload), .n_win(fe_nwin));

  // decision logic for the current z
  wire        s_i = ~zi[15] & (zi != 16'sd0);         // z.real > 0
  wire        s_q = ~zq[15] & (zq != 16'sd0);
  wire [1:0]  pt  = ( s_i &  s_q) ? 2'd0 : (~s_i &  s_q) ? 2'd1 : (~s_i & ~s_q) ? 2'd2 : 2'd3;
  wire [1:0]  dd  = pt - prev;
  wire [1:0]  cc  = (dd == 2'd2) ? 2'd3 : (dd == 2'd3) ? 2'd2 : dd;       // [0,1,3,2]
  wire        b0  = cc[1], b1 = cc[0];
  wire        pred0 = prbs_sr[14] ^ prbs_sr[13];
  wire [14:0] sr1 = {prbs_sr[13:0], b0};
  wire        pred1 = sr1[14] ^ sr1[13];
  wire        pr0 = (prbs_n >= 5'd15), pr1 = (prbs_n >= 5'd14);
  wire [1:0]  mm  = {1'b0, (pr0 & (b0 != pred0))} + {1'b0, (pr1 & (b1 != pred1))};
  wire [1:0]  nch = {1'b0, pr0} + {1'b0, pr1};

  // intermediate products (combinational, registered where used)
  wire signed [41:0] mpi = mi_r * $signed({1'b0, g}), mpq = mq_r * $signed({1'b0, g}), dpi = di_r * $signed({1'b0, g}), dpq = dq_r * $signed({1'b0, g});
  wire signed [32:0] tp = mi2 * di2 + mq2 * dq2;
  wire signed [17:0] err_a = $signed({1'b0, r_ref[16:0]}) - $signed({1'b0, a_est});
  wire signed [34:0] mu_prod = $signed({1'b0, r_mu[15:0]}) * err_a;
  wire signed [46:0] tb_prod = $signed({1'b0, r_tb[30:0]}) * e_t;
  wire signed [46:0] ta_prod = $signed({1'b0, r_ta[30:0]}) * e_t;
  wire signed [46:0] ta_sh = ta_prod >>> 21;
  wire        [51:0] ta_ext = {{5{ta_sh[46]}}, ta_sh};
  wire signed [47:0] cb_prod = $signed({1'b0, r_cb[30:0]}) * e_c;
  wire signed [47:0] ca_prod = $signed({1'b0, r_ca[30:0]}) * e_c;
  wire signed [47:0] ca_sh = ca_prod >>> 8;
  wire signed [32:0] zi_full = mi2 * trig_c + mq2 * trig_s;
  wire signed [32:0] zq_full = mq2 * trig_c - mi2 * trig_s;
  wire signed [16:0] ai = (mi2[15] ? -{mi2[15], mi2} : {mi2[15], mi2}), aq = (mq2[15] ? -{mq2[15], mq2} : {mq2[15], mq2});
  wire [16:0] amax = (ai > aq) ? ai : aq, amin = (ai > aq) ? aq : ai;
  wire signed [47:0] g_new = $signed({1'b0, g}) + (mu_prod >>> 16);
  wire signed [47:0] rate_new_w = rate + ((tb_prod + 47'sd1048576) >>> 21);      // rounded: a plain shift floors, which is -0.5 LSB per symbol and runs a narrow timing loop's integrator into its limit
  wire signed [47:0] maxr_s = $signed({1'b0, r_maxr[30:0]});
  wire signed [47:0] ec_raw = (s_i ? $signed({{32{zq[15]}}, zq}) : -$signed({{32{zq[15]}}, zq})) - (s_q ? $signed({{32{zi[15]}}, zi}) : -$signed({{32{zi[15]}}, zi}));
  wire signed [47:0] omega_new_w = omega + (cb_prod >>> 8);

  always @(posedge aclk) begin
    run_q <= run; sym_pulse <= 1'b0; fe_ld_ack <= 1'b0;
    cap_arm_q <= r_ctrl[1];
    if (!aresetn || !run) begin
      st <= ST_IDLE; ic <= 7'd0;
      // p starts at (44 taps * 16 arms + arm 8) << 16
      p <= 52'd46661632; rate <= 32'sd0; omega <= $signed(r_w0); theta <= 32'd0;
      g <= r_g0[16:0]; prev <= 2'd0; prbs_sr <= 15'd0; prbs_n <= 5'd0;
      n_sym <= 32'd0; n_bits <= 32'd0; n_mism <= 32'd0; n_over <= 32'd0;
      cap_active <= 1'b0; cap_done <= 1'b0; cap_cnt <= 11'd0; base <= wr_sync;
    end else begin
      if (r_ctrl[1] & ~cap_arm_q) begin cap_active <= 1'b1; cap_done <= 1'b0; cap_cnt <= 11'd0; end
      case (st)
        ST_IDLE: st <= ST_WAIT;
        ST_WAIT: if (avail) begin
                   if (diff > 32'd200) n_over <= n_over + 32'd1;          // the engine is far behind the samples
                   st <= ST_MAC; ic <= 7'd0;
                 end
        ST_MAC: begin
                   ic <= ic + 7'd1;
                   if (ic == 7'd46) st <= S0;
                 end
        S0: begin
              mi_r <= clip24(a_mi >>> 11); mq_r <= clip24(a_mq >>> 11); di_r <= clip24(a_di >>> 11); dq_r <= clip24(a_dq >>> 11);
              st <= S1;
            end
        S1: begin
              mi2 <= clip16(mpi >>> 10); mq2 <= clip16(mpq >>> 10); di2 <= clip16(dpi >>> 10); dq2 <= clip16(dpq >>> 10);
              st <= S2;
            end
        S2: begin
              a_est <= amax + (amin >> 1);
              e_t   <= clip13(tp >>> 13);
              st <= S3;
            end
        S3: begin
              g <= (g_new < 48'sd16) ? 17'd16 : (g_new > 48'sd131071) ? 17'd131071 : g_new[16:0];
              rate <= (rate_new_w > maxr_s) ? maxr_s[31:0] : (rate_new_w < -maxr_s) ? -maxr_s[31:0] : rate_new_w[31:0];
              st <= S4;
            end
        S4: begin
              p <= p + 52'd4194304 + {{20{rate[31]}}, rate} + ta_ext;          // + (NF*SPS) << 16 arms
              st <= S5;
            end
        S5: begin
              zi <= clip16(zi_full >>> 15); zq <= clip16(zq_full >>> 15);
              st <= S6;
            end
        S6: begin
              e_c <= clip13(ec_raw);
              bits2 <= {b0, b1};
              prev <= pt;
              prbs_sr <= {sr1[13:0], b1};
              prbs_n <= (prbs_n >= 5'd13) ? 5'd15 : prbs_n + 5'd2;
              n_bits <= n_bits + nch; n_mism <= n_mism + mm;
              if (cap_active) begin
                cap_mem[cap_cnt[9:0]] <= {zq, zi};
                cap_cnt <= cap_cnt + 11'd1;
                if (cap_cnt == 11'd1023) begin cap_active <= 1'b0; cap_done <= 1'b1; end
              end
              st <= S7;
            end
        S7: begin
              omega <= fe_ld_pend ? $signed(fe_ld_w) : (omega_new_w > 48'sd2147483647) ? 32'sh7FFFFFFF : (omega_new_w < -48'sd2147483648) ? 32'sh80000000 : omega_new_w[31:0];   // the estimator's frequency replaces the update
              if (fe_ld_pend) fe_ld_ack <= 1'b1;
              st <= S8;
            end
        S8: begin
              theta <= theta + omega + ca_sh[31:0];
              st <= S9;
            end
        S9: begin
              n_sym <= n_sym + 32'd1; sym_pulse <= 1'b1;
              st <= ST_WAIT;
            end
        default: st <= ST_IDLE;
      endcase
    end
  end

  // ======================= AXI-Lite read =======================
  reg [31:0] cap_rd;
  reg [13:0] araddr_q;
  reg        ar_cap, ar_pending;
  wire [31:0] status = {29'd0, (n_over != 32'd0), cap_done, (st != ST_IDLE)};
  assign s_axi_arready = s_axi_arvalid & ~s_axi_rvalid & ~ar_pending;
  always @(posedge aclk) begin
    cap_rd <= cap_mem[s_axi_araddr[11:2]];
    if (!aresetn) begin s_axi_rvalid <= 1'b0; s_axi_rdata <= 32'd0; s_axi_rresp <= 2'b00; ar_pending <= 1'b0; ar_cap <= 1'b0; end
    else begin
      if (s_axi_arready) begin
        ar_cap <= s_axi_araddr[12];
        ar_pending <= 1'b1;
      end else if (ar_pending) begin
        ar_pending <= 1'b0; s_axi_rvalid <= 1'b1;
        if (ar_cap) s_axi_rdata <= cap_rd;
        else case (araddr_q[7:2])
          6'h00: s_axi_rdata <= 32'hDD520004;
          6'h01: s_axi_rdata <= r_ctrl;   6'h02: s_axi_rdata <= r_ta;   6'h03: s_axi_rdata <= r_tb;   6'h04: s_axi_rdata <= r_ca;   6'h05: s_axi_rdata <= r_cb;
          6'h06: s_axi_rdata <= r_mu;     6'h07: s_axi_rdata <= r_ref;  6'h08: s_axi_rdata <= r_g0;   6'h09: s_axi_rdata <= r_w0;   6'h0A: s_axi_rdata <= r_maxr;
          6'h0C: s_axi_rdata <= status;   6'h0D: s_axi_rdata <= n_sym;  6'h0E: s_axi_rdata <= n_bits; 6'h0F: s_axi_rdata <= n_mism;
          6'h10: s_axi_rdata <= omega;    6'h11: s_axi_rdata <= rate;   6'h12: s_axi_rdata <= {15'd0, g};  6'h13: s_axi_rdata <= wr_sync;  6'h14: s_axi_rdata <= n_over;
          6'h1D: s_axi_rdata <= r_fe_ctrl;   6'h1E: s_axi_rdata <= r_fe_n;   6'h1F: s_axi_rdata <= {30'd0, fe_done, fe_active};   6'h20: s_axi_rdata <= fe_cnt;
          6'h21: s_axi_rdata <= fe_re;       6'h22: s_axi_rdata <= fe_im;     6'h23: s_axi_rdata <= fe_abs;   6'h24: s_axi_rdata <= fe_first;
          6'h25: s_axi_rdata <= r_fe_auto;   6'h26: s_axi_rdata <= fe_west;   6'h27: s_axi_rdata <= fe_nload;   6'h28: s_axi_rdata <= r_fe_qmin;
          6'h29: s_axi_rdata <= fe_nwin;     6'h2A: s_axi_rdata <= fe_wlast;
          default: s_axi_rdata <= 32'd0;
        endcase
      end else if (s_axi_rvalid & s_axi_rready) s_axi_rvalid <= 1'b0;
    end
  end
  always @(posedge aclk) if (s_axi_arready) araddr_q <= s_axi_araddr;
endmodule
