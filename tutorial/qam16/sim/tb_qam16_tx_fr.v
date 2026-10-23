`timescale 1ns/1ps
// Testbench of qam16_tx_fr.v: the DAC samples of NS ce periods (ce every second clock like l_clk at 3.84 MSPS), logged for compare_tx.py.
module tb;
  parameter NS = 14000;
  reg clk = 0, resetn = 0, ce = 0, enable = 0; reg [15:0] amp = 16'h2000; reg [31:0] cfg = 0;
  wire [15:0] dac_i, dac_q;
  always #65 clk = ~clk;
  qam16_tx_fr dut (.clk(clk), .resetn(resetn), .ce(ce), .enable(enable), .amp(amp), .cfg(cfg), .dac_i(dac_i), .dac_q(dac_q));
  integer f, k, ampv;
  initial begin
    if ($value$plusargs("amp=%d", ampv)) amp = ampv;
    f = $fopen("rtl_tx16.txt", "w");
    #1000 resetn = 1; #1000 @(posedge clk); #1 enable = 1;
    for (k = 0; k < NS; k = k + 1) begin
      @(posedge clk); #1 ce = 1;
      @(posedge clk); #1 ce = 0;
      $fwrite(f, "%0d %0d\n", $signed(dac_i), $signed(dac_q));
    end
    $fclose(f); $finish;
  end
endmodule
