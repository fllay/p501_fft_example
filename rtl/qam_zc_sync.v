// Zadoff-Chu frame synchroniser of the 16-QAM receiver (PLAN_QAM16.md section 2 (2)). Bit-exact model: tutorial/qam16/qam_zc_fixed.py (sync(), carrier_from_word()).
//
//   per symbol (pulse go: mi, mq = the engine's mi2, mq2 after the AGC, before the derotation; sym_idx = n; one symbol is 104 clock cycles, this block needs about 80):
//     a = max + min/2 of the symbol -> ring RAMs; E = sum of a over the last 63 symbols (running sum)
//     63 taps, one complex multiply-accumulate per clock: Cr + j Ci = sum x[n-62+k] q[k], q = conj(ZC) Q14 (qam_zc_rom); A = taps 0..30, S = taps 0..31, C = all; D = C - S
//     M = max(|Cr|,|Ci|) + min/2;  candidate(THR) = E > 0 and M >= 64 THR E;   peak at q = n - 1: M(q) >= M(q-1) and M(q) > M(n)
//     tracker: SEARCH: a THR_L peak at q > search_from: near the last THR_S peak + 967 (+-TOL) -> lock (event 1), else a THR_S candidate becomes the last peak
//              LOCKED: the first strict maximum of M among the THR_L candidates in ee-W..ee+W (ee = ref + 967): frame event (2) at n = ee+W, a miss (e = ee, miss = 1) if none; more than MISSMAX misses: lost event (3)
//     carrier (at a lock, sequenced in qam_zc_carrier, about 80 clocks): w = frequency, th0 = phase of the first payload symbol, turns x 2^32
//   The events are held in ev_*: ev_pend until the engine acknowledges (ev_ack). `late` counts symbols that arrived while the previous one was still being processed.
`timescale 1ns/1ps
module qam_zc_sync (
  input  wire        aclk,
  input  wire        run,
  input  wire        go,
  input  wire signed [15:0] mi, mq,
  input  wire [31:0] sym_idx,
  input  wire [7:0]  r_thr_s, r_thr_l,
  input  wire [31:0] r_tol, r_window, r_missmax,
  output reg         ev_pend,
  output reg  [1:0]  ev_kind,                  // 1 lock, 2 frame, 3 lost
  output reg  [31:0] ev_e, ev_known,
  output reg         ev_miss,
  output reg  signed [31:0] ev_w,
  output reg  [31:0] ev_th0,
  input  wire        ev_ack,
  output wire        locked,
  output reg  [31:0] n_peak, n_lock, n_hit, n_miss, n_lost, late, ev_over,
  output reg  signed [39:0] snap_cr, snap_ci,
  output reg  [23:0] snap_e,
  output reg  [41:0] snap_m
);
  localparam [31:0] FRAME = 32'd967;
  localparam [3:0] S_IDLE = 4'd0, S_E0 = 4'd1, S_E1 = 4'd2, S_E2 = 4'd3, S_MAC = 4'd4, S_DRAIN = 4'd5, S_MET1 = 4'd6, S_MET2 = 4'd7, S_CAND = 4'd8, S_TRK = 4'd9;
  reg [3:0]  st;
  reg signed [15:0] xr, xi;
  reg [31:0] n;
  reg        state_locked;                    // 0 SEARCH, 1 LOCKED
  assign locked = state_locked;

  // ---------------- rings: x (32 bit) and its magnitude a (17 bit) ----------------
  reg [31:0] ring [0:63];
  reg [16:0] mring [0:63];
  reg [5:0]  ra, ra_m;
  reg [31:0] rd_ring;
  reg [16:0] rd_m;
  always @(posedge aclk) begin
    rd_ring <= ring[ra];
    rd_m <= mring[ra_m];
  end

  function [16:0] amag16(input signed [15:0] r, input signed [15:0] i);
    reg [15:0] a, b, mx, mn;
    begin
      a = r[15] ? -r : r; b = i[15] ? -i : i;
      mx = (a > b) ? a : b; mn = (a > b) ? b : a;
      amag16 = {1'b0, mx} + {2'b0, mn[15:1]};
    end
  endfunction
  function [40:0] amag40(input signed [39:0] r, input signed [39:0] i);
    reg [39:0] a, b, mx, mn;
    begin
      a = r[39] ? -r : r; b = i[39] ? -i : i;
      mx = (a > b) ? a : b; mn = (a > b) ? b : a;
      amag40 = {1'b0, mx} + {2'b0, mn[39:1]};
    end
  endfunction
  wire [16:0] an = amag16(xr, xi);

  // ---------------- the energy ----------------
  reg [16:0] old_a;
  reg [23:0] e_sum;

  // ---------------- the multiply-accumulate pipeline ----------------
  wire signed [15:0] qr, qi;
  reg  [5:0] rom_a;
  qam_zc_rom u_rom (.clk(aclk), .addr(rom_a), .qr(qr), .qi(qi));
  reg  [5:0] kcnt;
  reg        v1, v2, v3, v4;
  reg  [5:0] k1, k2, k3, k4;
  reg signed [31:0] p1, p2, p3, p4;
  reg signed [32:0] tre, tim;
  reg signed [39:0] accr, acci, a_r, a_i, s_r, s_i, c_r, c_i;
  wire signed [39:0] accr_n = accr + tre, acci_n = acci + tim;
  wire signed [15:0] xr_d = rd_ring[15:0], xi_d = rd_ring[31:16];
  reg  [2:0] dcnt;
  always @(posedge aclk) begin
    v2 <= v1; k2 <= k1;
    p1 <= xr_d * qr; p2 <= xi_d * qi; p3 <= xr_d * qi; p4 <= xi_d * qr; v3 <= v2; k3 <= k2;
    tre <= p1 - p2; tim <= p3 + p4; v4 <= v3; k4 <= k3;
    if (st == S_E2) begin accr <= 40'sd0; acci <= 40'sd0; end
    else if (v4) begin
      accr <= accr_n; acci <= acci_n;
      if (k4 == 6'd30) begin a_r <= accr_n; a_i <= acci_n; end
      if (k4 == 6'd31) begin s_r <= accr_n; s_i <= acci_n; end
      if (k4 == 6'd62) begin c_r <= accr_n; c_i <= acci_n; end
    end
  end

  // ---------------- metric ----------------
  reg signed [41:0] m_cur;
  reg signed [39:0] d_r, d_i;
  reg        cs, cl;
  reg [40:0] mx_m;
  reg [37:0] thr_es, thr_el;
  reg signed [41:0] m_p1, m_p2;
  reg        cs_p1, cl_p1;
  reg signed [39:0] ar_p1, ai_p1, dr_p1, di_p1;
  reg [31:0] idx_p1;
  reg [23:0] e_p1;
  reg signed [39:0] cr_p1, ci_p1;
  wire [40:0] amc = amag40(c_r, c_i);
  wire full = (n >= 32'd62);

  // ---------------- tracker ----------------
  reg        lastv;
  reg [31:0] lastp, search_from, ref_idx, ee, best_idx, miss_run;
  reg        have;
  reg signed [41:0] best_m;
  wire signed [33:0] dq = $signed({2'b00, idx_p1}) - $signed({2'b00, lastp}) - 34'sd967;
  wire        near = lastv && (dq >= -$signed({2'b00, r_tol})) && (dq <= $signed({2'b00, r_tol}));
  wire        pk = (n >= 32'd2) && (m_p1 >= m_p2) && (m_p1 > m_cur);
  wire        pk_l = pk && cl_p1 && (idx_p1 > search_from);
  wire signed [33:0] lo_w = $signed({2'b00, ee}) - $signed({2'b00, r_window});
  wire signed [33:0] hi_w = $signed({2'b00, ee}) + $signed({2'b00, r_window});
  wire signed [33:0] n_s = $signed({2'b00, n});
  wire        in_win = (n_s >= lo_w) && (n_s <= hi_w);
  wire        at_end = (n_s == hi_w);
  wire        take = in_win && cl && (!have || (m_cur > best_m));
  wire        have_n = have || take;
  wire [31:0] best_n = take ? n : best_idx;

  // ---------------- carrier sequencer ----------------
  reg        c_start;
  reg signed [39:0] c_ar, c_ai, c_dr, c_di;
  reg [31:0] c_e, c_known;
  wire       c_done;
  wire signed [31:0] c_w;
  wire [31:0] c_th0;
  qam_zc_carrier u_car (.clk(aclk), .start(c_start), .ar(c_ar), .ai(c_ai), .dr(c_dr), .di(c_di), .done(c_done), .w(c_w), .th0(c_th0));

  always @(posedge aclk) begin
    c_start <= 1'b0;
    if (ev_ack) ev_pend <= 1'b0;
    if (!run) begin
      st <= S_IDLE; state_locked <= 1'b0; lastv <= 1'b0; lastp <= 32'd0; search_from <= 32'd0; ref_idx <= 32'd0; ee <= 32'd0; best_idx <= 32'd0; miss_run <= 32'd0; have <= 1'b0; best_m <= 42'sd0;
      m_p1 <= -42'sd1; m_p2 <= -42'sd1; cs_p1 <= 1'b0; cl_p1 <= 1'b0; idx_p1 <= 32'd0; e_sum <= 24'd0; ev_pend <= 1'b0; ev_kind <= 2'd0; ev_e <= 32'd0; ev_known <= 32'd0; ev_miss <= 1'b0; ev_w <= 32'sd0; ev_th0 <= 32'd0;
      n_peak <= 32'd0; n_lock <= 32'd0; n_hit <= 32'd0; n_miss <= 32'd0; n_lost <= 32'd0; late <= 32'd0; ev_over <= 32'd0; kcnt <= 6'd0; v1 <= 1'b0; dcnt <= 3'd0;
      snap_cr <= 40'sd0; snap_ci <= 40'sd0; snap_e <= 24'd0; snap_m <= 42'd0; ar_p1 <= 40'sd0; ai_p1 <= 40'sd0; dr_p1 <= 40'sd0; di_p1 <= 40'sd0; e_p1 <= 24'd0; cr_p1 <= 40'sd0; ci_p1 <= 40'sd0;
    end else begin
      if (go && st != S_IDLE) late <= late + 32'd1;
      v1 <= 1'b0;
      if (c_done) begin
        if (ev_pend && !ev_ack) ev_over <= ev_over + 32'd1;
        ev_pend <= 1'b1; ev_kind <= 2'd1; ev_e <= c_e; ev_known <= c_known; ev_miss <= 1'b0; ev_w <= c_w; ev_th0 <= c_th0;
      end
      case (st)
        S_IDLE: if (go) begin xr <= mi; xi <= mq; n <= sym_idx; st <= S_E0; end
        S_E0: begin                                   // write the symbol, read the magnitude that leaves the window (symbol n - 63 sits in slot n + 1)
                ring[n[5:0]] <= {xi, xr}; mring[n[5:0]] <= an; ra_m <= n[5:0] + 6'd1; st <= S_E1;
              end
        S_E1: st <= S_E2;
        S_E2: begin
                e_sum <= e_sum + {7'd0, an} - ((n >= 32'd63) ? {7'd0, rd_m} : 24'd0);
                kcnt <= 6'd0; st <= full ? S_MAC : S_MET1;
              end
        S_MAC: begin
                ra <= n[5:0] + 6'd2 + kcnt; rom_a <= kcnt; v1 <= 1'b1; k1 <= kcnt; kcnt <= kcnt + 6'd1;
                if (kcnt == 6'd62) begin st <= S_DRAIN; dcnt <= 3'd0; end
              end
        S_DRAIN: begin dcnt <= dcnt + 3'd1; if (dcnt == 3'd4) st <= S_MET1; end
        S_MET1: begin
                d_r <= c_r - s_r; d_i <= c_i - s_i; st <= S_MET2;
              end
        S_MET2: begin
                if (full) begin m_cur <= $signed({1'b0, amc}); thr_es <= r_thr_s * e_sum; thr_el <= r_thr_l * e_sum; end
                else begin m_cur <= -42'sd1; thr_es <= 38'd0; thr_el <= 38'd0; end
                st <= S_CAND;
              end
        S_CAND: begin
                cs <= full && (e_sum != 24'd0) && (m_cur >= $signed({4'b0000, thr_es, 6'b000000}));
                cl <= full && (e_sum != 24'd0) && (m_cur >= $signed({4'b0000, thr_el, 6'b000000}));
                st <= S_TRK;
              end
        S_TRK: begin
                if (!state_locked) begin
                  if (pk_l) begin
                    n_peak <= n_peak + 32'd1; snap_cr <= cr_p1; snap_ci <= ci_p1; snap_e <= e_p1; snap_m <= m_p1;
                    if (near) begin
                      state_locked <= 1'b1; ref_idx <= idx_p1; ee <= idx_p1 + FRAME; miss_run <= 32'd0; have <= 1'b0; n_lock <= n_lock + 32'd1;
                      c_start <= 1'b1; c_ar <= ar_p1; c_ai <= ai_p1; c_dr <= dr_p1; c_di <= di_p1; c_e <= idx_p1; c_known <= n;
                    end else if (cs_p1) begin lastp <= idx_p1; lastv <= 1'b1; end
                  end
                end else begin
                  have <= have_n; best_idx <= best_n; if (take) best_m <= m_cur;
                  if (at_end) begin
                    have <= 1'b0;
                    if (have_n) begin
                      ref_idx <= best_n; ee <= best_n + FRAME; miss_run <= 32'd0; n_hit <= n_hit + 32'd1;
                      if (ev_pend && !ev_ack) ev_over <= ev_over + 32'd1;
                      ev_pend <= 1'b1; ev_kind <= 2'd2; ev_e <= best_n; ev_known <= n; ev_miss <= 1'b0;
                    end else begin
                      n_miss <= n_miss + 32'd1; miss_run <= miss_run + 32'd1;
                      if (miss_run + 32'd1 > r_missmax) begin
                        state_locked <= 1'b0; lastv <= 1'b0; search_from <= n; n_lost <= n_lost + 32'd1;
                        if (ev_pend && !ev_ack) ev_over <= ev_over + 32'd1;
                        ev_pend <= 1'b1; ev_kind <= 2'd3; ev_e <= ee; ev_known <= n; ev_miss <= 1'b1;
                      end else begin
                        ref_idx <= ee; ee <= ee + FRAME;
                        if (ev_pend && !ev_ack) ev_over <= ev_over + 32'd1;
                        ev_pend <= 1'b1; ev_kind <= 2'd2; ev_e <= ee; ev_known <= n; ev_miss <= 1'b1;
                      end
                    end
                  end
                end
                // the history for the next symbol
                m_p2 <= m_p1; m_p1 <= m_cur; cs_p1 <= cs; cl_p1 <= cl; idx_p1 <= n; e_p1 <= e_sum;
                ar_p1 <= full ? a_r : 40'sd0; ai_p1 <= full ? a_i : 40'sd0; dr_p1 <= full ? d_r : 40'sd0; di_p1 <= full ? d_i : 40'sd0; cr_p1 <= full ? c_r : 40'sd0; ci_p1 <= full ? c_i : 40'sd0;
                st <= S_IDLE;
              end
        default: st <= S_IDLE;
      endcase
    end
  end
endmodule


// The carrier from the word at a lock: frequency w and the phase th0 of the first payload symbol (turns x 2^32) from the half sums A and D.
// qam_zc_fixed.carrier_from_word() is the bit-exact model: one common right shift to 18 bits, pr + j pi = D conj(A), w = atan2 / 32, then A e^{+j16w} + D e^{-j16w} with the 1024-entry table, th0 = atan2 + 32 w.
module qam_zc_carrier (
  input  wire        clk,
  input  wire        start,
  input  wire signed [39:0] ar, ai, dr, di,
  output reg         done,
  output reg  signed [31:0] w,
  output reg  [31:0] th0
);
  localparam [4:0] C_IDLE = 0, C_SH = 1, C_M1 = 2, C_M2 = 3, C_M3 = 4, C_CPRE = 5, C_CIT = 6, C_W = 7, C_T0 = 8, C_P2A = 9, C_P2B = 10, C_P2C = 11, C_P2D = 12, C_P3A = 13, C_P3B = 14, C_P3C = 15, C_P3D = 16, C_FIN = 17;
  reg [4:0]  cst;
  reg signed [39:0] a_r, a_i, d_r, d_i;
  reg [5:0]  sa;
  reg signed [17:0] sar, sai, sdr, sdi;
  reg signed [17:0] ma [0:3];
  reg signed [17:0] mb [0:3];
  reg signed [35:0] mp [0:3];
  // CORDIC
  reg signed [38:0] in_re, in_im;
  reg signed [27:0] cx, cy;
  reg [19:0] cang;
  reg [4:0]  cit;
  reg        second;
  reg [9:0]  tidx;
  wire signed [15:0] tc, ts;
  qpsk_rx_trig u_trig (.clk(clk), .a(tidx), .c(tc), .s(ts));
  reg signed [38:0] rr, ri;

  function [5:0] bitlen(input [39:0] v);
    integer i;
    begin bitlen = 6'd0; for (i = 0; i < 40; i = i + 1) if (v[i]) bitlen = i + 1; end
  endfunction
  function [39:0] absv(input signed [39:0] v); absv = v[39] ? -v : v; endfunction
  function [19:0] atab(input [4:0] i);
    case (i)
      5'd0: atab = 20'd131072; 5'd1: atab = 20'd77376; 5'd2: atab = 20'd40884; 5'd3: atab = 20'd20753; 5'd4: atab = 20'd10417; 5'd5: atab = 20'd5213;
      5'd6: atab = 20'd2607; 5'd7: atab = 20'd1304; 5'd8: atab = 20'd652; 5'd9: atab = 20'd326; 5'd10: atab = 20'd163; 5'd11: atab = 20'd81;
      5'd12: atab = 20'd41; 5'd13: atab = 20'd20; 5'd14: atab = 20'd10; 5'd15: atab = 20'd5; 5'd16: atab = 20'd3; default: atab = 20'd1;
    endcase
  endfunction
  wire signed [38:0] cmax_abs_re = in_re[38] ? -in_re : in_re, cmax_abs_im = in_im[38] ? -in_im : in_im;
  wire [5:0] bl_c = bitlen({1'b0, cmax_abs_re | cmax_abs_im});
  wire [5:0] sh_c = (bl_c > 6'd23) ? (bl_c - 6'd23) : 6'd0;
  wire signed [38:0] cre_s = in_re >>> sh_c, cim_s = in_im >>> sh_c;
  wire signed [27:0] cysh = cy >>> cit, cxsh = cx >>> cit;
  wire [39:0] orv = absv(ar) | absv(ai) | absv(dr) | absv(di);
  wire [5:0] bl_a = bitlen(orv);

  always @(posedge clk) begin
    done <= 1'b0;
    case (cst)
      C_IDLE: if (start) begin a_r <= ar; a_i <= ai; d_r <= dr; d_i <= di; sa <= (bl_a > 6'd17) ? (bl_a - 6'd17) : 6'd0; cst <= C_SH; second <= 1'b0; end
      C_SH: begin sar <= a_r >>> sa; sai <= a_i >>> sa; sdr <= d_r >>> sa; sdi <= d_i >>> sa; cst <= C_M1; end
      C_M1: begin ma[0] <= sdr; mb[0] <= sar; ma[1] <= sdi; mb[1] <= sai; ma[2] <= sdi; mb[2] <= sar; ma[3] <= sdr; mb[3] <= sai; cst <= C_M2; end
      C_M2: begin mp[0] <= ma[0] * mb[0]; mp[1] <= ma[1] * mb[1]; mp[2] <= ma[2] * mb[2]; mp[3] <= ma[3] * mb[3]; cst <= C_M3; end
      C_M3: begin in_re <= mp[0] + mp[1]; in_im <= mp[2] - mp[3]; cst <= C_CPRE; end                    // D conj(A)
      C_CPRE: begin
                if (cre_s < 0) begin cx <= -cre_s; cy <= -cim_s; cang <= 20'h80000; end
                else begin cx <= cre_s; cy <= cim_s; cang <= 20'd0; end
                cit <= 5'd0; cst <= C_CIT;
              end
      C_CIT: begin
                if (!cy[27]) begin cx <= cx + cysh; cy <= cy - cxsh; cang <= cang + atab(cit); end
                else         begin cx <= cx - cysh; cy <= cy + cxsh; cang <= cang - atab(cit); end
                cit <= cit + 5'd1;
                if (cit == 5'd17) cst <= second ? C_FIN : C_W;
              end
      C_W: begin w <= $signed({cang, 12'd0}) >>> 5; cst <= C_T0; end
      C_T0: begin tidx <= w[27:18]; cst <= C_P2A; end                                                    // e^{j 16 w}: the table address
      C_P2A: cst <= C_P2B;                                                                              // the table output is registered
      C_P2B: begin ma[0] <= sar; mb[0] <= tc; ma[1] <= sai; mb[1] <= ts; ma[2] <= sdr; mb[2] <= tc; ma[3] <= sdi; mb[3] <= ts; cst <= C_P2C; end
      C_P2C: begin mp[0] <= ma[0] * mb[0]; mp[1] <= ma[1] * mb[1]; mp[2] <= ma[2] * mb[2]; mp[3] <= ma[3] * mb[3]; cst <= C_P2D; end
      C_P2D: begin rr <= mp[0] - mp[1] + mp[2] + mp[3]; cst <= C_P3A; end                               // Re(A e^{+j} + D e^{-j})
      C_P3A: begin ma[0] <= sar; mb[0] <= ts; ma[1] <= sai; mb[1] <= tc; ma[2] <= sdi; mb[2] <= tc; ma[3] <= sdr; mb[3] <= ts; cst <= C_P3B; end
      C_P3B: begin mp[0] <= ma[0] * mb[0]; mp[1] <= ma[1] * mb[1]; mp[2] <= ma[2] * mb[2]; mp[3] <= ma[3] * mb[3]; cst <= C_P3C; end
      C_P3C: begin ri <= mp[0] + mp[1] + mp[2] - mp[3]; cst <= C_P3D; end                               // Im
      C_P3D: begin in_re <= rr; in_im <= ri; second <= 1'b1; cst <= C_CPRE; end
      C_FIN: begin th0 <= {cang, 12'd0} + {w[26:0], 5'd0}; done <= 1'b1; cst <= C_IDLE; end
      default: cst <= C_IDLE;
    endcase
  end
  initial cst = C_IDLE;
endmodule
