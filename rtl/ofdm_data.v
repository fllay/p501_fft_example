// Data-symbol processing of the OFDM receiver (bit-exact: tutorial/ofdm/ofdm_fixed.py, the part of receive_fixed after the channel estimate).
//
// sym_go (symbol `sym` = l, 0 .. 43): the FFT RAM holds the transform Y of the derotated window of data symbol l; the module then
//   phase 1:  for the 28 used bins  Z = (Y W + 2^13) >> 14 (W from the channel module, one complex multiply, 24-bit result);  data bins -> zmem[l][0..23];  the 4 pilots:  q = Z conj(ref) 181 >> 8 (ref = (+-1 +-j) x the PRBS-7 polarity of l),
//             g[l] = ((sum q_r + 2) >> 2, (sum q_i + 2) >> 2);  d4 = q(+4) conj q(-4), d11 = q(+11) conj q(-11), each shifted right to 14 bits;  slope[l] = (angle(d4 d11) (CORDIC, turns x 2^20) x 139811) >> 10
//   phase 2:  symbol l - 2 (and, at l = 43, also 42 and 43): g and slope averaged over the window l-2-2 .. l-2+2 (clipped to 0 .. 43): (sum x rc + 2^15) >> 16, rc = round(2^16 / count);
//             c = conj(gs) K / |gs|^2 (K = R 2^14, the divider; (2^14, 0) if gs = 0);  per data subcarrier k: th = (-slope k) mod 2^32, (cos, sin) = table[th >> 22];  r = (c (cos + j sin) + 2^14) >> 15 (20-bit);  out = (Z r + 2^13) >> 14;
//             slicer (thresholds 0, +-8192), Gray index, PRBS-15 checker (restarted by frame_start), EVM sums.
// About 700 clocks for phase 1 and 400 for each phase 2. ovf (sticky until frame_start): a Z beyond 24 bits or a correction beyond 20 bits.
`timescale 1ns/1ps
module ofdm_data (
  input  wire        clk,
  input  wire        frame_start,
  input  wire        sym_go,
  input  wire [5:0]  sym,
  output wire [5:0]  rd_addr,
  input  wire signed [19:0] rd_re, rd_im,
  output wire [4:0]  w_addr,
  input  wire signed [31:0] w_re, w_im,
  output reg         busy, done,
  output reg  [31:0] sym_cnt, sym_err, bit_err,
  output reg  [63:0] evm_err, evm_ref,
  output reg         o_valid,
  output reg  [10:0] o_idx,
  output reg  signed [23:0] o_re, o_im,
  output reg         ovf
);
  localparam signed [31:0] KK = 32'sd212221952;
  function [5:0] bin_of(input [4:0] i);
    case (i)
      5'd0: bin_of = 6'd50;
      5'd1: bin_of = 6'd51;
      5'd2: bin_of = 6'd52;
      5'd3: bin_of = 6'd53;
      5'd4: bin_of = 6'd54;
      5'd5: bin_of = 6'd55;
      5'd6: bin_of = 6'd56;
      5'd7: bin_of = 6'd57;
      5'd8: bin_of = 6'd58;
      5'd9: bin_of = 6'd59;
      5'd10: bin_of = 6'd60;
      5'd11: bin_of = 6'd61;
      5'd12: bin_of = 6'd62;
      5'd13: bin_of = 6'd63;
      5'd14: bin_of = 6'd1;
      5'd15: bin_of = 6'd2;
      5'd16: bin_of = 6'd3;
      5'd17: bin_of = 6'd4;
      5'd18: bin_of = 6'd5;
      5'd19: bin_of = 6'd6;
      5'd20: bin_of = 6'd7;
      5'd21: bin_of = 6'd8;
      5'd22: bin_of = 6'd9;
      5'd23: bin_of = 6'd10;
      5'd24: bin_of = 6'd11;
      5'd25: bin_of = 6'd12;
      5'd26: bin_of = 6'd13;
      5'd27: bin_of = 6'd14;
      default: bin_of = 6'd0;
    endcase
  endfunction
  function [2:0] pj_of(input [4:0] i);                 // {is pilot, pilot number 0 .. 3 (k = -11, -4, +4, +11)}
    case (i)
      5'd0: pj_of = 3'b000;
      5'd1: pj_of = 3'b000;
      5'd2: pj_of = 3'b000;
      5'd3: pj_of = 3'b100;
      5'd4: pj_of = 3'b000;
      5'd5: pj_of = 3'b000;
      5'd6: pj_of = 3'b000;
      5'd7: pj_of = 3'b000;
      5'd8: pj_of = 3'b000;
      5'd9: pj_of = 3'b000;
      5'd10: pj_of = 3'b101;
      5'd11: pj_of = 3'b000;
      5'd12: pj_of = 3'b000;
      5'd13: pj_of = 3'b000;
      5'd14: pj_of = 3'b000;
      5'd15: pj_of = 3'b000;
      5'd16: pj_of = 3'b000;
      5'd17: pj_of = 3'b110;
      5'd18: pj_of = 3'b000;
      5'd19: pj_of = 3'b000;
      5'd20: pj_of = 3'b000;
      5'd21: pj_of = 3'b000;
      5'd22: pj_of = 3'b000;
      5'd23: pj_of = 3'b000;
      5'd24: pj_of = 3'b111;
      5'd25: pj_of = 3'b000;
      5'd26: pj_of = 3'b000;
      5'd27: pj_of = 3'b000;
      default: pj_of = 3'b000;
    endcase
  endfunction
  function signed [5:0] kk_of(input [4:0] j);          // the subcarrier number of data subcarrier j
    case (j)
      5'd0: kk_of = -6'sd14;
      5'd1: kk_of = -6'sd13;
      5'd2: kk_of = -6'sd12;
      5'd3: kk_of = -6'sd10;
      5'd4: kk_of = -6'sd9;
      5'd5: kk_of = -6'sd8;
      5'd6: kk_of = -6'sd7;
      5'd7: kk_of = -6'sd6;
      5'd8: kk_of = -6'sd5;
      5'd9: kk_of = -6'sd3;
      5'd10: kk_of = -6'sd2;
      5'd11: kk_of = -6'sd1;
      5'd12: kk_of = 6'sd1;
      5'd13: kk_of = 6'sd2;
      5'd14: kk_of = 6'sd3;
      5'd15: kk_of = 6'sd5;
      5'd16: kk_of = 6'sd6;
      5'd17: kk_of = 6'sd7;
      5'd18: kk_of = 6'sd8;
      5'd19: kk_of = 6'sd9;
      5'd20: kk_of = 6'sd10;
      5'd21: kk_of = 6'sd12;
      5'd22: kk_of = 6'sd13;
      5'd23: kk_of = 6'sd14;
      default: kk_of = 6'sd0;
    endcase
  endfunction
  localparam [43:0] POLB = 44'b01011101100001110101111001111101111110000000;          // bit l: the polarity of symbol l is +1 (1) or -1 (0)
  reg [4:0] idx;
  assign rd_addr = bin_of(idx);
  assign w_addr = idx;
  // ---- storage
  reg signed [23:0] zm_r [0:1055], zm_i [0:1055];     // 44 x 24 data values
  reg signed [23:0] g_r [0:43], g_i [0:43];
  reg signed [31:0] sl_m [0:43];
  // ---- states
  localparam [5:0] S_IDLE = 0, S_RD = 1, S_MUL = 2, S_Z = 3, S_ST = 4, S_Q1 = 5, S_Q2 = 6, S_G = 7, S_D1 = 8, S_D2 = 9, S_D3 = 10, S_D4 = 11, S_CORD = 12, S_SL = 13,
                   S_F0 = 14, S_F1 = 15, S_F2 = 16, S_F3 = 17, S_F4 = 18, S_DIV1 = 19, S_DIV2 = 20, S_J0 = 21, S_J1 = 22, S_J2 = 23, S_J3 = 24, S_J4 = 25, S_J5 = 26, S_J6 = 27, S_J7 = 28, S_NEXT = 29, S_FWAIT = 30, S_DONE = 31;
  reg [5:0] st;
  reg [5:0] cur;                                       // the symbol of phase 1
  reg [5:0] fl;                                        // the symbol of phase 2
  reg [1:0] fcount;                                    // how many phase 2 runs remain after this one (at the last symbol)
  reg [4:0] dcnt;
  reg signed [19:0] yr, yi; reg signed [31:0] wr, wi;
  reg signed [51:0] m0, m1, m2, m3;
  reg signed [23:0] zr, zi;
  reg signed [23:0] pq_r [0:3], pq_i [0:3];
  reg signed [27:0] sq_r, sq_i;
  wire [2:0] pj = pj_of(idx);
  wire pol = POLB[cur];
  // the signs of the pilot values (+-1 +-j)/sqrt 2: from the model PIL_V
  reg [1:0] pvs;
  always @* begin
    case (pj[1:0])
      2'd0: pvs = 2'b11; 2'd1: pvs = 2'b10; 2'd2: pvs = 2'b01; default: pvs = 2'b00;      // {sign of re > 0, sign of im > 0}: (1+j), (1-j), (-1+j), (-1-j)
    endcase
  end
  wire rs_p = pvs[1] ^ ~pol;                         // the real sign of the reference: (+1 if 1): pvs real sign times the polarity
  wire rsi_p = pvs[0] ^ ~pol;
  reg signed [47:0] uu, vv;
  // CORDIC and the slope
  reg cord_start; wire cord_done; wire [19:0] cord_ang;
  reg signed [39:0] cin_r, cin_i;
  ofdm_cordic u_cordic (.clk(clk), .start(cord_start), .re(cin_r), .im(cin_i), .done(cord_done), .ang(cord_ang));
  reg signed [47:0] d4r, d4i, d11r, d11i;
  reg signed [27:0] n4r, n4i, n11r, n11i;
  reg signed [55:0] sp;
  function [5:0] bitlen48(input [47:0] v);
    integer i;
    begin bitlen48 = 6'd0; for (i = 0; i < 48; i = i + 1) if (v[i]) bitlen48 = i + 1; end
  endfunction
  function [5:0] shn(input signed [47:0] a, input signed [47:0] b);
    reg [47:0] aa, bb; reg [5:0] bl;
    begin aa = a[47] ? -a : a; bb = b[47] ? -b : b; bl = bitlen48(aa | bb); shn = (bl > 6'd14) ? (bl - 6'd14) : 6'd0; end
  endfunction
  // phase 2
  reg signed [31:0] gs_r, gs_i; reg signed [31:0] ss;
  reg signed [49:0] sacc_r, sacc_i, sacc_s;
  reg [5:0] wl, wh, wi_; reg [15:0] rc; reg [2:0] wcnt;
  reg [41:0] den; reg signed [49:0] numr, numi;
  reg div_start; wire div_done; wire signed [31:0] div_q; reg signed [49:0] div_num; reg [41:0] div_den;
  ofdm_div u_div (.clk(clk), .start(div_start), .num(div_num), .den(div_den), .done(div_done), .q(div_q));
  reg signed [31:0] ir, ii;
  reg [4:0] j; reg second_div;
  reg [31:0] th; wire signed [15:0] tc, ts; reg [9:0] tidx;
  qpsk_rx_trig u_trig (.clk(clk), .a(tidx), .c(tc), .s(ts));
  reg signed [51:0] c0, c1, c2, c3;
  reg signed [19:0] cr_, ci_;
  reg signed [23:0] fr, fi_;
  reg signed [63:0] o0, o1, o2, o3;
  // checker
  reg [14:0] prbs; reg [3:0] exp_idx;
  reg [1:0] lvl_i, lvl_q; reg [3:0] dec_idx;
  reg signed [15:0] sv_i, sv_q;
  function [1:0] slice2(input signed [23:0] z);      // 0: -3, 1: -1, 2: +1, 3: +3
    slice2 = (z < -24'sd8192) ? 2'd0 : (z < 24'sd0) ? 2'd1 : (z < 24'sd8192) ? 2'd2 : 2'd3;
  endfunction
  function [1:0] gray2(input [1:0] l);               // level -> Gray index 00,01,11,10
    case (l) 2'd0: gray2 = 2'b00; 2'd1: gray2 = 2'b01; 2'd2: gray2 = 2'b11; default: gray2 = 2'b10; endcase
  endfunction
  function signed [15:0] levv(input [1:0] l);        // level value in units of 4096 (-3, -1, 1, 3)
    case (l) 2'd0: levv = -16'sd3; 2'd1: levv = -16'sd1; 2'd2: levv = 16'sd1; default: levv = 16'sd3; endcase
  endfunction
  integer q;
  reg signed [63:0] e_i, e_q, sq_ref;
  reg [14:0] pn; reg [3:0] pb;
  initial begin st = S_IDLE; busy = 0; done = 0; o_valid = 0; ovf = 0; end
  always @(posedge clk) begin
    done <= 1'b0; o_valid <= 1'b0; cord_start <= 1'b0; div_start <= 1'b0;
    if (frame_start) begin
      ovf <= 1'b0; sym_cnt <= 0; sym_err <= 0; bit_err <= 0; evm_err <= 0; evm_ref <= 0; prbs <= 15'h7FFF; st <= S_IDLE; busy <= 1'b0;
    end else case (st)
      S_IDLE: if (sym_go) begin cur <= sym; idx <= 5'd0; dcnt <= 5'd0; sq_r <= 0; sq_i <= 0; busy <= 1'b1; st <= S_RD; end
      // ---- phase 1: the 28 bins
      S_RD:   begin yr <= rd_re; yi <= rd_im; wr <= w_re; wi <= w_im; st <= S_MUL; end
      S_MUL:  begin m0 <= yr * wr; m1 <= yi * wi; m2 <= yr * wi; m3 <= yi * wr; st <= S_Z; end
      S_Z:    begin
                zr <= (m0 - m1 + 52'sd8192) >>> 14; zi <= (m2 + m3 + 52'sd8192) >>> 14;
                if ((((m0 - m1 + 52'sd8192) >>> 14) > 52'sd8388607) || (((m0 - m1 + 52'sd8192) >>> 14) < -52'sd8388608) || (((m2 + m3 + 52'sd8192) >>> 14) > 52'sd8388607) || (((m2 + m3 + 52'sd8192) >>> 14) < -52'sd8388608)) ovf <= 1'b1;
                st <= S_ST;
              end
      S_ST:   begin
                if (pj[2]) st <= S_Q1;
                else begin zm_r[cur * 24 + dcnt] <= zr; zm_i[cur * 24 + dcnt] <= zi; dcnt <= dcnt + 5'd1; st <= S_NEXT; end
              end
      S_Q1:   begin
                uu <= zr * (rs_p ? 24'sd1 : -24'sd1) + zi * (rsi_p ? 24'sd1 : -24'sd1);
                vv <= zi * (rs_p ? 24'sd1 : -24'sd1) - zr * (rsi_p ? 24'sd1 : -24'sd1);
                st <= S_Q2;
              end
      S_Q2:   begin
                pq_r[pj[1:0]] <= (uu * 48'sd181 + 48'sd128) >>> 8; pq_i[pj[1:0]] <= (vv * 48'sd181 + 48'sd128) >>> 8;
                sq_r <= sq_r + ((uu * 48'sd181 + 48'sd128) >>> 8); sq_i <= sq_i + ((vv * 48'sd181 + 48'sd128) >>> 8);
                st <= S_NEXT;
              end
      S_NEXT: begin
                if (idx == 5'd27) st <= S_G; else begin idx <= idx + 5'd1; st <= S_RD; end
              end
      S_G:    begin
                g_r[cur] <= (sq_r + 28'sd2) >>> 2; g_i[cur] <= (sq_i + 28'sd2) >>> 2;
                // d4 = q(+4) conj q(-4) (pilots 2 and 1), d11 = q(+11) conj q(-11) (pilots 3 and 0)
                d4r <= pq_r[2] * pq_r[1] + pq_i[2] * pq_i[1]; d4i <= pq_i[2] * pq_r[1] - pq_r[2] * pq_i[1];
                d11r <= pq_r[3] * pq_r[0] + pq_i[3] * pq_i[0]; d11i <= pq_i[3] * pq_r[0] - pq_r[3] * pq_i[0];
                st <= S_D1;
              end
      S_D1:   begin
                n4r <= d4r >>> shn(d4r, d4i); n4i <= d4i >>> shn(d4r, d4i); n11r <= d11r >>> shn(d11r, d11i); n11i <= d11i >>> shn(d11r, d11i); st <= S_D2;
              end
      S_D2:   begin cin_r <= n4r * n11r - n4i * n11i; cin_i <= n4r * n11i + n4i * n11r; st <= S_D3; end
      S_D3:   begin cord_start <= 1'b1; st <= S_CORD; end
      S_CORD: if (cord_done) st <= S_SL;
      S_SL:   begin
                sp = $signed({{36{cord_ang[19]}}, cord_ang}) * 56'sd139811;
                sl_m[cur] <= sp >>> 10;
                if (cur >= 6'd2) begin fl <= cur - 6'd2; fcount <= (cur == 6'd43) ? 2'd2 : 2'd0; st <= S_F0; end
                else begin busy <= 1'b0; done <= 1'b1; st <= S_IDLE; end
              end
      // ---- phase 2 for symbol fl
      S_F0:   begin
                wl <= (fl >= 6'd2) ? (fl - 6'd2) : 6'd0; wh <= (fl + 6'd2 > 6'd43) ? 6'd43 : (fl + 6'd2);
                sacc_r <= 0; sacc_i <= 0; sacc_s <= 0; st <= S_F1;
              end
      S_F1:   begin wi_ <= wl; wcnt <= 3'd0; st <= S_F2; end
      S_F2:   begin
                sacc_r <= sacc_r + g_r[wi_]; sacc_i <= sacc_i + g_i[wi_]; sacc_s <= sacc_s + sl_m[wi_]; wcnt <= wcnt + 3'd1;
                if (wi_ == wh) st <= S_F3; else wi_ <= wi_ + 6'd1;
              end
      S_F3:   begin
                rc <= (wcnt == 3'd3) ? 16'd21845 : (wcnt == 3'd4) ? 16'd16384 : 16'd13107;       // (65536 + count / 2) / count
                st <= S_F4;
              end
      S_F4:   begin
                gs_r <= (sacc_r * $signed({1'b0, rc}) + 50'sd32768) >>> 16; gs_i <= (sacc_i * $signed({1'b0, rc}) + 50'sd32768) >>> 16; ss <= (sacc_s * $signed({1'b0, rc}) + 50'sd32768) >>> 16;
                st <= S_DIV1;
              end
      S_DIV1: begin
                den <= gs_r * gs_r + gs_i * gs_i;
                st <= S_DIV2;
              end
      S_DIV2: begin
                if (den == 0) begin ir <= 32'sd16384; ii <= 32'sd0; j <= 5'd0; st <= S_J0; end
                else begin div_num <= gs_r * KK; div_den <= den; div_start <= 1'b1; second_div <= 1'b0; st <= S_J7; end        // S_J7 is used here as the wait for the first quotient
              end
      S_J7:   if (div_done) begin
                if (!second_div) begin ir <= div_q; second_div <= 1'b1; div_num <= -gs_i * KK; div_den <= den; div_start <= 1'b1; end
                else begin ii <= div_q; second_div <= 1'b0; j <= 5'd0; st <= S_J0; end
              end
      // ---- per data subcarrier j
      S_J0:   begin
                th <= -(ss * kk_of(j)); st <= S_J1;
              end
      S_J1:   begin tidx <= th[31:22]; st <= S_J2; end
      S_J2:   st <= S_J3;                                                    // the table output is registered
      S_J3:   begin
                c0 <= ir * tc; c1 <= ii * ts; c2 <= ir * ts; c3 <= ii * tc; st <= S_J4;
              end
      S_J4:   begin
                cr_ <= (c0 - c1 + 52'sd16384) >>> 15; ci_ <= (c2 + c3 + 52'sd16384) >>> 15;
                if ((((c0 - c1 + 52'sd16384) >>> 15) > 52'sd524287) || (((c0 - c1 + 52'sd16384) >>> 15) < -52'sd524288) || (((c2 + c3 + 52'sd16384) >>> 15) > 52'sd524287) || (((c2 + c3 + 52'sd16384) >>> 15) < -52'sd524288)) ovf <= 1'b1;
                st <= S_J5;
              end
      S_J5:   begin
                o0 <= zm_r[fl * 24 + j] * cr_; o1 <= zm_i[fl * 24 + j] * ci_; o2 <= zm_r[fl * 24 + j] * ci_; o3 <= zm_i[fl * 24 + j] * cr_; st <= S_J6;
              end
      S_J6:   begin
                fr <= (o0 - o1 + 64'sd8192) >>> 14; fi_ <= (o2 + o3 + 64'sd8192) >>> 14; st <= S_FWAIT;
              end
      S_FWAIT: begin
                // the checker: the expected index from the PRBS-15 (4 bits per symbol, in the order of the payload), the decision, the counters
                lvl_i <= slice2(fr); lvl_q <= slice2(fi_);
                pn = prbs; pb = 4'd0;
                for (q = 0; q < 4; q = q + 1) begin pb = {pb[2:0], pn[14]}; pn = {pn[13:0], pn[14] ^ pn[13]}; end
                exp_idx <= pb; prbs <= pn;
                o_valid <= 1'b1; o_idx <= fl * 24 + j; o_re <= fr; o_im <= fi_;
                st <= S_DONE;
              end
      S_DONE: begin
                dec_idx = {gray2(lvl_i), gray2(lvl_q)};
                sym_cnt <= sym_cnt + 32'd1;
                if (dec_idx != exp_idx) sym_err <= sym_err + 32'd1;
                bit_err <= bit_err + (dec_idx[0] ^ exp_idx[0]) + (dec_idx[1] ^ exp_idx[1]) + (dec_idx[2] ^ exp_idx[2]) + (dec_idx[3] ^ exp_idx[3]);
                sv_i = levv(lvl_i); sv_q = levv(lvl_q);
                e_i = fr - sv_i * 4096; e_q = fi_ - sv_q * 4096; sq_ref = (sv_i * sv_i + sv_q * sv_q) * 16777216;
                evm_err <= evm_err + e_i * e_i + e_q * e_q;
                evm_ref <= evm_ref + sq_ref;
                if (j == 5'd23) begin
                  if (fcount != 2'd0) begin fl <= fl + 6'd1; fcount <= fcount - 2'd1; st <= S_F0; end
                  else begin busy <= 1'b0; done <= 1'b1; st <= S_IDLE; end
                end else begin j <= j + 5'd1; st <= S_J0; end
              end
      default: st <= S_IDLE;
    endcase
  end
endmodule
