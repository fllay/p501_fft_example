// Vectoring CORDIC for the OFDM receiver: atan2(im, re) in turns x 2^20 (mod 2^20), bit-exact with qam_zc_fixed.cordic_turns20 (the CORDIC of rtl/qpsk_sync.v):
// the inputs are reduced to 24 bit signed by a common right shift, then 18 iterations. About 22 clocks.
`timescale 1ns/1ps
module ofdm_cordic (
  input  wire        clk,
  input  wire        start,
  input  wire signed [39:0] re, im,
  output reg         done,
  output reg  [19:0] ang
);
  localparam [2:0] C_IDLE = 0, C_SH = 1, C_PRE = 2, C_IT = 3;
  reg [2:0]  st = C_IDLE;
  reg signed [39:0] in_re, in_im;
  reg signed [27:0] cx, cy;
  reg [4:0]  it;
  reg [5:0]  sh;
  function [5:0] bitlen(input [39:0] v);
    integer i;
    begin bitlen = 6'd0; for (i = 0; i < 40; i = i + 1) if (v[i]) bitlen = i + 1; end
  endfunction
  function [19:0] atab(input [4:0] i);
    case (i)
      5'd0: atab = 20'd131072; 5'd1: atab = 20'd77376; 5'd2: atab = 20'd40884; 5'd3: atab = 20'd20753; 5'd4: atab = 20'd10417; 5'd5: atab = 20'd5213;
      5'd6: atab = 20'd2607; 5'd7: atab = 20'd1304; 5'd8: atab = 20'd652; 5'd9: atab = 20'd326; 5'd10: atab = 20'd163; 5'd11: atab = 20'd81;
      5'd12: atab = 20'd41; 5'd13: atab = 20'd20; 5'd14: atab = 20'd10; 5'd15: atab = 20'd5; 5'd16: atab = 20'd3; default: atab = 20'd1;
    endcase
  endfunction
  wire [39:0] ar = in_re[39] ? -in_re : in_re, ai = in_im[39] ? -in_im : in_im;
  wire [5:0]  bl = bitlen(ar | ai);
  wire signed [39:0] sre = in_re >>> sh, sim = in_im >>> sh;
  wire signed [27:0] cysh = cy >>> it, cxsh = cx >>> it;
  always @(posedge clk) begin
    done <= 1'b0;
    case (st)
      C_IDLE: if (start) begin in_re <= re; in_im <= im; st <= C_SH; end
      C_SH:   begin sh <= (bl > 6'd23) ? (bl - 6'd23) : 6'd0; st <= C_PRE; end
      C_PRE:  begin
                if (sre < 0) begin cx <= -sre[27:0]; cy <= -sim[27:0]; ang <= 20'h80000; end
                else         begin cx <= sre[27:0];  cy <= sim[27:0];  ang <= 20'd0; end
                it <= 5'd0; st <= C_IT;
              end
      C_IT:   begin
                if (!cy[27]) begin cx <= cx + cysh; cy <= cy - cxsh; ang <= ang + atab(it); end
                else         begin cx <= cx - cysh; cy <= cy + cxsh; ang <= ang - atab(it); end
                it <= it + 5'd1;
                if (it == 5'd17) begin st <= C_IDLE; done <= 1'b1; end
              end
      default: st <= C_IDLE;
    endcase
  end
endmodule
