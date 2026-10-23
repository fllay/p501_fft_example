// 16-QAM receiver with the Zadoff-Chu frame synchroniser (PLAN_QAM16.md; ID 0xDD520006). Bit-exact model: tutorial/qam16/qam16_rx_fixed.py (front16 + engine16) and qam_zc_fixed.py.
//
//   ADC samples (adc_clk, 3.84 MSPS) -> sample RAM -> engine (aclk, 100 MHz, once per symbol, about 70 of the 104 clock cycles):
//     44-tap polyphase matched + derivative filter -> power AGC (rounded) -> timing error / loop (acquisition gains for the first ACQ symbols) -> mi2, mq2
//       -> qam_zc_sync (the frame synchroniser, its own state machine) and a 16-deep delay line
//     symbol j = n - 10 from the delay line: position counter pos (CP 0-7, word 8-70, payload 71-966; set by the synchroniser's events) -> derotation by the NCO (1024-entry table)
//       -> 16-QAM slicer (levels +-1, +-3 x 4096) -> phase error: data Im(z conj s), pilot (weight), known word / CP symbols (aided) -> omega, theta
//       -> Gray decision, PRBS-15 symbol / bit error counters (the payload of every frame is the PRBS-15 restarted at its first symbol), EVM sums, capture RAM of 1024 soft symbols.
//   An event of the synchroniser with decision index `known` is applied at the engine step n = known + 2 (before the label of symbol j = n - 10).
//
// Registers (32 bit, byte offsets = 4 x index):
//   0x00 ID 0xDD520006   0x04 CTRL bit0 run (0 resets), bit1 capture arm (0 -> 1)
//   0x08 TA  0x0C TB  timing gains (narrow)   0x10 CA  0x14 CB  PLL gains (gain_rad x 2^40 / (2 pi 640))   0x18 MU  AGC speed (narrow)   0x1C PREF  AGC reference (R^2 >> 8 = 655391)   0x20 G0  initial gain (Q10)
//   0x28 MAXR  timing rate limit   0x2C TAA  0x30 TBA  acquisition timing gains   0x34 MUA  acquisition AGC speed   0x38 ACQ  symbols in the acquisition mode (0 = never)
//   0x3C PCFG bit0 aided (the known CP / word symbols drive the PLL), bits 11:8 pilot error multiplier (3 pw: 3, 9, 15)
//   0x40 SY_THR  thr_s [7:0] (154 = 0.60), thr_l [15:8] (115 = 0.45)   0x44 SY_TOL (3)   0x48 SY_WIN (4)   0x4C SY_MISSMAX (3)
//   0x50 STATUS (R) bit0 running, bit1 capture done, bit2 overrun seen, bit3 synchroniser locked, bit4 run active   0x54 SYMBOLS   0x58 FRAMES (complete payloads)   0x5C SYM_ERR   0x60 BIT_ERR   0x64 SYM_CNT   0x68 BAD_FRAMES
//   0x6C EVM_ERR_LO  0x70 EVM_ERR_HI (the last complete frame: sum of |z - s|^2, 48 bit)   0x74 EVM_REF (sum of |s|^2 / 4096^2)   0x78 FRAME_ERR (symbol errors of the last frame)
//   0x7C GAIN  0x80 RATE  0x84 OMEGA  0x88 WRCNT  0x8C OVERRUNS  0x90 N_PEAK  0x94 N_LOCK  0x98 N_HIT  0x9C N_MISS  0xA0 N_LOST  0xA4 SY_LATE  0xA8 EV_OVER  0xAC EV_LATE  0xB0 LOCK_W  0xB4 POS
//   0xB8 NSW (index 0x2E, R/W): frames after a lock before the acquisition mode ends (4; 0 = only the ACQ symbol count); a lost lock starts it again
//   0x1000 .. 0x1FFC: capture RAM (R), 1024 words {zq[15:0], zi[15:0]}
`timescale 1ns/1ps
module qam16_rx (
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
  input  wire        adc_clk,
  input  wire        adc_valid,
  input  wire [15:0] adc_i,
  input  wire [15:0] adc_q
);
  localparam [31:0] D_DELAY = 32'd10;
  // ======================= registers =======================
  reg [31:0] r_ctrl, r_ta, r_tb, r_ca, r_cb, r_mu, r_pref, r_g0, r_maxr, r_taa, r_tba, r_mua, r_acq, r_pcfg, r_thr, r_tol, r_win, r_missmax, r_nsw;
  wire do_write = s_axi_awvalid & s_axi_wvalid & ~s_axi_bvalid;
  assign s_axi_awready = do_write;
  assign s_axi_wready  = do_write;
  always @(posedge aclk) begin
    if (!aresetn) begin
      r_ctrl <= 32'd0; r_ta <= 32'd729017; r_tb <= 32'd16195; r_ca <= 32'd15000000; r_cb <= 32'd425000; r_mu <= 32'd136; r_pref <= 32'd655391; r_g0 <= 32'd1024; r_maxr <= 32'd52429;
      r_taa <= 32'd0; r_tba <= 32'd0; r_mua <= 32'd544; r_acq <= 32'd0; r_pcfg <= 32'h0000_0901; r_thr <= 32'h0000_739A; r_tol <= 32'd3; r_win <= 32'd4; r_missmax <= 32'd3; r_nsw <= 32'd4;
      s_axi_bvalid <= 1'b0; s_axi_bresp <= 2'b00;
    end else begin
      if (do_write) begin
        case (s_axi_awaddr[7:2])
          6'h01: r_ctrl <= s_axi_wdata;   6'h02: r_ta <= s_axi_wdata;     6'h03: r_tb <= s_axi_wdata;     6'h04: r_ca <= s_axi_wdata;     6'h05: r_cb <= s_axi_wdata;
          6'h06: r_mu <= s_axi_wdata;     6'h07: r_pref <= s_axi_wdata;   6'h08: r_g0 <= s_axi_wdata;     6'h0A: r_maxr <= s_axi_wdata;   6'h0B: r_taa <= s_axi_wdata;
          6'h0C: r_tba <= s_axi_wdata;    6'h0D: r_mua <= s_axi_wdata;    6'h0E: r_acq <= s_axi_wdata;    6'h0F: r_pcfg <= s_axi_wdata;   6'h10: r_thr <= s_axi_wdata;
          6'h11: r_tol <= s_axi_wdata;    6'h12: r_win <= s_axi_wdata;    6'h13: r_missmax <= s_axi_wdata;    6'h2E: r_nsw <= s_axi_wdata;
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
  localparam [4:0] ST_IDLE = 5'd0, ST_WAIT = 5'd1, ST_MAC = 5'd2, S0 = 5'd3, S1 = 5'd4, S2 = 5'd5, S3 = 5'd6, S4 = 5'd7, S5 = 5'd8, S6 = 5'd9, S7 = 5'd10, S8 = 5'd11, S9 = 5'd12, S10 = 5'd13, S11 = 5'd14;
  reg [4:0]  st;
  reg [31:0] base;
  reg [51:0] p;
  reg [6:0]  ic;
  reg signed [31:0] rate, omega;
  reg [31:0] theta;
  reg [16:0] g;
  reg [31:0] n_sym;
  wire [31:0] t32 = p[51:20];
  wire [3:0]  arm = p[19:16];
  wire [31:0] diff = wr_sync - base - t32;
  wire        avail = (diff != 32'd0) && !diff[31];

  // MAC (unchanged from qpsk_rx.v)
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

  function signed [23:0] clip24(input signed [47:0] v);
    clip24 = (v > 48'sd8388607) ? 24'sd8388607 : (v < -48'sd8388608) ? -24'sd8388608 : v[23:0];
  endfunction
  function signed [15:0] clip16(input signed [47:0] v);
    clip16 = (v > 48'sd32767) ? 16'sd32767 : (v < -48'sd32768) ? -16'sd32768 : v[15:0];
  endfunction
  function signed [13:0] clip13(input signed [47:0] v);
    clip13 = (v > 48'sd8191) ? 14'sd8191 : (v < -48'sd8191) ? -14'sd8191 : v[13:0];
  endfunction

  reg signed [23:0] mi_r, mq_r, di_r, dq_r;
  reg signed [15:0] mi2, mq2, di2, dq2;
  reg signed [13:0] e_t;
  reg [31:0] pw;                                  // mi2^2 + mq2^2 (33 bit in the model, < 2^32 here: 2 x 32768^2 = 2^31)
  // ---- AGC and timing multipliers
  reg         acq_auto;                          // acquisition mode until NSW frames have followed a lock, again after a lost lock
  reg [31:0]  hit_cnt;
  wire        acq = (n_sym < r_acq) | acq_auto;
  wire [31:0] mu_eff = acq ? r_mua : r_mu, ta_eff = acq ? r_taa : r_ta, tb_eff = acq ? r_tba : r_tb;
  wire signed [41:0] mpi = mi_r * $signed({1'b0, g}), mpq = mq_r * $signed({1'b0, g}), dpi = di_r * $signed({1'b0, g}), dpq = dq_r * $signed({1'b0, g});
  wire signed [32:0] tp = mi2 * di2 + mq2 * dq2;
  wire signed [32:0] pw_s = $signed({1'b0, pw});
  wire signed [47:0] e_p = $signed({1'b0, r_pref}) - (pw_s >>> 8);
  wire signed [47:0] mu_prod = $signed({1'b0, mu_eff[15:0]}) * e_p;
  wire signed [47:0] g_new = $signed({1'b0, g}) + ((mu_prod + 48'sd8388608) >>> 24);
  wire signed [46:0] tb_prod = $signed({1'b0, tb_eff[30:0]}) * e_t;
  wire signed [46:0] ta_prod = $signed({1'b0, ta_eff[30:0]}) * e_t;
  wire signed [46:0] ta_sh = ta_prod >>> 21;
  wire        [51:0] ta_ext = {{5{ta_sh[46]}}, ta_sh};
  wire signed [47:0] rate_new_w = rate + ((tb_prod + 47'sd1048576) >>> 21);
  wire signed [47:0] maxr_s = $signed({1'b0, r_maxr[30:0]});

  // ---- delay line
  reg [31:0] dline [0:15];
  reg [3:0]  ra_d;
  reg [31:0] rd_d;
  always @(posedge aclk) rd_d <= dline[ra_d];
  wire signed [15:0] mi_d = rd_d[15:0], mq_d = rd_d[31:16];

  // ---- the synchroniser
  wire        ev_pend; wire [1:0] ev_kind; wire [31:0] ev_e, ev_known; wire ev_miss; wire signed [31:0] ev_w; wire [31:0] ev_th0; reg ev_ack;
  wire        sy_locked; wire [31:0] sy_peak, sy_lock, sy_hit, sy_miss, sy_lost, sy_late, sy_evover;
  wire signed [39:0] sy_cr, sy_ci; wire [23:0] sy_e; wire [41:0] sy_m;
  qam_zc_sync u_sy (.aclk(aclk), .run(r_ctrl[0] & aresetn), .go(st == S2), .mi(mi2), .mq(mq2), .sym_idx(n_sym), .r_thr_s(r_thr[7:0]), .r_thr_l(r_thr[15:8]), .r_tol(r_tol), .r_window(r_win), .r_missmax(r_missmax),
                    .ev_pend(ev_pend), .ev_kind(ev_kind), .ev_e(ev_e), .ev_known(ev_known), .ev_miss(ev_miss), .ev_w(ev_w), .ev_th0(ev_th0), .ev_ack(ev_ack), .locked(sy_locked),
                    .n_peak(sy_peak), .n_lock(sy_lock), .n_hit(sy_hit), .n_miss(sy_miss), .n_lost(sy_lost), .late(sy_late), .ev_over(sy_evover), .snap_cr(sy_cr), .snap_ci(sy_ci), .snap_e(sy_e), .snap_m(sy_m));

  // ---- labels and the NCO
  reg        run_act, wait_lock, fr_on;
  reg [9:0]  pos;
  reg [31:0] lock_e, lock_w, lock_th, ev_late, w_last;
  wire signed [31:0] j_idx = n_sym - D_DELAY;
  wire        proc = run_act && !wait_lock;
  reg [1:0]  kind;                                 // 0 none, 1 data, 2 pilot, 3 known (CP, word)
  reg [5:0]  arg6;                                 // known symbol: index of ZC (0..62)
  reg [3:0]  pblk;                                 // pilot: block 0..13
  wire [9:0] opos = pos - 10'd71;                  // offset in the payload; o % 64 = opos[5:0], o / 64 = opos[9:6]
  wire signed [15:0] trig_c, trig_s;
  qpsk_rx_trig u_trig (.clk(aclk), .a(theta[31:22]), .c(trig_c), .s(trig_s));
  wire signed [15:0] zcr_q, zci_q;
  qam_zc_rom u_zcr (.clk(aclk), .addr(arg6), .qr(zcr_q), .qi(zci_q));          // conj(ZC[k]) = (zcr_q, zci_q): the known symbol ZC[k] is (zcr_q, -zci_q)
  reg signed [15:0] zi, zq;
  wire signed [32:0] zi_full = mi_d * trig_c + mq_d * trig_s;
  wire signed [32:0] zq_full = mq_d * trig_c - mi_d * trig_s;

  // ---- slicer, phase error
  wire [1:0] li = (zi < -16'sd8192) ? 2'd0 : (zi < 16'sd0) ? 2'd1 : (zi < 16'sd8192) ? 2'd2 : 2'd3;       // position of the level -3 -1 1 3
  wire [1:0] lq = (zq < -16'sd8192) ? 2'd0 : (zq < 16'sd0) ? 2'd1 : (zq < 16'sd8192) ? 2'd2 : 2'd3;
  function signed [3:0] lval(input [1:0] l);
    lval = (l == 2'd0) ? -4'sd3 : (l == 2'd1) ? -4'sd1 : (l == 2'd2) ? 4'sd1 : 4'sd3;
  endfunction
  wire signed [3:0] si = lval(li), sq = lval(lq);
  wire [3:0] ix = {li[1], li[1] ^ li[0], lq[1], lq[1] ^ lq[0]};                                           // Gray: position 0 1 2 3 -> 00 01 11 10
  wire signed [47:0] e_data_raw = zq * si - zi * sq;
  wire signed [47:0] e_data = (e_data_raw + 48'sd32) >>> 6;
  function pilot_neg(input [3:0] b);                       // PILOTS = 1 1 -1 1 -1 -1 1 1 1 -1 -1 1 -1 1
    case (b) 4'd2, 4'd4, 4'd5, 4'd9, 4'd10, 4'd12: pilot_neg = 1'b1; default: pilot_neg = 1'b0; endcase
  endfunction
  wire signed [5:0] pm = {2'b00, r_pcfg[11:8]};
  wire signed [47:0] zq_pm = zq * pm;
  wire signed [47:0] e_pil = ((pilot_neg(pblk) ? -zq_pm : zq_pm) + 48'sd32) >>> 6;
  wire signed [47:0] kn_a = zq * zcr_q;                   // Im(z conj ZC) = zq ZCr - zi ZCi with ZCr = zcr_q, ZCi = -zci_q
  wire signed [47:0] kn_b = zi * zci_q;
  wire signed [47:0] kn_e = (((kn_a + kn_b) * 48'sd13) + 48'sd2097152) >>> 22;
  reg  signed [13:0] e_c;
  reg  [3:0] ix_r;
  reg  [3:0] rix;
  reg  [34:0] esq;                                          // |z - s|^2 of the data symbol
  reg  [7:0]  rsq;                                          // si^2 + sq^2
  wire signed [47:0] cb_prod = $signed({1'b0, r_cb[30:0]}) * e_c;
  wire signed [47:0] ca_prod = $signed({1'b0, r_ca[30:0]}) * e_c;
  wire signed [47:0] omega_new_w = omega + ((cb_prod + 48'sd128) >>> 8);
  wire signed [31:0] omega_n = (omega_new_w > 48'sd2147483647) ? 32'sh7FFFFFFF : (omega_new_w < -48'sd2147483648) ? 32'sh80000000 : omega_new_w[31:0];
  wire signed [47:0] ca_sh = (ca_prod + 48'sd128) >>> 8;
  wire signed [16:0] dI = zi - $signed({si, 12'd0}), dQ = zq - $signed({sq, 12'd0});

  // ---- PRBS-15 reference, counters
  reg [14:0] lfsr;
  function [14:0] lfsr4(input [14:0] s);
    reg [14:0] t; integer k;
    begin t = s; for (k = 0; k < 4; k = k + 1) t = {t[13:0], t[14] ^ t[13]}; lfsr4 = t; end
  endfunction
  function [3:0] ref4(input [14:0] s);
    reg [14:0] t; reg [3:0] b; integer k;
    begin t = s; for (k = 0; k < 4; k = k + 1) begin b[3 - k] = t[14]; t = {t[13:0], t[14] ^ t[13]}; end ref4 = b; end
  endfunction
  wire [14:0] lfsr_cur = (pos == 10'd71) ? 15'h7FFF : lfsr;
  reg [31:0] sym_err, bit_err, sym_cnt, frames, bad_frames, fr_n, fr_err, fr_bit, fr_last_err, n_over, fr_r2, r2_last;
  reg [47:0] fr_e2, e2_last;
  wire [3:0] xorix = ix_r ^ rix;
  wire [2:0] pop = xorix[0] + xorix[1] + xorix[2] + xorix[3];

  reg        sym_pulse;
  wire       run = r_ctrl[0];
  reg        cap_arm_q, cap_active, cap_done;
  reg [10:0] cap_cnt;
  reg [31:0] cap_mem [0:1023];
  wire       ev_due = ev_pend && ((ev_known + 32'd2) <= n_sym);

  always @(posedge aclk) begin
    sym_pulse <= 1'b0; ev_ack <= 1'b0;
    cap_arm_q <= r_ctrl[1];
    if (!aresetn || !run) begin
      st <= ST_IDLE; ic <= 7'd0;
      p <= 52'd46661632; rate <= 32'sd0; omega <= 32'sd0; theta <= 32'd0;
      g <= r_g0[16:0]; n_sym <= 32'd0; run_act <= 1'b0; wait_lock <= 1'b0; fr_on <= 1'b0; pos <= 10'd0; kind <= 2'd0; arg6 <= 6'd0; pblk <= 4'd0;
      lock_e <= 32'd0; lock_w <= 32'd0; lock_th <= 32'd0; ev_late <= 32'd0; w_last <= 32'd0; lfsr <= 15'h7FFF; acq_auto <= (r_nsw != 32'd0); hit_cnt <= 32'd0;
      sym_err <= 32'd0; bit_err <= 32'd0; sym_cnt <= 32'd0; frames <= 32'd0; bad_frames <= 32'd0; fr_n <= 32'd0; fr_err <= 32'd0; fr_bit <= 32'd0; fr_last_err <= 32'd0; n_over <= 32'd0;
      fr_e2 <= 48'd0; e2_last <= 48'd0; fr_r2 <= 32'd0; r2_last <= 32'd0; e_c <= 14'sd0; esq <= 35'd0; rsq <= 8'd0; ix_r <= 4'd0; rix <= 4'd0;
      cap_active <= 1'b0; cap_done <= 1'b0; cap_cnt <= 11'd0; base <= wr_sync;
    end else begin
      if (r_ctrl[1] & ~cap_arm_q) begin cap_active <= 1'b1; cap_done <= 1'b0; cap_cnt <= 11'd0; end
      case (st)
        ST_IDLE: st <= ST_WAIT;
        ST_WAIT: if (avail) begin
                   if (diff > 32'd200) n_over <= n_over + 32'd1;
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
        S2: begin                                          // mi2, mq2 valid: go to the synchroniser (st == S2), and into the delay line
              pw <= mi2 * mi2 + mq2 * mq2;
              e_t <= clip13(tp >>> 13);
              dline[n_sym[3:0]] <= {mq2, mi2};
              st <= S3;
            end
        S3: begin
              g <= (g_new < 48'sd16) ? 17'd16 : (g_new > 48'sd131071) ? 17'd131071 : g_new[16:0];
              rate <= (rate_new_w > maxr_s) ? maxr_s[31:0] : (rate_new_w < -maxr_s) ? -maxr_s[31:0] : rate_new_w[31:0];
              st <= S4;
            end
        S4: begin
              p <= p + 52'd4194304 + {{20{rate[31]}}, rate} + ta_ext;
              st <= S5;
            end
        S5: begin                                          // events of the synchroniser, release of a lock; the read address of the delay line
              ra_d <= n_sym[3:0] + 4'd6;                   // the slot of symbol n - 10
              if (ev_due) begin
                ev_ack <= 1'b1;
                if ((ev_known + 32'd2) != n_sym) ev_late <= ev_late + 32'd1;
                case (ev_kind)
                  2'd1: begin run_act <= 1'b1; wait_lock <= 1'b1; lock_e <= ev_e; lock_w <= ev_w; lock_th <= ev_th0; fr_on <= 1'b0; w_last <= ev_w; hit_cnt <= 32'd0; end
                  2'd2: begin
                          if (run_act && !wait_lock) pos <= 10'd70 + (j_idx - ev_e);
                          if (!ev_miss) begin hit_cnt <= hit_cnt + 32'd1; if (r_nsw != 32'd0 && (hit_cnt + 32'd1) >= r_nsw) acq_auto <= 1'b0; end
                        end
                  2'd3: begin run_act <= 1'b0; wait_lock <= 1'b0; fr_on <= 1'b0; hit_cnt <= 32'd0; acq_auto <= (r_nsw != 32'd0); end
                  default: ;
                endcase
              end
              if (run_act && wait_lock && (j_idx == lock_e + 32'd1)) begin
                theta <= lock_th; omega <= lock_w; pos <= 10'd71; wait_lock <= 1'b0;
              end
              st <= S6;
            end
        S6: begin                                          // the label of the symbol (pos is final); the ZC reference address
              if (pos >= 10'd71) begin
                kind <= (opos[5:0] == 6'd63) ? 2'd2 : 2'd1;
                pblk <= opos[9:6];
              end else kind <= r_pcfg[0] ? 2'd3 : 2'd0;
              arg6 <= (pos < 10'd8) ? (6'd55 + pos[5:0]) : (pos[5:0] - 6'd8);
              st <= S7;
            end
        S7: st <= S8;                                      // the table output (theta) and the ROM output (arg6) are registered
        S8: begin                                          // derotation
              zi <= clip16(zi_full >>> 15); zq <= clip16(zq_full >>> 15);
              st <= S9;
            end
        S9: begin                                          // slicer and phase error
              case (kind)
                2'd1: e_c <= clip13(e_data);
                2'd2: e_c <= clip13(e_pil);
                2'd3: e_c <= clip13(kn_e);
                default: e_c <= 14'sd0;
              endcase
              ix_r <= ix; rix <= ref4(lfsr_cur);
              esq <= dI * dI + dQ * dQ; rsq <= si * si + sq * sq;
              st <= S10;
            end
        S10: begin                                         // PLL update, counters
              if (proc && kind != 2'd0) begin
                omega <= omega_n;
                theta <= theta + omega_n + ca_sh[31:0];
              end else if (proc) theta <= theta + omega;
              if (proc && pos == 10'd71) fr_on <= 1'b1;
              if (proc && kind == 2'd1) begin
                lfsr <= lfsr4(lfsr_cur);
                fr_n <= ((pos == 10'd71) ? 32'd0 : fr_n) + 32'd1;
                fr_err <= ((pos == 10'd71) ? 32'd0 : fr_err) + ((ix_r != rix) ? 32'd1 : 32'd0);
                fr_bit <= ((pos == 10'd71) ? 32'd0 : fr_bit) + {29'd0, pop};
                fr_e2 <= ((pos == 10'd71) ? 48'd0 : fr_e2) + {13'd0, esq};
                fr_r2 <= ((pos == 10'd71) ? 32'd0 : fr_r2) + {24'd0, rsq};
                if (cap_active) begin
                  cap_mem[cap_cnt[9:0]] <= {zq, zi};
                  cap_cnt <= cap_cnt + 11'd1;
                  if (cap_cnt == 11'd1023) begin cap_active <= 1'b0; cap_done <= 1'b1; end
                end
              end
              st <= S11;
            end
        S11: begin
              if (proc) begin
                if (pos == 10'd966) begin
                  pos <= 10'd0; fr_on <= 1'b0;
                  if (fr_on && fr_n == 32'd882) begin
                    frames <= frames + 32'd1; sym_err <= sym_err + fr_err; sym_cnt <= sym_cnt + 32'd882; bit_err <= bit_err + fr_bit;
                    bad_frames <= bad_frames + ((fr_err * 32'd5 > 32'd882) ? 32'd1 : 32'd0);
                    fr_last_err <= fr_err; e2_last <= fr_e2; r2_last <= fr_r2;
                  end
                end else pos <= pos + 10'd1;
              end
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
  wire [31:0] status = {27'd0, run_act, sy_locked, (n_over != 32'd0), cap_done, (st != ST_IDLE)};
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
          6'h00: s_axi_rdata <= 32'hDD520006;
          6'h01: s_axi_rdata <= r_ctrl;   6'h02: s_axi_rdata <= r_ta;   6'h03: s_axi_rdata <= r_tb;   6'h04: s_axi_rdata <= r_ca;   6'h05: s_axi_rdata <= r_cb;
          6'h06: s_axi_rdata <= r_mu;     6'h07: s_axi_rdata <= r_pref; 6'h08: s_axi_rdata <= r_g0;   6'h0A: s_axi_rdata <= r_maxr; 6'h0B: s_axi_rdata <= r_taa;
          6'h0C: s_axi_rdata <= r_tba;    6'h0D: s_axi_rdata <= r_mua;  6'h0E: s_axi_rdata <= r_acq;  6'h0F: s_axi_rdata <= r_pcfg; 6'h10: s_axi_rdata <= r_thr;
          6'h11: s_axi_rdata <= r_tol;    6'h12: s_axi_rdata <= r_win;  6'h13: s_axi_rdata <= r_missmax;
          6'h14: s_axi_rdata <= status;   6'h15: s_axi_rdata <= n_sym;  6'h16: s_axi_rdata <= frames; 6'h17: s_axi_rdata <= sym_err; 6'h18: s_axi_rdata <= bit_err; 6'h19: s_axi_rdata <= sym_cnt; 6'h1A: s_axi_rdata <= bad_frames;
          6'h1B: s_axi_rdata <= e2_last[31:0]; 6'h1C: s_axi_rdata <= {16'd0, e2_last[47:32]}; 6'h1D: s_axi_rdata <= r2_last; 6'h1E: s_axi_rdata <= fr_last_err;
          6'h1F: s_axi_rdata <= {15'd0, g}; 6'h20: s_axi_rdata <= rate; 6'h21: s_axi_rdata <= omega; 6'h22: s_axi_rdata <= wr_sync; 6'h23: s_axi_rdata <= n_over;
          6'h24: s_axi_rdata <= sy_peak;  6'h25: s_axi_rdata <= sy_lock; 6'h26: s_axi_rdata <= sy_hit;  6'h27: s_axi_rdata <= sy_miss; 6'h28: s_axi_rdata <= sy_lost; 6'h29: s_axi_rdata <= sy_late;
          6'h2A: s_axi_rdata <= sy_evover; 6'h2B: s_axi_rdata <= ev_late; 6'h2C: s_axi_rdata <= w_last; 6'h2D: s_axi_rdata <= {22'd0, pos}; 6'h2E: s_axi_rdata <= r_nsw;
          default: s_axi_rdata <= 32'd0;
        endcase
      end else if (s_axi_rvalid & s_axi_rready) s_axi_rvalid <= 1'b0;
    end
  end
  always @(posedge aclk) if (s_axi_arready) araddr_q <= s_axi_araddr;
endmodule
