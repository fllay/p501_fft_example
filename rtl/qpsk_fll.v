// Band-edge FLL for the QPSK receiver: the FPGA version of GNU Radio's digital.fll_band_edge_cc, in front of the polyphase matched filter (qpsk_rx_fll.v).
//
//   raw ADC samples (RAM written on adc_clk) -> derotate  y = x e^{j phi}, phi += fr per sample  -> derotated sample RAM (read by the receiver engine)
//   once per block of 4 samples (a symbol): error = normalised power difference of the two band-edge filters (55 complex taps, 4 multipliers give both) over the last
//   55 derotated samples -> fr += GI e, phi += GP e, taking effect at the first sample of block k + 2.
//
// tutorial/qpsk/p501_rx_fll/qpsk_fll_fixed.py is the bit-exact integer model; every width, shift and the two-block latency come from it. Everything runs on aclk (100 MHz):
// a sample arrives every 26 clock cycles, the derotator needs 7, the error engine about 70 per block of 4 samples (104 cycles).
`timescale 1ns/1ps
module qpsk_fll (
  input  wire        aclk,
  input  wire        run,                    // 0 resets the stage (the parent's run)
  // raw samples: the parent's RAM, written on adc_clk; raw_cnt = number of samples written (already in the aclk domain)
  input  wire [31:0] raw_cnt,
  output reg  [7:0]  raw_raddr,
  input  wire [31:0] raw_word,               // {q[15:0], i[15:0]}, valid two cycles after raw_raddr
  // derotated samples for the engine
  output reg  [31:0] d_cnt,                  // derotated samples written, same indexing as raw_cnt
  input  wire [7:0]  e_raddr,
  output reg  [31:0] e_word,                 // {yq, yi}, valid the cycle after e_raddr
  // registers
  input  wire [31:0] r_ctrl,                 // bit0: loop enabled (0 holds fr), bit1: rising edge loads fr from r_f0
  input  wire [31:0] r_gi, r_gp, r_f0,
  output wire [31:0] o_freq,                 // fr, turns x 2^32 per sample (two's complement)
  output wire [15:0] o_err,                  // the last error e, Q15
  output wire [31:0] o_nblk,                 // blocks measured
  output wire [31:0] o_late                  // cycles the derotator had to wait for a measurement: 0 in normal operation
);
  // ======================= derotated sample RAM: two copies (engine, error MAC) =======================
  reg [31:0] dram_e [0:255];
  reg [31:0] dram_f [0:255];
  reg        d_we;
  reg [7:0]  d_waddr;
  reg [31:0] d_wdata;
  always @(posedge aclk) begin
    if (d_we) begin dram_e[d_waddr] <= d_wdata; dram_f[d_waddr] <= d_wdata; end
    e_word <= dram_e[e_raddr];
  end

  // ======================= derotator =======================
  localparam [3:0] DW = 4'd0, D1 = 4'd1, D2 = 4'd2, D3 = 4'd3, D4 = 4'd4, D5 = 4'd5, D6 = 4'd6;
  reg [3:0]  ds;
  reg [31:0] n, blk, phi, fr, late_cnt;
  reg [1:0]  ph;
  reg signed [15:0] xr, xq;
  reg [9:0]  rot_a;
  wire signed [15:0] rc, rs;
  qpsk_rx_trig u_rot (.clk(aclk), .a(rot_a), .c(rc), .s(rs));
  reg signed [32:0] mr, mi;
  reg        ld_q;
  reg        mac_req;
  reg [7:0]  mac_wend;
  reg        pend_valid;
  reg [31:0] pend_dfr, pend_dphi;
  wire [31:0] avail_diff = raw_cnt - n;
  wire        raw_avail = (avail_diff != 32'd0) && !avail_diff[31];
  wire signed [32:0] mr_r = mr + 33'sd16384, mi_r = mi + 33'sd16384;
  wire signed [32:0] yr_f = mr_r >>> 15, yi_f = mi_r >>> 15;
  wire signed [15:0] yr_c = (yr_f > 33'sd32767) ? 16'sd32767 : (yr_f < -33'sd32767) ? -16'sd32767 : yr_f[15:0];
  wire signed [15:0] yi_c = (yi_f > 33'sd32767) ? 16'sd32767 : (yi_f < -33'sd32767) ? -16'sd32767 : yi_f[15:0];
  assign o_freq = fr;
  assign o_late = late_cnt;

  always @(posedge aclk) begin
    ld_q <= r_ctrl[1]; d_we <= 1'b0; mac_req <= 1'b0;
    if (!run) begin
      n <= raw_cnt; d_cnt <= raw_cnt; ph <= 2'd0; blk <= 32'd0; phi <= 32'd0; fr <= r_f0; ds <= DW; late_cnt <= 32'd0;
    end else begin
      case (ds)
        DW: if (raw_avail) begin
              if (ph == 2'd0 && blk >= 32'd15) begin                         // the update measured two blocks ago takes effect now
                if (pend_valid) begin fr <= fr + pend_dfr; phi <= phi + pend_dphi; raw_raddr <= n[7:0]; ds <= D1; end
                else late_cnt <= late_cnt + 32'd1;
              end else begin raw_raddr <= n[7:0]; ds <= D1; end
            end
        D1: ds <= D2;                                                         // the RAM read
        D2: begin xr <= raw_word[15:0]; xq <= raw_word[31:16]; rot_a <= (phi + 32'h0020_0000) >> 22; ds <= D3; end
        D3: ds <= D4;                                                         // the table read
        D4: begin mr <= xr * rc - xq * rs; mi <= xr * rs + xq * rc; ds <= D5; end
        D5: begin
              d_wdata <= {yi_c, yr_c}; d_waddr <= n[7:0]; d_we <= 1'b1;
              phi <= phi + fr; n <= n + 32'd1; ph <= ph + 2'd1;
              if (ph == 2'd3) begin blk <= blk + 32'd1; if (blk >= 32'd13) begin mac_req <= 1'b1; mac_wend <= n[7:0]; end end
              ds <= D6;
            end
        D6: begin d_cnt <= n; ds <= DW; end                                   // the sample is in the RAM from this edge on
        default: ds <= DW;
      endcase
      if (r_ctrl[1] & ~ld_q) fr <= r_f0;                                      // a live load of the frequency (the driver hands the total offset over)
    end
  end

  // ======================= error engine, once per block =======================
  localparam [3:0] M_IDLE = 4'd0, M_RUN = 4'd1, M_UL = 4'd2, M_SQ1 = 4'd3, M_SQ2 = 4'd4, M_SQ3 = 4'd5, M_SUM = 4'd6, M_MSB = 4'd7, M_NORM = 4'd8, M_UPD1 = 4'd9, M_UPD2 = 4'd10;
  reg [3:0]  ms;
  reg [6:0]  ci;
  reg [7:0]  wend, f_addr;
  reg [5:0]  t_addr;
  reg        v0, v1, v2;
  reg [31:0] f_word;
  wire signed [15:0] tcr, tci;
  qpsk_fll_taps u_tap (.clk(aclk), .i(t_addr), .cr(tcr), .ci(tci));
  reg signed [31:0] pA, pB, pC, pD;
  reg signed [39:0] sA, sB, sC, sD;
  reg signed [23:0] ur, ui, lr, li;
  reg signed [47:0] q1, q2, q3, q4;
  reg        [47:0] pu, pl;
  reg        [48:0] ssum;
  reg signed [48:0] dif;
  reg [5:0]  msb;
  reg signed [15:0] e_q;
  reg signed [63:0] dtmp;
  reg signed [48:0] mf, mp;
  reg [15:0] err_r;
  reg [31:0] nblk;
  assign o_err = err_r;
  assign o_nblk = nblk;

  function signed [23:0] clipv(input signed [40:0] v);                        // round(v >> 6), clipped to 24 bit
    reg signed [40:0] t;
    begin t = (v + 41'sd32) >>> 6; clipv = (t > 41'sd8388607) ? 24'sd8388607 : (t < -41'sd8388607) ? -24'sd8388607 : t[23:0]; end
  endfunction
  function [5:0] msb49(input [48:0] v);
    integer k;
    begin msb49 = 6'd0; for (k = 0; k < 49; k = k + 1) if (v[k]) msb49 = k[5:0]; end
  endfunction

  always @(posedge aclk) begin
    // pipeline of the multiply-accumulate: addresses (v0) -> data valid (v1) -> products valid (v2)
    f_word <= dram_f[f_addr];
    v1 <= v0; v2 <= v1;
    pA <= $signed(f_word[15:0])  * tcr;  pB <= $signed(f_word[31:16]) * tci;
    pC <= $signed(f_word[31:16]) * tcr;  pD <= $signed(f_word[15:0])  * tci;
    if (!run) begin ms <= M_IDLE; pend_valid <= 1'b0; nblk <= 32'd0; err_r <= 16'd0; v0 <= 1'b0; end
    else begin
      if (pend_valid && ds == DW && ph == 2'd0 && blk >= 32'd15 && raw_avail) pend_valid <= 1'b0;   // consumed by the derotator
      case (ms)
        M_IDLE: if (mac_req) begin wend <= mac_wend; ci <= 7'd0; sA <= 40'sd0; sB <= 40'sd0; sC <= 40'sd0; sD <= 40'sd0; ms <= M_RUN; end
        M_RUN: begin
                 f_addr <= wend - 8'd54 + {1'b0, ci}; t_addr <= ci[5:0]; v0 <= (ci < 7'd55); ci <= ci + 7'd1;
                 if (v2) begin sA <= sA + pA; sB <= sB + pB; sC <= sC + pC; sD <= sD + pD; end
                 if (ci == 7'd59) ms <= M_UL;
               end
        M_UL:  begin ur <= clipv(sA - sB); ui <= clipv(sC + sD); lr <= clipv(sA + sB); li <= clipv(sC - sD); ms <= M_SQ1; end
        M_SQ1: begin q1 <= ur * ur; q2 <= ui * ui; ms <= M_SQ2; end
        M_SQ2: begin q3 <= lr * lr; q4 <= li * li; pu <= q1[47:0] + q2[47:0]; ms <= M_SQ3; end
        M_SQ3: begin pl <= q3[47:0] + q4[47:0]; ms <= M_SUM; end
        M_SUM: begin ssum <= {1'b0, pu} + {1'b0, pl}; dif <= $signed({1'b0, pl}) - $signed({1'b0, pu}); ms <= M_MSB; end
        M_MSB: begin msb <= msb49(ssum); ms <= M_NORM; end
        M_NORM: begin
                  if (ssum == 49'd0) e_q <= 16'sd0;
                  else begin
                    if (msb > 6'd14) dtmp = ($signed({{15{dif[48]}}, dif}) + (64'sd1 <<< (msb - 6'd15))) >>> (msb - 6'd14);
                    else dtmp = $signed({{15{dif[48]}}, dif}) <<< (6'd14 - msb);
                    e_q <= (dtmp > 64'sd32767) ? 16'sd32767 : (dtmp < -64'sd32767) ? -16'sd32767 : dtmp[15:0];
                  end
                  ms <= M_UPD1;
                end
        M_UPD1: begin mf <= $signed({1'b0, r_gi}) * e_q; mp <= $signed({1'b0, r_gp}) * e_q; ms <= M_UPD2; end
        M_UPD2: if (!pend_valid) begin
                  pend_dfr <= r_ctrl[0] ? ((mf + 49'sd16384) >>> 15) : 32'd0;
                  pend_dphi <= r_ctrl[0] ? ((mp + 49'sd16384) >>> 15) : 32'd0;
                  pend_valid <= 1'b1; err_r <= e_q; nblk <= nblk + 32'd1; ms <= M_IDLE;
                end
        default: ms <= M_IDLE;
      endcase
    end
  end
endmodule
