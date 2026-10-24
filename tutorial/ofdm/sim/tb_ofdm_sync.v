`timescale 1ns/1ps
// Testbench of ofdm_detect.v: ADC samples from a hex file ({xq[15:0], xi[15:0]}), one every SPACING clocks; a log of every window and of the result.
module tb_ofdm_sync;
  reg clk = 0; always #5 clk = ~clk;
  reg run = 0, valid = 0; reg signed [11:0] xi = 0, xq = 0;
  wire found, late, w_pulse, w_cond; wire [31:0] o_n0, w_n; wire [6:0] o_first, o_last, o_pkidx; wire signed [31:0] o_s0, o_wc; wire [15:0] o_gain; wire [28:0] o_epk, w_e; wire signed [39:0] o_sr, o_si; wire [10:0] o_pk;
  wire signed [29:0] w_sr, w_si;
  ofdm_detect dut (.clk(clk), .run(run), .s_valid(valid), .xi(xi), .xq(xq), .r_thr(8'd166), .r_emin(8'd4), .r_target(16'd400), .found(found), .o_n0(o_n0), .o_first(o_first), .o_last(o_last), .o_pkidx(o_pkidx),
    .o_s0(o_s0), .o_wc(o_wc), .o_gain(o_gain), .o_epk(o_epk), .o_sr(o_sr), .o_si(o_si), .o_pk(o_pk), .late(late), .w_pulse(w_pulse), .w_n(w_n), .w_cond(w_cond), .w_sr(w_sr), .w_si(w_si), .w_e(w_e));
  parameter NS = 2000;
  reg [31:0] samples [0:NS-1];
  integer fw, fr, k, spacing, nsym, waited; reg [1023:0] hexname; reg got = 0;
  always @(posedge clk) if (w_pulse) $fwrite(fw, "%0d %0d %0d %0d %0d\n", w_n, w_cond, $signed(w_sr), $signed(w_si), w_e);
  always @(posedge clk) if (found) begin
    got <= 1;
    $fwrite(fr, "%0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d\n", o_n0, o_first, o_last, o_pkidx, $signed(o_s0), $signed(o_wc), o_gain, o_epk, $signed(o_sr), $signed(o_si), o_pk);
  end
  initial begin
    if (!$value$plusargs("hex=%s", hexname)) hexname = "sc_a.hex";
    if (!$value$plusargs("ns=%d", nsym)) nsym = NS;
    if (!$value$plusargs("sp=%d", spacing)) spacing = 26;
    $readmemh(hexname, samples);
    fw = $fopen("rtl_ofdm_win.txt", "w"); fr = $fopen("rtl_ofdm_res.txt", "w");
    #100 run = 1; #100;
    for (k = 0; k < nsym && !got; k = k + 1) begin
      @(posedge clk); #1 valid = 1; xi = samples[k][11:0]; xq = samples[k][27:16];
      @(posedge clk); #1 valid = 0;
      repeat (spacing - 2) @(posedge clk);
    end
    repeat (3000) @(posedge clk);
    $display("found = %0d", got); $display("late = %0d", late);
    $fclose(fw); $fclose(fr); $finish;
  end
endmodule
