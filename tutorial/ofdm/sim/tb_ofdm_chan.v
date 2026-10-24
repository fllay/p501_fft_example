`timescale 1ns/1ps
// Testbench of ofdm_fft.v + ofdm_chan.v: per case the windows T1 and T2 (64 samples each) go through the FFT; the channel module copies A, then computes H, the noise and the weights.
module tb_ofdm_chan;
  reg clk = 0; always #5 clk = ~clk;
  reg start = 0, valid = 0; reg signed [15:0] xr = 0, xi = 0; reg cmd_a = 0, cmd_b = 0; reg [4:0] xa = 0;
  wire busy, done, ovf; wire signed [19:0] rr, ri; wire [5:0] ra;
  wire cbusy, cdone; wire [47:0] noise; wire signed [20:0] h_re, h_im; wire signed [31:0] w_re, w_im;
  ofdm_fft fft (.clk(clk), .start(start), .in_valid(valid), .in_re(xr), .in_im(xi), .busy(busy), .done(done), .ovf(ovf), .rd_addr(ra), .rd_re(rr), .rd_im(ri));
  ofdm_chan dut (.clk(clk), .cmd_a(cmd_a), .cmd_b(cmd_b), .rd_addr(ra), .rd_re(rr), .rd_im(ri), .busy(cbusy), .done(cdone), .noise(noise), .x_addr(xa), .h_re(h_re), .h_im(h_im), .w_re(w_re), .w_im(w_im));
  parameter NC = 200;
  reg [31:0] mem [0:128*NC-1];
  integer f, c, k, nc, w, nov; time tb0; reg first = 1; reg [1023:0] hexname;
  task run_fft(input integer base);
    begin
      @(posedge clk); #1 start = 1; @(posedge clk); #1 start = 0;
      for (k = 0; k < 64; k = k + 1) begin @(posedge clk); #1 valid = 1; xr = mem[base+k][15:0]; xi = mem[base+k][31:16]; end
      @(posedge clk); #1 valid = 0; wait (done); @(posedge clk); #1;
      if (ovf) nov = nov + 1;
    end
  endtask
  initial begin
    if (!$value$plusargs("hex=%s", hexname)) hexname = "chan_in.hex";
    if (!$value$plusargs("nc=%d", nc)) nc = NC;
    $readmemh(hexname, mem); f = $fopen("rtl_ofdm_chan.txt", "w"); nov = 0;
    #100;
    for (c = 0; c < nc; c = c + 1) begin
      run_fft(c * 128);
      @(posedge clk); #1 cmd_a = 1; @(posedge clk); #1 cmd_a = 0; wait (!cbusy); @(posedge clk); #1;
      run_fft(c * 128 + 64);
      @(posedge clk); #1 cmd_b = 1; tb0 = $time; @(posedge clk); #1 cmd_b = 0; wait (cdone); if (first) begin $display("clocks from cmd_b to done: %0d", ($time - tb0) / 10); first = 0; end @(posedge clk); #1;
      for (w = 0; w < 28; w = w + 1) begin xa = w; #1 $fwrite(f, "%0d %0d %0d %0d\n", h_re, h_im, w_re, w_im); end
      $fwrite(f, "%0d\n", noise);
    end
    $display("cases = %0d, FFT overflow flags = %0d", nc, nov);
    $fclose(f); $finish;
  end
endmodule
