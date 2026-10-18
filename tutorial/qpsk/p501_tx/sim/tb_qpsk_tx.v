`timescale 1ns/1ps
module tb;
  reg clk = 0, resetn = 0, ce = 0, enable = 0; reg [15:0] amp = 16'h4000;
  wire signed [15:0] di, dq;
  qpsk_tx dut (.clk(clk), .resetn(resetn), .ce(ce), .enable(enable), .amp(amp), .dac_i(di), .dac_q(dq));
  always #5 clk = ~clk;
  integer k, f;
  initial begin
    f = $fopen("rtl_out.txt", "w");
    #100 resetn = 1; #100 enable = 1;
    for (k = 0; k < 4000; k = k + 1) begin
      @(posedge clk); #1 ce = 1;                  // one ce pulse every 2nd clock, like dac_valid in 1R1T
      @(posedge clk); #1 $fwrite(f, "%0d %0d\n", di, dq); ce = 0;     // di/dq after the clock edge that took the ce
      @(posedge clk);
    end
    $fclose(f); $finish;
  end
endmodule
