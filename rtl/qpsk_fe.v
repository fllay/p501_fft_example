// Carrier-frequency estimator for the QPSK receiver: the differential 4th-power estimator, one symbol at a time, in about 23 clock cycles (a symbol lasts 104).
// tutorial/qpsk/p501_rx_fll/qpsk_fe_fixed.py is the bit-exact integer model; every width, shift and table comes from it.
//
//   m  = the symbol after the AGC, before the Costas derotation (the engine's mi2, mq2)          go = one pulse per symbol, with m valid
//   d  = m x conj(m_previous)            round(>>15), clipped to +-16383     (4 multipliers)
//   (angle, |d|) = CORDIC vectoring of (8 d), 13 iterations (adds and shifts)
//   psi = 4 x angle (the 16-bit angle wraps by itself: the DQPSK data steps, multiples of 90 degrees, vanish)
//   (c, s) = exp(j psi) from the 1024-entry sine/cosine table (Q15)
//   window: ACC_RE += c, ACC_IM += s, ACC_ABS += |d|(CORDIC), for N symbols after the arm (the first symbol after the start has no predecessor and is skipped)
//   Python: f = atan2(ACC_IM, ACC_RE) / (8 pi) x 960 kHz   (exact for |f| < 120 kHz);  quality = |ACC| / (N x 32767)
`timescale 1ns/1ps
module qpsk_fe (
  input  wire        aclk,
  input  wire        run,
  input  wire        go,
  input  wire signed [15:0] mi, mq,
  input  wire [31:0] sym_idx,                // the index of this symbol (symbols since the start)
  input  wire        arm,                    // pulse: clear the accumulators and start a window
  input  wire [31:0] r_n,                    // window length in symbols (1 .. 65535)
  output reg         active, done,
  output reg  [31:0] cnt, first,
  output reg  signed [31:0] acc_re, acc_im,
  output reg  [31:0] acc_abs
);
  localparam [3:0] F_IDLE = 4'd0, F_MUL = 4'd1, F_SUM = 4'd2, F_PRE = 4'd3, F_CORDIC = 4'd4, F_IDX = 4'd5, F_WAIT = 4'd6, F_ACC = 4'd7;
  reg [3:0]  fs;
  reg signed [15:0] ci, cq, pmi, pmq;
  reg [31:0] fidx;
  reg        pv, vthis;
  reg signed [31:0] p1, p2, p3, p4;
  reg signed [15:0] dr, di;
  reg signed [23:0] x, y;
  reg [15:0] ang;
  reg [3:0]  it;
  reg [9:0]  ta;
  wire signed [15:0] tc, ts;
  qpsk_rx_trig u_t (.clk(aclk), .a(ta), .c(tc), .s(ts));

  wire signed [33:0] sre = p1 + p2, sim = p3 - p4;                          // a x conj(b): re = ar br + ai bi, im = ai br - ar bi
  wire signed [33:0] rre = (sre + 34'sd16384) >>> 15, rim = (sim + 34'sd16384) >>> 15;
  wire signed [23:0] xs = {{5{dr[15]}}, dr, 3'b000}, ys = {{5{di[15]}}, di, 3'b000};
  wire up = ~y[23];
  wire signed [23:0] ysh = y >>> it, xsh = x >>> it;
  reg [15:0] atab;
  always @(*) case (it)
    4'd0: atab = 16'd8192; 4'd1: atab = 16'd4836; 4'd2: atab = 16'd2555; 4'd3: atab = 16'd1297; 4'd4: atab = 16'd651; 4'd5: atab = 16'd326;
    4'd6: atab = 16'd163;  4'd7: atab = 16'd81;   4'd8: atab = 16'd41;   4'd9: atab = 16'd20;   4'd10: atab = 16'd10; 4'd11: atab = 16'd5; default: atab = 16'd3;
  endcase
  wire [15:0] psi = {ang[13:0], 2'b00};
  wire [16:0] psi_r = {1'b0, psi} + 17'd32;
  wire [31:0] nn = (r_n == 32'd0) ? 32'd1 : (r_n > 32'd65535) ? 32'd65535 : r_n;
  wire [32:0] abs_sum = {1'b0, acc_abs} + {9'd0, x[23:0]};                  // |d| x 1.647 x 8: x is non-negative after the CORDIC

  always @(posedge aclk) begin
    if (!run) begin
      fs <= F_IDLE; active <= 1'b0; done <= 1'b0; cnt <= 32'd0; first <= 32'd0; acc_re <= 32'sd0; acc_im <= 32'sd0; acc_abs <= 32'd0;
      pv <= 1'b0; pmi <= 16'sd0; pmq <= 16'sd0; vthis <= 1'b0;
    end else begin
      case (fs)
        F_IDLE: if (go) begin ci <= mi; cq <= mq; fidx <= sym_idx; fs <= F_MUL; end
        F_MUL:  begin p1 <= ci * pmi; p2 <= cq * pmq; p3 <= cq * pmi; p4 <= ci * pmq; vthis <= pv; fs <= F_SUM; end
        F_SUM:  begin
                  dr <= (rre > 34'sd16383) ? 16'sd16383 : (rre < -34'sd16383) ? -16'sd16383 : rre[15:0];
                  di <= (rim > 34'sd16383) ? 16'sd16383 : (rim < -34'sd16383) ? -16'sd16383 : rim[15:0];
                  pmi <= ci; pmq <= cq; pv <= 1'b1; fs <= F_PRE;
                end
        F_PRE:  begin                                                           // fold into the right half plane
                  x <= xs[23] ? -xs : xs; y <= xs[23] ? -ys : ys; ang <= xs[23] ? 16'h8000 : 16'h0000; it <= 4'd0; fs <= F_CORDIC;
                end
        F_CORDIC: begin
                  x <= up ? x + ysh : x - ysh;
                  y <= up ? y - xsh : y + xsh;
                  ang <= up ? ang + atab : ang - atab;
                  it <= it + 4'd1;
                  if (it == 4'd12) fs <= F_IDX;
                end
        F_IDX:  begin ta <= psi_r[15:6]; fs <= F_WAIT; end                       // (psi + 32) >> 6, modulo 1024
        F_WAIT: fs <= F_ACC;                                                     // the table read
        F_ACC:  begin
                  if (active && vthis) begin
                    acc_re <= acc_re + tc; acc_im <= acc_im + ts;
                    acc_abs <= (abs_sum > 33'h7FFFFFFF) ? 32'h7FFFFFFF : abs_sum[31:0];
                    if (cnt == 32'd0) first <= fidx;
                    cnt <= cnt + 32'd1;
                    if (cnt + 32'd1 >= nn) begin active <= 1'b0; done <= 1'b1; end
                  end
                  fs <= F_IDLE;
                end
        default: fs <= F_IDLE;
      endcase
      if (arm) begin active <= 1'b1; done <= 1'b0; cnt <= 32'd0; acc_re <= 32'sd0; acc_im <= 32'sd0; acc_abs <= 32'd0; end
    end
  end
endmodule
