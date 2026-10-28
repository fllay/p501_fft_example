// Testbench of rtl/ofdm_tx.v: l_clk 7.68 MHz with a ce every ce_div clocks (2 = 3.84 MS/s), fclk 100 MHz; logs the DAC values at every ce into tx_out.txt.
`timescale 1ns/1ps
module tb_ofdm_tx #(parameter STS = 0);
  reg clk = 0, fclk = 0, resetn = 0, fresetn = 0, enable = 0, ce = 0;
  reg [15:0] amp = 16'd32767;
  wire [15:0] dac_i, dac_q; wire [3:0] status;
  integer ce_div, nsamp, n, fd, cnt = 0, run_en = 0, ev_n = 0, ev_after = -1, ev_len = 0;
  always #65 clk = ~clk;
  always #5 fclk = ~fclk;
  ofdm_tx #(.STS(STS)) dut (.clk(clk), .resetn(resetn), .ce(ce), .enable(enable), .amp(amp), .cfg(32'd0), .dac_i(dac_i), .dac_q(dac_q), .fclk(fclk), .fresetn(fresetn), .status(status));
  always @(posedge clk) begin
    cnt <= cnt + 1;
    ce <= enable && ((cnt % ce_div) == 0);
  end
  always @(posedge clk) if (ce && run_en) begin
    $fdisplay(fd, "%0d %0d", $signed(dac_i), $signed(dac_q)); n = n + 1;
    if (n == nsamp) begin
      $display("samples %0d status %b", n, status); $fclose(fd); $finish;
    end
  end
  integer amp_i;
  initial begin
    if (!$value$plusargs("ce_div=%d", ce_div)) ce_div = 2;
    if (!$value$plusargs("n=%d", nsamp)) nsamp = 12000;
    if ($value$plusargs("amp=%d", amp_i)) amp = amp_i;
    fd = $fopen("tx_out.txt", "w"); n = 0;
    #1000 resetn = 1; fresetn = 1;
    #2000 enable = 1; run_en = 1;
    #200000000 $display("timeout"); $finish;
  end
endmodule
