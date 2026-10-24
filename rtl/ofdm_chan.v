// Channel estimate of the OFDM receiver (bit-exact: tutorial/ofdm/ofdm_fixed.py, the "channel" block of receive_fixed):
//   cmd_a: copy the 28 used bins of the FFT RAM (the training symbol T1) into A.   cmd_b: the same bins of T2 (B) are read from the FFT RAM, then for every used subcarrier i
//   s = A + B, d = A - B;  u = sr s_r + si s_i, v = sr s_i - si s_r  (sr, si = +-1: the signs of the QPSK training value);  H_r = ((((u 181 + 128) >> 8) + 1) >> 1), H_i likewise from v
//   noise = sum of d_r^2 + d_i^2;  weights  W = conj(H) K / |H|^2 with K = R 2^14 (R = 12953, unit RMS), rounded half away from zero (a restoring divider, 50 clocks per quotient), W = 0 where H = 0.
// The index i = 0 .. 27 runs over k = -14 .. -1, 1 .. 14. h_*, w_* are read ports (asynchronous) for the next stages. About 28 x 6 + 28 x 110 clocks after cmd_b.
`timescale 1ns/1ps
module ofdm_chan (
  input  wire        clk,
  input  wire        cmd_a, cmd_b,
  output wire [5:0]  rd_addr,
  input  wire signed [19:0] rd_re, rd_im,
  output reg         busy, done,
  output reg  [47:0] noise,
  input  wire [4:0]  x_addr,
  output wire signed [20:0] h_re, h_im,
  output wire signed [31:0] w_re, w_im
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
  function [1:0] sgn_of(input [4:0] i);                // {sr > 0, si > 0}
    case (i)
      5'd0: sgn_of = 2'b10;
      5'd1: sgn_of = 2'b00;
      5'd2: sgn_of = 2'b10;
      5'd3: sgn_of = 2'b10;
      5'd4: sgn_of = 2'b01;
      5'd5: sgn_of = 2'b00;
      5'd6: sgn_of = 2'b10;
      5'd7: sgn_of = 2'b11;
      5'd8: sgn_of = 2'b10;
      5'd9: sgn_of = 2'b01;
      5'd10: sgn_of = 2'b11;
      5'd11: sgn_of = 2'b00;
      5'd12: sgn_of = 2'b10;
      5'd13: sgn_of = 2'b11;
      5'd14: sgn_of = 2'b10;
      5'd15: sgn_of = 2'b01;
      5'd16: sgn_of = 2'b11;
      5'd17: sgn_of = 2'b00;
      5'd18: sgn_of = 2'b10;
      5'd19: sgn_of = 2'b10;
      5'd20: sgn_of = 2'b11;
      5'd21: sgn_of = 2'b11;
      5'd22: sgn_of = 2'b11;
      5'd23: sgn_of = 2'b10;
      5'd24: sgn_of = 2'b01;
      5'd25: sgn_of = 2'b00;
      5'd26: sgn_of = 2'b01;
      5'd27: sgn_of = 2'b00;
      default: sgn_of = 2'b00;
    endcase
  endfunction
  reg signed [19:0] a_r [0:27], a_i [0:27];
  reg signed [20:0] hm_r [0:27], hm_i [0:27];
  reg signed [31:0] wm_r [0:27], wm_i [0:27];
  assign h_re = hm_r[x_addr]; assign h_im = hm_i[x_addr]; assign w_re = wm_r[x_addr]; assign w_im = wm_i[x_addr];
  reg [4:0] idx;
  assign rd_addr = bin_of(idx);
  localparam [3:0] S_IDLE = 0, S_A = 1, S_B1 = 2, S_B2 = 3, S_B3 = 4, S_B4 = 5, S_B5 = 6, S_W1 = 7, S_W2 = 8, S_W3 = 9, S_DIV = 10, S_DFIN = 11, S_WST = 12;
  reg [3:0] st;
  reg signed [19:0] ar, ai, br, bi;
  reg signed [20:0] s_r, s_i, d_r, d_i;
  reg signed [21:0] u, v;
  reg [41:0] pd_r, pd_i;
  reg signed [30:0] hu, hv;
  reg signed [20:0] hr, hi;
  reg [41:0] den; reg signed [49:0] nr, ni;
  reg [49:0] mag; reg [43:0] rem; reg [49:0] q; reg [5:0] it; reg neg; reg second; reg [41:0] dd;
  wire [1:0] sg = sgn_of(idx);
  wire [43:0] rem_sh = {rem[42:0], mag[49]};
  initial begin st = S_IDLE; busy = 0; done = 0; noise = 0; end
  always @(posedge clk) begin
    done <= 1'b0;
    case (st)
      S_IDLE: begin
                if (cmd_a) begin idx <= 5'd0; busy <= 1'b1; st <= S_A; end
                else if (cmd_b) begin idx <= 5'd0; busy <= 1'b1; noise <= 48'd0; st <= S_B1; end
              end
      S_A:    begin
                a_r[idx] <= rd_re; a_i[idx] <= rd_im;
                if (idx == 5'd27) begin busy <= 1'b0; st <= S_IDLE; end else idx <= idx + 5'd1;
              end
      S_B1:   begin ar <= a_r[idx]; ai <= a_i[idx]; br <= rd_re; bi <= rd_im; st <= S_B2; end
      S_B2:   begin s_r <= ar + br; s_i <= ai + bi; d_r <= ar - br; d_i <= ai - bi; st <= S_B3; end
      S_B3:   begin
                u <= (sg[1] ? s_r : -s_r) + (sg[0] ? s_i : -s_i);
                v <= (sg[1] ? s_i : -s_i) - (sg[0] ? s_r : -s_r);
                pd_r <= d_r * d_r; pd_i <= d_i * d_i; st <= S_B4;
              end
      S_B4:   begin
                noise <= noise + pd_r + pd_i;
                hu <= u * 31'sd181 + 31'sd128; hv <= v * 31'sd181 + 31'sd128; st <= S_B5;
              end
      S_B5:   begin
                hm_r[idx] <= (((hu >>> 8) + 31'sd1) >>> 1); hm_i[idx] <= (((hv >>> 8) + 31'sd1) >>> 1);
                if (idx == 5'd27) begin idx <= 5'd0; st <= S_W1; end else begin idx <= idx + 5'd1; st <= S_B1; end
              end
      S_W1:   begin hr <= hm_r[idx]; hi <= hm_i[idx]; st <= S_W2; end
      S_W2:   begin den <= hr * hr + hi * hi; nr <= hr * KK; ni <= -hi * KK; st <= S_W3; end
      S_W3:   begin
                if (den == 0) begin wm_r[idx] <= 32'sd0; wm_i[idx] <= 32'sd0; st <= S_WST; end
                else begin
                  dd <= den; second <= 1'b0; mag <= nr[49] ? -nr : nr; neg <= nr[49]; rem <= 44'd0; q <= 50'd0; it <= 6'd0; st <= S_DIV;
                end
              end
      S_DIV:  begin
                // restoring division of the 50-bit magnitude by dd, most significant bit first
                if (rem_sh >= {2'd0, dd}) begin rem <= rem_sh - {2'd0, dd}; q <= {q[48:0], 1'b1}; end
                else begin rem <= rem_sh; q <= {q[48:0], 1'b0}; end
                mag <= {mag[48:0], 1'b0}; it <= it + 6'd1;
                if (it == 6'd49) st <= S_DFIN;
              end
      S_DFIN: begin
                // round half away from zero: q + (2 rem >= dd), then the sign
                if (!second) begin wm_r[idx] <= neg ? -$signed(q[31:0] + (({rem, 1'b0} >= {3'd0, dd}) ? 32'd1 : 32'd0)) : $signed(q[31:0] + (({rem, 1'b0} >= {3'd0, dd}) ? 32'd1 : 32'd0));
                                   second <= 1'b1; mag <= ni[49] ? -ni : ni; neg <= ni[49]; rem <= 44'd0; q <= 50'd0; it <= 6'd0; st <= S_DIV; end
                else begin wm_i[idx] <= neg ? -$signed(q[31:0] + (({rem, 1'b0} >= {3'd0, dd}) ? 32'd1 : 32'd0)) : $signed(q[31:0] + (({rem, 1'b0} >= {3'd0, dd}) ? 32'd1 : 32'd0)); st <= S_WST; end
              end
      S_WST:  begin
                if (idx == 5'd27) begin busy <= 1'b0; done <= 1'b1; st <= S_IDLE; end else begin idx <= idx + 5'd1; st <= S_W1; end
              end
      default: st <= S_IDLE;
    endcase
  end
endmodule
