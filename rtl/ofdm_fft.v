// 64-point FFT of the OFDM receiver: radix-2 decimation in time, ONE butterfly, in place in a 64 x 2 x 20-bit RAM; bit-exact with tutorial/ofdm/ofdm_fixed.py, fft64.
//   input   64 complex samples (16 bit signed) written in bit-reversed order, one per clock or slower (in_valid); the first after `start`
//   compute 6 stages x 32 butterflies, 4 clocks each: t = (b w + 2^14) >> 15 (w = exp(-j 2 pi k / 64), Q15), a' = a + t, b' = a - t. No scaling: the data path is 20 bits, `ovf` (sticky until `start`) flags a result outside it.
//   output  the 64 bins in natural order in the RAM, read with rd_addr (asynchronous read) while `done` is high / after it; 64 + 768 clocks from start to done.
`timescale 1ns/1ps
module ofdm_fft (
  input  wire        clk,
  input  wire        start,                 // pulse: the next in_valid sample is sample 0
  input  wire        in_valid,
  input  wire signed [15:0] in_re, in_im,
  output reg         busy,
  output reg         done,                  // pulse when the transform is complete
  output reg         ovf,
  input  wire [5:0]  rd_addr,
  output wire signed [19:0] rd_re, rd_im
);
  reg signed [19:0] ram_r [0:63], ram_i [0:63];
  reg [6:0]  nin;
  reg        loading;
  reg [2:0]  stg;                           // stage 0 .. 5
  reg [5:0]  bf;                            // butterfly 0 .. 31 (5 bits used)
  reg [2:0]  ph;
  reg signed [19:0] a_r, a_i, b_r, b_i; reg signed [15:0] w_r, w_i;
  reg signed [35:0] m0, m1, m2, m3;
  reg signed [19:0] t_r, t_i;
  wire [5:0] half  = 6'd1 << stg;
  wire [5:0] j     = bf[4:0] & (half - 6'd1);
  wire [5:0] i1    = ((bf >> stg) << (stg + 3'd1)) | j;
  wire [5:0] i2    = i1 | half;
  wire [4:0] twi   = j[4:0] << (3'd5 - stg);
  reg signed [15:0] twr, twi_v;
  function [5:0] bitrev6(input [5:0] v); bitrev6 = {v[0], v[1], v[2], v[3], v[4], v[5]}; endfunction
  always @* begin
    case (twi)
      5'd0: twr = 16'sd32767;
      5'd1: twr = 16'sd32609;
      5'd2: twr = 16'sd32137;
      5'd3: twr = 16'sd31356;
      5'd4: twr = 16'sd30273;
      5'd5: twr = 16'sd28898;
      5'd6: twr = 16'sd27245;
      5'd7: twr = 16'sd25329;
      5'd8: twr = 16'sd23170;
      5'd9: twr = 16'sd20787;
      5'd10: twr = 16'sd18204;
      5'd11: twr = 16'sd15446;
      5'd12: twr = 16'sd12539;
      5'd13: twr = 16'sd9512;
      5'd14: twr = 16'sd6393;
      5'd15: twr = 16'sd3212;
      5'd16: twr = 16'sd0;
      5'd17: twr = -16'sd3212;
      5'd18: twr = -16'sd6393;
      5'd19: twr = -16'sd9512;
      5'd20: twr = -16'sd12539;
      5'd21: twr = -16'sd15446;
      5'd22: twr = -16'sd18204;
      5'd23: twr = -16'sd20787;
      5'd24: twr = -16'sd23170;
      5'd25: twr = -16'sd25329;
      5'd26: twr = -16'sd27245;
      5'd27: twr = -16'sd28898;
      5'd28: twr = -16'sd30273;
      5'd29: twr = -16'sd31356;
      5'd30: twr = -16'sd32137;
      5'd31: twr = -16'sd32609;
      default: twr = 16'sd0;
    endcase
  end
  always @* begin
    case (twi)
      5'd0: twi_v = 16'sd0;
      5'd1: twi_v = -16'sd3212;
      5'd2: twi_v = -16'sd6393;
      5'd3: twi_v = -16'sd9512;
      5'd4: twi_v = -16'sd12539;
      5'd5: twi_v = -16'sd15446;
      5'd6: twi_v = -16'sd18204;
      5'd7: twi_v = -16'sd20787;
      5'd8: twi_v = -16'sd23170;
      5'd9: twi_v = -16'sd25329;
      5'd10: twi_v = -16'sd27245;
      5'd11: twi_v = -16'sd28898;
      5'd12: twi_v = -16'sd30273;
      5'd13: twi_v = -16'sd31356;
      5'd14: twi_v = -16'sd32137;
      5'd15: twi_v = -16'sd32609;
      5'd16: twi_v = -16'sd32767;
      5'd17: twi_v = -16'sd32609;
      5'd18: twi_v = -16'sd32137;
      5'd19: twi_v = -16'sd31356;
      5'd20: twi_v = -16'sd30273;
      5'd21: twi_v = -16'sd28898;
      5'd22: twi_v = -16'sd27245;
      5'd23: twi_v = -16'sd25329;
      5'd24: twi_v = -16'sd23170;
      5'd25: twi_v = -16'sd20787;
      5'd26: twi_v = -16'sd18204;
      5'd27: twi_v = -16'sd15446;
      5'd28: twi_v = -16'sd12539;
      5'd29: twi_v = -16'sd9512;
      5'd30: twi_v = -16'sd6393;
      5'd31: twi_v = -16'sd3212;
      default: twi_v = 16'sd0;
    endcase
  end
  assign rd_re = ram_r[rd_addr];
  assign rd_im = ram_i[rd_addr];
  wire signed [21:0] s_ar = a_r + t_r, s_ai = a_i + t_i, d_ar = a_r - t_r, d_ai = a_i - t_i;
  initial begin busy = 0; done = 0; ovf = 0; loading = 0; ph = 0; nin = 0; end
  always @(posedge clk) begin
    done <= 1'b0;
    if (start) begin loading <= 1'b1; nin <= 7'd0; busy <= 1'b1; ovf <= 1'b0; end
    else if (loading && in_valid) begin
      ram_r[bitrev6(nin[5:0])] <= {{4{in_re[15]}}, in_re}; ram_i[bitrev6(nin[5:0])] <= {{4{in_im[15]}}, in_im};
      nin <= nin + 7'd1;
      if (nin == 7'd63) begin loading <= 1'b0; stg <= 3'd0; bf <= 6'd0; ph <= 3'd0; end
    end else if (busy && !loading) begin
      case (ph)
        3'd0: begin a_r <= ram_r[i1]; a_i <= ram_i[i1]; b_r <= ram_r[i2]; b_i <= ram_i[i2]; w_r <= twr; w_i <= twi_v; ph <= 3'd1; end
        3'd1: begin m0 <= b_r * w_r; m1 <= b_i * w_i; m2 <= b_r * w_i; m3 <= b_i * w_r; ph <= 3'd2; end
        3'd2: begin t_r <= (m0 - m1 + 36'sd16384) >>> 15; t_i <= (m2 + m3 + 36'sd16384) >>> 15; ph <= 3'd3; end
        3'd3: begin
                ram_r[i1] <= s_ar[19:0]; ram_i[i1] <= s_ai[19:0]; ram_r[i2] <= d_ar[19:0]; ram_i[i2] <= d_ai[19:0];
                if (s_ar > 22'sd524287 || s_ar < -22'sd524288 || s_ai > 22'sd524287 || s_ai < -22'sd524288 || d_ar > 22'sd524287 || d_ar < -22'sd524288 || d_ai > 22'sd524287 || d_ai < -22'sd524288) ovf <= 1'b1;
                ph <= 3'd0;
                if (bf == 6'd31) begin
                  bf <= 6'd0;
                  if (stg == 3'd5) begin busy <= 1'b0; done <= 1'b1; end else stg <= stg + 3'd1;
                end else bf <= bf + 6'd1;
              end
        default: ph <= 3'd0;
      endcase
    end
  end
endmodule
