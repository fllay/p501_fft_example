`timescale 1ns/1ps
module tb;
  localparam NS = 60000;                          // samples fed
  reg aclk = 0, adc_clk = 0, aresetn = 0;
  always #5 aclk = ~aclk;                         // 100 MHz
  always #65 adc_clk = ~adc_clk;                  // 7.69 MHz = l_clk at 3.84 MSPS (dac/adc valid every second clock)
  reg [13:0] awaddr = 0; reg awvalid = 0; reg [31:0] wdata = 0; reg wvalid = 0; wire awready, wready, bvalid; wire [1:0] bresp;
  reg [13:0] araddr = 0; reg arvalid = 0; wire arready, rvalid; wire [31:0] rdata; wire [1:0] rresp;
  reg adc_valid = 0; reg [15:0] adc_i = 0, adc_q = 0;
  qpsk_rx_fe dut (.aclk(aclk), .aresetn(aresetn), .s_axi_awaddr(awaddr), .s_axi_awvalid(awvalid), .s_axi_awready(awready), .s_axi_wdata(wdata), .s_axi_wstrb(4'hf), .s_axi_wvalid(wvalid),
    .s_axi_wready(wready), .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(1'b1), .s_axi_araddr(araddr), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
    .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(1'b1), .adc_clk(adc_clk), .adc_valid(adc_valid), .adc_i(adc_i), .adc_q(adc_q));
  reg [31:0] samples [0:NS-1];
  integer f, fy, fe, ff, k, nlog = 0;
  task wr(input [13:0] a, input [31:0] d); begin
    @(posedge aclk); awaddr <= a; wdata <= d; awvalid <= 1; wvalid <= 1;
    @(posedge aclk); while (!(awready && wready)) @(posedge aclk);
    awvalid <= 0; wvalid <= 0; @(posedge aclk); while (!bvalid) @(posedge aclk); end endtask
  task rd(input [13:0] a, output [31:0] d); begin
    @(posedge aclk); araddr <= a; arvalid <= 1; @(posedge aclk); while (!arready) @(posedge aclk);
    arvalid <= 0; while (!rvalid) @(posedge aclk); d = rdata; end endtask
  always @(posedge aclk) if (dut.sym_pulse) begin
    $fwrite(f, "%0d %0d %0d %0d %0d %0d %0d %0d\n", dut.bits2, $signed(dut.zi), $signed(dut.zq), $signed(dut.omega), $signed(dut.rate), dut.g, $signed(dut.e_t), $signed(dut.e_c));
    nlog = nlog + 1;
  end
  reg [31:0] v; integer tbv, gi, gp, f0, fllc;
  // the estimator: two windows, armed at symbol 6000 (N = 1024) and 11000 (N = 500); the registers are read when each window is done
  task wr2(input [13:0] a, input [31:0] d); begin
    @(posedge aclk); awaddr <= a; wdata <= d; awvalid <= 1; wvalid <= 1;
    @(posedge aclk); while (!(awready && wready)) @(posedge aclk);
    awvalid <= 0; wvalid <= 0; @(posedge aclk); while (!bvalid) @(posedge aclk); end endtask
  reg [31:0] r0, r1, r2, r3, r4, r5;
  task rd2(input [13:0] a, output [31:0] d); begin
    @(posedge aclk); araddr <= a; arvalid <= 1; @(posedge aclk); while (!arready) @(posedge aclk);
    arvalid <= 0; while (!rvalid) @(posedge aclk); d = rdata; end endtask
  task window(input integer start_sym, input integer n); begin
    wait (dut.n_sym >= start_sym);
    wr2(14'h078, n); wr2(14'h074, 32'h0); wr2(14'h074, 32'h1);
    repeat (20) @(posedge aclk);
    wait (dut.fe_done == 1'b1);
    repeat (4) @(posedge aclk);
    rd2(14'h080, r0); rd2(14'h084, r1); rd2(14'h088, r2); rd2(14'h08C, r3); rd2(14'h090, r4);
    $fwrite(ff, "%0d %0d %0d %0d %0d\n", r0, $signed(r1), $signed(r2), r3, r4);
    $display("window: cnt %0d  acc_re %0d  acc_im %0d  acc_abs %0d  first %0d", r0, $signed(r1), $signed(r2), r3, r4);
  end endtask
  initial begin
    wait (dut.aresetn == 1'b1 && dut.r_ctrl[0] == 1'b1);
    #1000;
    window(6000, 1024); window(11000, 500);
  end
  // the FLL stage: every derotated sample, and the error of every block (logged when it is handed to the derotator)
  always @(posedge aclk) if (dut.u_fll.d_we) $fwrite(fy, "%0d %0d\n", $signed(dut.u_fll.d_wdata[15:0]), $signed(dut.u_fll.d_wdata[31:16]));
  always @(posedge aclk) if (dut.u_fll.ms == 4'd10 && !dut.u_fll.pend_valid) $fwrite(fe, "%0d\n", $signed(dut.u_fll.e_q));
  initial begin
    $readmemh("../../p501_rx/sim/samples.hex", samples);
    f = $fopen("rtl_rx_out.txt", "w"); fy = $fopen("rtl_fll_y.txt", "w"); fe = $fopen("rtl_fll_e.txt", "w"); ff = $fopen("rtl_fe.txt", "w");
    #200 aresetn = 1; #100;
    rd(14'h000, v); $display("ID = %h", v);
    if ($value$plusargs("tb=%d", tbv)) wr(14'h00C, tbv);
    if ($value$plusargs("gi=%d", gi)) wr(14'h058, gi);
    if ($value$plusargs("gp=%d", gp)) wr(14'h05C, gp);
    if ($value$plusargs("fllc=%d", fllc)) wr(14'h054, fllc);   // FLL_CTRL: 0 holds the FLL (at F0)
    if ($value$plusargs("f0=%d", f0)) wr(14'h060, f0);       // optional: another timing integral gain (the narrow-loop test)
    wr(14'h004, 32'h1);                           // run
    #1000;
    for (k = 0; k < NS; k = k + 1) begin
      @(posedge adc_clk); #1 adc_valid = 1; adc_i = samples[k][15:0]; adc_q = samples[k][31:16];
      @(posedge adc_clk); #1 adc_valid = 0;
    end
    #20000;
    rd(14'h034, v); $display("symbols = %0d", v); rd(14'h038, v); $display("bits checked = %0d", v); rd(14'h03C, v); $display("mismatches = %0d", v); rd(14'h050, v); $display("overruns = %0d", v); rd(14'h064, v); $display("fll freq = %0d", $signed(v)); rd(14'h06C, v); $display("fll blocks = %0d", v); rd(14'h070, v); $display("fll late = %0d", v); rd(14'h068, v); $display("fll err = %0d", $signed(v));
    $fclose(f); $fclose(fy); $fclose(fe); $fclose(ff); $display("logged %0d symbols", nlog); $finish;
  end
endmodule
