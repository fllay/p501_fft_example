// Signed / unsigned restoring divider of the OFDM receiver: q = round(num / den) with the rounding half away from zero (ofdm_fixed.rdiv), den > 0.
// 50-bit numerator, 42-bit denominator, 32-bit quotient (|q| < 2^31 is the user's responsibility: the weights are bounded by K = R 2^14 < 2^28). 54 clocks.
`timescale 1ns/1ps
module ofdm_div (
  input  wire        clk,
  input  wire        start,
  input  wire signed [49:0] num,
  input  wire [41:0] den,
  output reg         done,
  output reg  signed [31:0] q
);
  reg [49:0] mag; reg [43:0] rem; reg [49:0] qq; reg [5:0] it; reg neg, busy; reg [41:0] dd;
  wire [43:0] rem_sh = {rem[42:0], mag[49]};
  wire [31:0] qr = qq[31:0] + (({rem, 1'b0} >= {3'd0, dd}) ? 32'd1 : 32'd0);
  initial begin busy = 0; done = 0; end
  always @(posedge clk) begin
    done <= 1'b0;
    if (start && !busy) begin mag <= num[49] ? -num : num; neg <= num[49]; dd <= den; rem <= 44'd0; qq <= 50'd0; it <= 6'd0; busy <= 1'b1; end
    else if (busy) begin
      if (it == 6'd50) begin q <= neg ? -$signed(qr) : $signed(qr); done <= 1'b1; busy <= 1'b0; end
      else begin
        if (rem_sh >= {2'd0, dd}) begin rem <= rem_sh - {2'd0, dd}; qq <= {qq[48:0], 1'b1}; end
        else begin rem <= rem_sh; qq <= {qq[48:0], 1'b0}; end
        mag <= {mag[48:0], 1'b0}; it <= it + 6'd1;
      end
    end
  end
endmodule
