`timescale 1ns/1ps
module tb;
  reg clk = 0, resetn = 0, ce = 0, enable = 0; reg [15:0] amp = 16'h4000; reg [31:0] cfg = 32'd0;
  wire signed [15:0] di, dq;
  qpsk_tx_fr dut (.clk(clk), .resetn(resetn), .ce(ce), .enable(enable), .amp(amp), .cfg(cfg), .dac_i(di), .dac_q(dq));
  always #5 clk = ~clk;
  integer k, f, c;
  initial begin
    if ($value$plusargs("cfg=%d", c)) cfg = c;
    f = $fopen("rtl_tx_fr.txt", "w");
    #100 resetn = 1; #100 enable = 1;
    for (k = 0; k < 12000; k = k + 1) begin
      @(posedge clk); #1 ce = 1;
      @(posedge clk); #1 $fwrite(f, "%0d %0d\n", di, dq); ce = 0;
      @(posedge clk);
    end
    $fclose(f); $finish;
  end
endmodule
