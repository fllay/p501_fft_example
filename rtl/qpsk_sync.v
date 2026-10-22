// Frame synchroniser of the m-sequence project (chapter 4e, part 1): correlates the phase steps of the received symbols with the known m-sequence preamble,
// finds the peak, tracks the frame period and produces the payload gate. Bit-exact model: tutorial/qpsk/p501_sync/qpsk_sync_fixed.py.
//
//   per symbol (pulse go, the engine's mi2, mq2 after the AGC, before the Costas derotation; one symbol is 104 clock cycles, this block needs about 55):
//     d = round((m x conj(m_prev)) >> 15), clip +-16383          -> a 64-entry ring RAM (two copies: two taps per clock)
//     C = sum_{k=0..62} chip[k] d[n-62+k],   E = sum |d|,   M = |C|      (|x| ~ max + min/2)           chip[k] = -1 where MSEQ[k] = 1
//     candidate: E > 0 and 256 M >= THR E;  peak at n-1: candidate(n-1) and M(n-1) >= M(n-2) and M(n-1) > M(n)
//     tracker: SEARCH -> LOCKED when two peaks are FL apart (+-TOL);  LOCKED: a peak within +-TOL of ref + FL is a hit (ref = peak), no peak by ref + FL + TOL + 1 is a miss,
//              MISSMAX misses in a row -> SEARCH
//     gate (combinational, for the engine's symbol eng_n):  LOCKED and GUARD <= eng_n - ref - 1 < PL
//   HARDWARE ACQUISITION (cooperation with the Costas loop): at every lock/hit (r_load = 2) or at the first r_nload of them (r_load = 1) an atan2 CORDIC (18 iterations) turns C into the frequency
//     w = signed(angle in turns x 2^20) << 12 (the OMEGA unit) and requests a load into the Costas frequency (ld_pend, ld_w; the engine takes it at its S7 state and answers ld_ack);
//     `narrow` selects the tracking gains once the tracker is locked and r_nsw hits have followed the lock (always when r_nsw = 0), else the acquisition gains.
`timescale 1ns/1ps
module qpsk_sync (
  input  wire        aclk,
  input  wire        run,
  input  wire        go,
  input  wire signed [15:0] mi, mq,
  input  wire [31:0] sym_idx,                // index n of the symbol that go announces
  input  wire [31:0] eng_n,                  // the engine's symbol counter, for the gate
  input  wire [31:0] r_fl, r_pl, r_thr, r_tol, r_missmax, r_guard, r_load, r_nload, r_nsw,
  output wire        narrow,
  output reg         ld_pend,
  output reg  [31:0] ld_w, w_last, n_ld,
  input  wire        ld_ack,
  output wire        gate,
  output wire        locked,
  output reg  [31:0] ref_idx, pk_idx,
  output reg  [31:0] n_det, n_hit, n_miss, n_false, n_lock, n_lost, late,
  output reg  signed [23:0] snap_re, snap_im,
  output reg  [23:0] snap_met, snap_en
);
  localparam [62:0] MSEQ = 63'b111110101011001101110110100100111000101111001010001100001000001;   // bit k = 1: chip k = -1
  localparam [3:0] F_IDLE = 4'd0, F_MUL = 4'd1, F_SUM = 4'd2, F_WR = 4'd3, F_LOOP = 4'd4, F_DRAIN = 4'd5, F_MET = 4'd6, F_CAND = 4'd7, F_PEAK = 4'd8, F_TRK1 = 4'd9, F_TRK2 = 4'd10;
  reg [3:0]  fs;
  reg signed [15:0] ci, cq, pmi, pmq;
  reg [31:0] n;
  reg signed [31:0] p1, p2, p3, p4;
  reg        state;                           // 0 SEARCH, 1 LOCKED
  reg        lastv;
  reg [31:0] lastp;
  reg [31:0] miss_run;
  reg [31:0] hlk, ev_cnt;                     // hits since the lock, locks and hits since the start
  assign locked = state;
  assign narrow = (r_nsw == 32'd0) || (state && (hlk >= r_nsw));

  // ---- the ring RAMs: d = {di, dr}; two copies, one read port each
  reg [31:0] ring_a [0:63];
  reg [31:0] ring_b [0:63];
  reg        wr_en;
  reg [5:0]  wr_addr;
  reg [31:0] wr_data;
  reg [5:0]  ra_addr, rb_addr;
  reg [31:0] rd_a, rd_b;
  always @(posedge aclk) begin
    if (wr_en) begin ring_a[wr_addr] <= wr_data; ring_b[wr_addr] <= wr_data; end
    rd_a <= ring_a[ra_addr]; rd_b <= ring_b[rb_addr];
  end

  function [23:0] amag(input signed [15:0] r, input signed [15:0] i);
    reg [15:0] a, b, mx, mn;
    begin a = r[15] ? -r : r; b = i[15] ? -i : i; mx = (a > b) ? a : b; mn = (a > b) ? b : a; amag = {8'd0, mx} + {9'd0, mn[15:1]}; end
  endfunction
  function [23:0] amag24(input signed [23:0] r, input signed [23:0] i);
    reg [23:0] a, b, mx, mn;
    begin a = r[23] ? -r : r; b = i[23] ? -i : i; mx = (a > b) ? a : b; mn = (a > b) ? b : a; amag24 = mx + {1'b0, mn[23:1]}; end
  endfunction

  wire signed [33:0] sre = p1 + p2, sim = p3 - p4;
  wire signed [33:0] rre = (sre + 34'sd16384) >>> 15, rim = (sim + 34'sd16384) >>> 15;
  reg signed [15:0] dr, di;

  // ---- the correlation loop: two taps per clock; c = issue, c+1 RAM read, c+2 terms, c+3 accumulate
  reg [5:0]  q;                               // tap pair 0..31
  reg [1:0]  vpipe;
  reg        vA1, vB1, vA2, vB2, sA1, sB1, sA2, sB2;
  reg signed [23:0] sr, si, se;               // accumulators (se is non-negative)
  reg signed [23:0] t0r, t0i, t1r, t1i;
  reg [23:0] m0, m1;
  wire [5:0]  k0 = {q[4:0], 1'b0}, k1 = {q[4:0], 1'b1};
  wire [31:0] jA = n + {26'd0, k0}, jB = n + {26'd0, k1};     // j + 62 where j = n - 62 + k
  wire        okA = (jA >= 32'd62) && (k0 <= 6'd62), okB = (jB >= 32'd62) && (k1 <= 6'd62);
  wire        negA = (k0 <= 6'd62) ? MSEQ[k0] : 1'b0, negB = (k1 <= 6'd62) ? MSEQ[k1] : 1'b0;

  // ---- metric, candidate, peak
  reg [23:0] met, en_c;
  reg signed [23:0] cre_c, cim_c;
  reg        cand;
  reg [23:0] m_p1, m_p2;                      // M(n-1), M(n-2)
  reg        c_p1;
  reg signed [23:0] re_p1, im_p1; reg [23:0] en_p1;
  reg [31:0] idx_p1;
  reg        peak;
  wire [47:0] lhs = {16'd0, met, 8'd0};
  wire [47:0] rhs = r_thr[7:0] * en_c;

  // ---- tracker helpers
  wire signed [33:0] delta = $signed({2'b00, idx_p1}) - $signed({2'b00, ref_idx}) - $signed({2'b00, r_fl});       // p - (ref + FL)
  wire        near_ref = (delta >= -$signed({2'b00, r_tol})) && (delta <= $signed({2'b00, r_tol}));
  wire signed [33:0] dls = $signed({2'b00, idx_p1}) - $signed({2'b00, lastp}) - $signed({2'b00, r_fl});
  wire        near_last = lastv && (dls >= -$signed({2'b00, r_tol})) && (dls <= $signed({2'b00, r_tol}));
  wire [31:0] miss_at = ref_idx + r_fl + r_tol + 32'd1;
  reg         a_start;
  reg signed [23:0] a_re, a_im;
  wire        ev_ok = (r_load[1:0] == 2'd2) || ((r_load[1:0] == 2'd1) && ((ev_cnt + 32'd1) <= r_nload));

  wire signed [32:0] pos = $signed({1'b0, eng_n}) - $signed({1'b0, ref_idx}) - 33'sd1;
  assign gate = state && !pos[32] && (pos >= $signed({1'b0, r_guard})) && (pos < $signed({1'b0, r_pl}));

  always @(posedge aclk) begin
    wr_en <= 1'b0; a_start <= 1'b0;                                              // a_start is a one-cycle pulse (set in F_TRK1)
    p1 <= ci * pmi; p2 <= cq * pmq; p3 <= cq * pmi; p4 <= ci * pmq;
    // stage 1 -> 2 of the correlation pipeline (free running; the valid bits are 0 outside the loop)
    vA1 <= 1'b0; vB1 <= 1'b0;
    vA2 <= vA1; vB2 <= vB1; sA2 <= sA1; sB2 <= sB1;
    // stage 2: terms of the two taps (the RAM data rd_a, rd_b are valid when vA2, vB2)
    t0r <= vA2 ? (sA2 ? -$signed(rd_a[15:0])  : $signed(rd_a[15:0]))  : 24'sd0;
    t0i <= vA2 ? (sA2 ? -$signed(rd_a[31:16]) : $signed(rd_a[31:16])) : 24'sd0;
    t1r <= vB2 ? (sB2 ? -$signed(rd_b[15:0])  : $signed(rd_b[15:0]))  : 24'sd0;
    t1i <= vB2 ? (sB2 ? -$signed(rd_b[31:16]) : $signed(rd_b[31:16])) : 24'sd0;
    m0  <= vA2 ? amag($signed(rd_a[15:0]), $signed(rd_a[31:16])) : 24'd0;
    m1  <= vB2 ? amag($signed(rd_b[15:0]), $signed(rd_b[31:16])) : 24'd0;
    if (!run) begin
      fs <= F_IDLE; state <= 1'b0; lastv <= 1'b0; lastp <= 32'd0; miss_run <= 32'd0; ref_idx <= 32'd0; pk_idx <= 32'd0; hlk <= 32'd0; ev_cnt <= 32'd0;
      n_det <= 32'd0; n_hit <= 32'd0; n_miss <= 32'd0; n_false <= 32'd0; n_lock <= 32'd0; n_lost <= 32'd0; late <= 32'd0;
      pmi <= 16'sd0; pmq <= 16'sd0; m_p1 <= 24'd0; m_p2 <= 24'd0; c_p1 <= 1'b0; re_p1 <= 24'sd0; im_p1 <= 24'sd0; en_p1 <= 24'd0; idx_p1 <= 32'd0;
      snap_re <= 24'sd0; snap_im <= 24'sd0; snap_met <= 24'd0; snap_en <= 24'd0; vpipe <= 2'd0; q <= 6'd0; sr <= 24'sd0; si <= 24'sd0; se <= 24'sd0;
    end else begin
      if (go && fs != F_IDLE) late <= late + 32'd1;
      if (fs == F_LOOP || fs == F_DRAIN) begin sr <= sr + t0r + t1r; si <= si + t0i + t1i; se <= se + m0 + m1; end      // stage 3
      case (fs)
        F_IDLE: if (go) begin ci <= mi; cq <= mq; n <= sym_idx; fs <= F_MUL; end
        F_MUL:  fs <= F_SUM;                                                          // the products are registered at the end of this cycle
        F_SUM:  begin
                  dr <= (rre > 34'sd16383) ? 16'sd16383 : (rre < -34'sd16383) ? -16'sd16383 : rre[15:0];
                  di <= (rim > 34'sd16383) ? 16'sd16383 : (rim < -34'sd16383) ? -16'sd16383 : rim[15:0];
                  pmi <= ci; pmq <= cq; fs <= F_WR;
                end
        F_WR:   begin
                  wr_en <= 1'b1; wr_addr <= n[5:0]; wr_data <= {di, dr};
                  q <= 6'd0; sr <= 24'sd0; si <= 24'sd0; se <= 24'sd0; vpipe <= 2'd0; fs <= F_LOOP;
                end
        F_LOOP: begin
                  // issue the reads for tap pair q: the address of j = n - 62 + k is (n + k + 2) mod 64
                  ra_addr <= n[5:0] + k0 + 6'd2; rb_addr <= n[5:0] + k1 + 6'd2;
                  vA1 <= okA; vB1 <= okB; sA1 <= negA; sB1 <= negB;
                  q <= q + 6'd1;
                  if (q == 6'd31) fs <= F_DRAIN;
                end
        F_DRAIN: begin
                  vpipe <= vpipe + 2'd1;
                  if (vpipe == 2'd2) fs <= F_MET;                                      // cycle c+3 of the last pair has been accumulated at the end of this cycle
                end
        F_MET:  begin met <= amag24(sr, si); en_c <= se[23:0]; cre_c <= sr; cim_c <= si; fs <= F_CAND; end
        F_CAND: begin cand <= (en_c != 24'd0) && (lhs >= rhs); fs <= F_PEAK; end
        F_PEAK: begin
                  peak <= (n >= 32'd1) && c_p1 && (m_p1 >= m_p2) && (m_p1 > met);
                  fs <= F_TRK1;
                end
        F_TRK1: begin
                  if (peak) begin
                    n_det <= n_det + 32'd1; pk_idx <= idx_p1; snap_re <= re_p1; snap_im <= im_p1; snap_met <= m_p1; snap_en <= en_p1;
                    if (!state) begin
                      if (near_last) begin state <= 1'b1; ref_idx <= idx_p1; miss_run <= 32'd0; lastv <= 1'b0; n_lock <= n_lock + 32'd1; hlk <= 32'd0; ev_cnt <= ev_cnt + 32'd1;
                                           if (ev_ok) begin a_start <= 1'b1; a_re <= re_p1; a_im <= im_p1; end end
                      else begin lastp <= idx_p1; lastv <= 1'b1; end
                    end else begin
                      if (near_ref) begin ref_idx <= idx_p1; miss_run <= 32'd0; n_hit <= n_hit + 32'd1; hlk <= hlk + 32'd1; ev_cnt <= ev_cnt + 32'd1;
                                          if (ev_ok) begin a_start <= 1'b1; a_re <= re_p1; a_im <= im_p1; end end
                      else n_false <= n_false + 32'd1;
                    end
                  end
                  m_p2 <= m_p1; m_p1 <= met; c_p1 <= cand; re_p1 <= cre_c; im_p1 <= cim_c; en_p1 <= en_c; idx_p1 <= n;      // the history for the next symbol
                  fs <= F_TRK2;
                end
        F_TRK2: begin
                  if (state && n == miss_at) begin
                    n_miss <= n_miss + 32'd1; miss_run <= miss_run + 32'd1; ref_idx <= ref_idx + r_fl;
                    if (miss_run + 32'd1 >= r_missmax) begin state <= 1'b0; lastv <= 1'b0; n_lost <= n_lost + 32'd1; end
                  end
                  fs <= F_IDLE;
                end
        default: fs <= F_IDLE;
      endcase
    end
  end

  // ---- atan2 of C: CORDIC vectoring, 18 iterations, the angle in turns x 2^20 (the table: atan(2^-i) / 2 pi x 2^20)
  reg [1:0]  as;                              // 0 idle, 1 iterate, 2 done
  reg signed [34:0] ax, ay;
  reg [19:0] aang;
  reg [4:0]  ait;
  wire signed [34:0] aysh = ay >>> ait, axsh = ax >>> ait;
  reg [19:0] atab;
  always @(*) case (ait)
    5'd0: atab = 20'd131072; 5'd1: atab = 20'd77376; 5'd2: atab = 20'd40884; 5'd3: atab = 20'd20753; 5'd4: atab = 20'd10417; 5'd5: atab = 20'd5213;
    5'd6: atab = 20'd2607;   5'd7: atab = 20'd1304;  5'd8: atab = 20'd652;   5'd9: atab = 20'd326;   5'd10: atab = 20'd163;  5'd11: atab = 20'd81;
    5'd12: atab = 20'd41;    5'd13: atab = 20'd20;   5'd14: atab = 20'd10;   5'd15: atab = 20'd5;    5'd16: atab = 20'd3;    default: atab = 20'd1;
  endcase
  always @(posedge aclk) begin
    if (ld_ack) ld_pend <= 1'b0;
    if (!run) begin as <= 2'd0; ld_pend <= 1'b0; ld_w <= 32'd0; w_last <= 32'd0; n_ld <= 32'd0; end
    else case (as)
      2'd0: if (a_start) begin
              if (a_re[23]) begin ax <= -{{11{a_re[23]}}, a_re}; ay <= -{{11{a_im[23]}}, a_im}; aang <= 20'h80000; end
              else          begin ax <= {{11{a_re[23]}}, a_re};  ay <= {{11{a_im[23]}}, a_im};  aang <= 20'd0; end
              ait <= 5'd0; as <= 2'd1;
            end
      2'd1: begin
              if (!ay[34]) begin ax <= ax + aysh; ay <= ay - axsh; aang <= aang + atab; end
              else         begin ax <= ax - aysh; ay <= ay + axsh; aang <= aang - atab; end
              ait <= ait + 5'd1;
              if (ait == 5'd17) as <= 2'd2;
            end
      2'd2: begin ld_w <= {aang, 12'd0}; w_last <= {aang, 12'd0}; ld_pend <= 1'b1; n_ld <= n_ld + 32'd1; as <= 2'd0; end
      default: as <= 2'd0;
    endcase
  end
endmodule
