// Schmidl-and-Cox detector of the OFDM receiver (PLAN_OFDM.md section 12; bit-exact model: tutorial/ofdm/ofdm_fixed.py, detect_info and metric).
//
// One ADC sample per s_valid, at least 26 clocks apart (3.84 MS/s at 100 MHz): the processing takes 9 clocks, 25 in the collecting mode (`late` if a sample comes sooner).
//   c[n] = x[n+32] conj x[n];  S = sum of 32 c;  E = sum of 32 |x[n+32]|^2 (running sums over rings of 32);  the window of the sample m is n = m - 63
//   S' = S >> 8, E' = E >> 8, S2 = S'r^2 + S'i^2, E2 = E'^2;  cond = (E' >= EMIN) and (256 S2 >= THR E2)
//   the first window with cond is n0; the 72 windows n0 .. n0 + 71 are stored: mq = min((S2s << 10) / E2s, 2047) (S2s, E2s: both shifted right by max(0, bitlen(E2) - 20)), S and E
//   plateau: pk = max mq (first maximum at pkidx), t90 = pk 29 >> 5, first / last = the first and the last stored window with mq >= t90;  s0 = n0 + ((first + last + 1) >> 1) - 8 (start of the S&C symbol)
//   coarse carrier: CORDIC (ofdm_cordic.v) of the sum of S over first .. last, turns x 2^20, x 128 = w_c (turns x 2^32 per sample)
//   gain G (Q8) = min(65535, 256 TARGET / max(isqrt(E[pkidx] >> 5), 1))
// found pulses once; run = 0 re-arms. w_* are taps for the testbench (one pulse per valid window).
`timescale 1ns/1ps
module ofdm_detect (
  input  wire        clk,
  input  wire        run,
  input  wire        s_valid,
  input  wire signed [11:0] xi, xq,
  input  wire [7:0]  r_thr,
  input  wire [7:0]  r_emin,
  input  wire [15:0] r_target,
  output reg         found,
  output reg  [31:0] o_n0,
  output reg  [6:0]  o_first, o_last, o_pkidx,
  output reg  signed [31:0] o_s0,
  output reg  signed [31:0] o_wc,
  output reg  [15:0] o_gain,
  output reg  [28:0] o_epk,
  output reg  signed [39:0] o_sr, o_si,
  output reg  [10:0] o_pk,
  output reg         late,
  output wire        ready,                  // the processing of the last sample is finished (the next sample may come)
  output reg         w_pulse,
  output reg  [31:0] w_n,
  output reg         w_cond,
  output reg  signed [29:0] w_sr, w_si,
  output reg  [28:0] w_e
);
  // ---- rings and running sums
  reg signed [11:0] ring_r [0:31], ring_i [0:31];
  reg signed [24:0] cring_r [0:31], cring_i [0:31];
  reg [23:0]        ering [0:31];
  reg [4:0]  wp;
  reg [31:0] cnt;
  reg signed [29:0] sum_r, sum_i;
  reg [28:0] sum_e;
  // ---- stored windows
  reg [10:0] mq_ram [0:71];
  reg signed [29:0] sr_ram [0:71], si_ram [0:71];
  reg [28:0] e_ram [0:71];

  localparam [4:0] P_IDLE = 0, P_PROD = 1, P_ACC = 2, P_SH = 3, P_SQ = 4, P_SUM = 5, P_CMP = 6, P_COND = 7, P_DEC = 8, P_NORM = 9, P_DIV0 = 10, P_DIV = 11, P_STORE = 12, P_DIVI = 24,
                   A_PK = 13, A_T = 14, A_FL = 15, A_SUM = 16, A_CORDIC = 17, A_CW = 18, A_SQ = 19, A_DIV0 = 20, A_DIV = 21, A_FIN = 22, S_DONE = 23;
  reg [4:0]  st;
  reg signed [11:0] x_r, x_i, o_r, o_i;
  reg signed [24:0] oc_r, oc_i; reg [23:0] oe;
  reg signed [24:0] p0, p1, p2, p3; reg [23:0] pe0, pe1;
  reg signed [24:0] c_re, c_im; reg [23:0] e_new;
  reg signed [21:0] sp_r, sp_i; reg [20:0] ep;
  reg [41:0] s2a, s2b, e2, s2; reg [49:0] lhs, rhs; reg gate_e, cond;
  reg [5:0]  nsh; reg [41:0] s2s, e2s;
  reg [31:0] drem; reg [3:0] dit; reg [10:0] dq;
  reg collecting;
  reg [6:0]  cidx;
  reg [31:0] n0;
  wire [31:0] m_now = cnt;
  function [5:0] bitlen42(input [41:0] v);
    integer i;
    begin bitlen42 = 6'd0; for (i = 0; i < 42; i = i + 1) if (v[i]) bitlen42 = i + 1; end
  endfunction
  // ---- plateau analysis
  reg [10:0] pk, t90; reg [6:0] ai_, first, last, pkidx; reg have_first;
  reg signed [39:0] acc_r, acc_i;
  wire [15:0] pk29 = pk * 5'd29;
  reg cord_start; wire cord_done; wire [19:0] cord_ang;
  ofdm_cordic u_cordic (.clk(clk), .start(cord_start), .re(acc_r), .im(acc_i), .done(cord_done), .ang(cord_ang));
  reg [23:0] sq_num, sq_res, sq_bit; reg [3:0] sq_it; reg [11:0] isq;
  reg [24:0] gd_rem; reg [23:0] gd_num; reg [11:0] gd_den; reg [4:0] gd_it; reg [23:0] gd_q;
  wire [11:0] isq_c = (isq == 0) ? 12'd1 : isq;

  assign ready = (st == P_IDLE) && run;
  initial begin st = P_IDLE; cnt = 0; wp = 0; collecting = 0; late = 0; sum_r = 0; sum_i = 0; sum_e = 0; end
  always @(posedge clk) begin
    found <= 1'b0; w_pulse <= 1'b0; cord_start <= 1'b0;
    if (!run) begin
      st <= P_IDLE; cnt <= 0; wp <= 0; sum_r <= 0; sum_i <= 0; sum_e <= 0; collecting <= 0; late <= 1'b0;
    end else begin
      if (s_valid && st != P_IDLE && st < A_PK) late <= 1'b1;
      case (st)
        P_IDLE: if (s_valid) begin
                  x_r <= xi; x_i <= xq;
                  o_r <= (cnt >= 32) ? ring_r[wp] : 12'sd0; o_i <= (cnt >= 32) ? ring_i[wp] : 12'sd0;
                  oc_r <= (cnt >= 64) ? cring_r[wp] : 25'sd0; oc_i <= (cnt >= 64) ? cring_i[wp] : 25'sd0; oe <= (cnt >= 64) ? ering[wp] : 24'd0;
                  st <= P_PROD;
                end
        P_PROD: begin
                  p0 <= x_r * o_r; p1 <= x_i * o_i; p2 <= x_i * o_r; p3 <= x_r * o_i; pe0 <= x_r * x_r; pe1 <= x_i * x_i;
                  ring_r[wp] <= x_r; ring_i[wp] <= x_i; st <= P_ACC;
                end
        P_ACC:  begin
                  c_re = p0 + p1; c_im = p2 - p3; e_new = (cnt >= 32) ? (pe0 + pe1) : 24'd0;
                  cring_r[wp] <= c_re; cring_i[wp] <= c_im; ering[wp] <= e_new;
                  sum_r <= sum_r + c_re - oc_r; sum_i <= sum_i + c_im - oc_i; sum_e <= sum_e + e_new - oe;
                  st <= P_SH;
                end
        P_SH:   begin sp_r <= sum_r >>> 8; sp_i <= sum_i >>> 8; ep <= sum_e >> 8; st <= P_SQ; end
        P_SQ:   begin s2a <= sp_r * sp_r; s2b <= sp_i * sp_i; e2 <= ep * ep; st <= P_SUM; end
        P_SUM:  begin s2 <= s2a + s2b; st <= P_CMP; end
        P_CMP:  begin lhs <= {s2, 8'd0}; rhs <= r_thr * e2; gate_e <= (ep >= {13'd0, r_emin}); st <= P_COND; end
        P_COND: begin cond <= gate_e && (lhs >= rhs); st <= P_DEC; end
        P_DEC:  begin
                  w_cond <= cond; w_sr <= sum_r; w_si <= sum_i; w_e <= sum_e; w_n <= m_now - 32'd63;
                  wp <= wp + 5'd1; cnt <= cnt + 32'd1;
                  if (m_now >= 32'd63) begin
                    w_pulse <= 1'b1;
                    if (!collecting && cond) begin collecting <= 1'b1; cidx <= 7'd0; n0 <= m_now - 32'd63; st <= P_NORM; end
                    else if (collecting) st <= P_NORM;
                    else st <= P_IDLE;
                  end else st <= P_IDLE;
                end
        P_NORM: begin nsh <= (bitlen42(e2) > 6'd20) ? (bitlen42(e2) - 6'd20) : 6'd0; st <= P_DIV0; end
        P_DIV0: begin s2s <= s2 >> nsh; e2s <= e2 >> nsh; dit <= 4'd10; dq <= 11'd0; st <= P_DIV; end
        P_DIV:  begin
                  // the quotient floor((S2s << 10) / E2s) in 11 bits, clipped to 2047 (E2s = 0 gives 0): the clip test first, then 11 restoring steps
                  drem <= {s2s[20:0], 10'd0};
                  if (e2s == 0) begin dq <= 11'd0; st <= P_STORE; end
                  else if ({s2s, 10'd0} >= {e2s, 11'd0}) begin dq <= 11'd2047; st <= P_STORE; end
                  else st <= P_DIVI;
                end
        P_DIVI: begin
                  if (drem >= ({12'd0, e2s[19:0]} << dit)) begin drem <= drem - ({12'd0, e2s[19:0]} << dit); dq[dit] <= 1'b1; end
                  if (dit == 4'd0) st <= P_STORE; else dit <= dit - 4'd1;
                end
        P_STORE:begin
                  mq_ram[cidx] <= dq; sr_ram[cidx] <= w_sr; si_ram[cidx] <= w_si; e_ram[cidx] <= w_e;
                  if (cidx == 7'd71) begin pk <= 11'd0; pkidx <= 7'd0; ai_ <= 7'd0; st <= A_PK; end
                  else begin cidx <= cidx + 7'd1; st <= P_IDLE; end
                end
        A_PK:   begin
                  if (mq_ram[ai_] > pk) begin pk <= mq_ram[ai_]; pkidx <= ai_; end
                  if (ai_ == 7'd71) st <= A_T; else ai_ <= ai_ + 7'd1;
                end
        A_T:    begin t90 <= pk29[15:5]; ai_ <= 7'd0; have_first <= 1'b0; st <= A_FL; end
        A_FL:   begin
                  if (mq_ram[ai_] >= t90) begin if (!have_first) begin first <= ai_; have_first <= 1'b1; end last <= ai_; end
                  if (ai_ == 7'd71) begin st <= A_SUM; end else ai_ <= ai_ + 7'd1;
                  if (ai_ == 7'd71) begin ai_ <= 7'd0; acc_r <= 40'sd0; acc_i <= 40'sd0; end
                end
        A_SUM:  begin
                  if (ai_ >= first && ai_ <= last) begin acc_r <= acc_r + sr_ram[ai_]; acc_i <= acc_i + si_ram[ai_]; end
                  if (ai_ == last) begin st <= A_CORDIC; cord_start <= 1'b1; end   // one clock later the sums are final: start after the last add (acc settles next edge)
                  else ai_ <= ai_ + 7'd1;
                end
        A_CORDIC: if (cord_done) st <= A_CW;
        A_CW:   begin
                  o_wc <= $signed({{12{cord_ang[19]}}, cord_ang}) <<< 7;
                  sq_num <= e_ram[pkidx] >> 5; sq_res <= 24'd0; sq_bit <= 24'd1 << 22; sq_it <= 4'd0; st <= A_SQ;
                end
        A_SQ:   begin
                  if (sq_num >= sq_res + sq_bit) begin sq_num <= sq_num - sq_res - sq_bit; sq_res <= (sq_res >> 1) + sq_bit; end
                  else sq_res <= sq_res >> 1;
                  sq_bit <= sq_bit >> 2; sq_it <= sq_it + 4'd1;
                  if (sq_it == 4'd11) st <= A_DIV0;
                end
        A_DIV0: begin
                  isq <= sq_res[11:0]; gd_num <= {r_target, 8'd0}; gd_rem <= 25'd0; gd_q <= 24'd0; gd_it <= 5'd0; st <= A_DIV;
                end
        A_DIV:  begin
                  // restoring division of 256 TARGET by max(isq, 1), 24 bits of dividend
                  if ({gd_rem[23:0], gd_num[23]} >= {13'd0, isq_c}) begin gd_rem <= {gd_rem[23:0], gd_num[23]} - {13'd0, isq_c}; gd_q <= {gd_q[22:0], 1'b1}; end
                  else begin gd_rem <= {gd_rem[23:0], gd_num[23]}; gd_q <= {gd_q[22:0], 1'b0}; end
                  gd_num <= {gd_num[22:0], 1'b0}; gd_it <= gd_it + 5'd1;
                  if (gd_it == 5'd23) st <= A_FIN;
                end
        A_FIN:  begin
                  o_gain <= (gd_q > 24'd65535) ? 16'd65535 : gd_q[15:0];
                  o_n0 <= n0; o_first <= first; o_last <= last; o_pkidx <= pkidx; o_pk <= pk; o_epk <= e_ram[pkidx]; o_sr <= acc_r; o_si <= acc_i;
                  o_s0 <= $signed(n0) + $signed(({25'd0, first} + {25'd0, last} + 32'd1) >> 1) - 32'sd8;
                  found <= 1'b1; st <= S_DONE;
                end
        S_DONE: ;
        default: st <= P_IDLE;
      endcase
    end
  end
endmodule
