`timescale 1ns/1ps
// Testbench of ofdm_fft.v: transforms from fft_in.hex (64 samples each, {im, re}); the 64 bins of each are logged after `done`.
module tb_ofdm_fft;
  reg clk = 0; always #5 clk = ~clk;
  reg start = 0, valid = 0; reg signed [15:0] xr = 0, xi = 0; reg [5:0] ra = 0;
  wire busy, done, ovf; wire signed [19:0] rr, ri;
  ofdm_fft dut (.clk(clk), .start(start), .in_valid(valid), .in_re(xr), .in_im(xi), .busy(busy), .done(done), .ovf(ovf), .rd_addr(ra), .rd_re(rr), .rd_im(ri));
  parameter NT = 400;
  reg [31:0] mem [0:64*NT-1];
  integer f, t, k, nt, gap, nov; time t_start, t_done; reg first = 1; reg [1023:0] hexname;
  initial begin
    if (!$value$plusargs("hex=%s", hexname)) hexname = "fft_in.hex";
    if (!$value$plusargs("nt=%d", nt)) nt = NT;
    if (!$value$plusargs("gap=%d", gap)) gap = 1;
    $readmemh(hexname, mem); f = $fopen("rtl_ofdm_fft.txt", "w"); nov = 0;
    #100;
    for (t = 0; t < nt; t = t + 1) begin
      @(posedge clk); #1 start = 1; t_start = $time; @(posedge clk); #1 start = 0;
      for (k = 0; k < 64; k = k + 1) begin
        @(posedge clk); #1 valid = 1; xr = mem[t*64+k][15:0]; xi = mem[t*64+k][31:16];
        if (gap > 1) begin @(posedge clk); #1 valid = 0; repeat (gap - 2) @(posedge clk); end
      end
      @(posedge clk); #1 valid = 0;
      wait (done); t_done = $time; if (first) begin $display("clocks from start to done (input at gap %0d): %0d", gap, (t_done - t_start) / 10); first = 0; end @(posedge clk); #1;
      if (ovf) nov = nov + 1;
      for (k = 0; k < 64; k = k + 1) begin ra = k; #1 $fwrite(f, "%0d %0d\n", rr, ri); end
    end
    $display("transforms = %0d, with overflow flag = %0d", nt, nov);
    $fclose(f); $finish;
  end
endmodule
