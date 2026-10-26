`timescale 1ns/1ps
// Whole-frame testbench of ofdm_rx.v: ADC samples from a hex file, one every 26 clocks; AXI-Lite writes and reads; per complete frame the registers and the corrected symbols are logged, at the end the capture RAM and H over AXI.
module tb_ofdm_rx;
  parameter STS = 0;                       // 0: Schmidl and Cox, 1: the 128-sample STS (xelab -generic_top STS=1)
  reg aclk = 0; always #5 aclk = ~aclk;
  reg aresetn = 0;
  reg [13:0] awaddr = 0, araddr = 0; reg awvalid = 0, wvalid = 0, arvalid = 0, bready = 1, rready = 1; reg [31:0] wdata = 0;
  wire awready, wready, bvalid, arvalid_o, arready, rvalid; wire [31:0] rdata; wire [1:0] bresp, rresp;
  reg adc_valid = 0; reg [15:0] adc_i = 0, adc_q = 0;
  ofdm_rx #(.STS(STS)) dut (.aclk(aclk), .aresetn(aresetn), .s_axi_awaddr(awaddr), .s_axi_awvalid(awvalid), .s_axi_awready(awready), .s_axi_wdata(wdata), .s_axi_wstrb(4'hF), .s_axi_wvalid(wvalid), .s_axi_wready(wready),
    .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready), .s_axi_araddr(araddr), .s_axi_arvalid(arvalid), .s_axi_arready(arready), .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(rready),
    .adc_clk(aclk), .adc_valid(adc_valid), .adc_i(adc_i), .adc_q(adc_q));
  task wr(input [13:0] ad, input [31:0] dd); begin
    @(posedge aclk); #1 awaddr = ad; wdata = dd; awvalid = 1; wvalid = 1; @(posedge aclk); #1 awvalid = 0; wvalid = 0; while (!bvalid) @(posedge aclk); end endtask
  task rd(input [13:0] ad, output [31:0] dd); begin
    @(posedge aclk); #1 araddr = ad; arvalid = 1; @(posedge aclk); while (!arready) @(posedge aclk); #1 arvalid = 0; while (!rvalid) @(posedge aclk); dd = rdata; @(posedge aclk); end endtask
  parameter NS = 9000;
  reg [31:0] samples [0:NS-1];
  integer f, k, ns, nf, i, j, kk; reg [1023:0] hexname; reg [31:0] v;
  reg signed [23:0] zb_r [0:1055], zb_i [0:1055]; reg [31:0] frames_q = 0; integer go = 0;
  always @(posedge aclk) if (dut.u_data.o_valid) begin zb_r[dut.u_data.o_idx] <= dut.u_data.o_re; zb_i[dut.u_data.o_idx] <= dut.u_data.o_im; end
  reg [4:0] cs_q = 0; always @(posedge aclk) begin cs_q <= dut.c_st; if (dut.c_st == 5'd4 && cs_q != 5'd4) $display("FINE: P=(%0d,%0d) e1=%0d e2=%0d pairs=%0d s0=%0d wc=%0d", dut.pr_acc, dut.pi_acc, dut.e1_acc, dut.e2_acc, dut.pair_cnt, dut.l_s0, $signed(dut.l_wc)); end
  // when a frame completes: log the registers and the symbols
  always @(posedge aclk) begin
    frames_q <= dut.frames;
    if (dut.frames != frames_q && dut.frames != 0) begin
      #20;
      $fwrite(f, "F%0d s0 %0d\nF%0d w_c %0d\nF%0d w_f %0d\nF%0d gain %0d\nF%0d noise %0d\nF%0d sym_cnt %0d\nF%0d sym_err %0d\nF%0d bit_err %0d\nF%0d evm_err %0d\nF%0d evm_ref %0d\n",
        dut.frames, dut.s0_last, dut.frames, $signed(dut.w_c_last), dut.frames, $signed(dut.w_f_last), dut.frames, dut.g_last, dut.frames, dut.ls_noise, dut.frames, dut.ls_cnt, dut.frames, dut.ls_err, dut.frames, dut.ls_bit, dut.frames, dut.ls_ee, dut.frames, dut.ls_er);
      $fwrite(f, "F%0d Z", dut.frames); for (kk = 0; kk < 1056; kk = kk + 1) $fwrite(f, " %0d %0d", zb_r[kk], zb_i[kk]); $fwrite(f, "\n");
    end
  end
  initial begin
    if (!$value$plusargs("hex=%s", hexname)) hexname = "frame_1.hex";
    if (!$value$plusargs("ns=%d", ns)) ns = NS;
    $readmemh(hexname, samples); f = $fopen("rtl_ofdm_rx.txt", "w");
    repeat (10) @(posedge aclk); aresetn = 1; repeat (5) @(posedge aclk);
    wr(14'h0004, 32'h7);                                   // CTRL: run, capture arm, continuous
    for (k = 0; k < ns; k = k + 1) begin
      @(posedge aclk); #1 adc_valid = 1; adc_i = samples[k][15:0]; adc_q = samples[k][31:16];
      @(posedge aclk); #1 adc_valid = 0;
      repeat (24) @(posedge aclk);
    end
    repeat (60000) @(posedge aclk);
    // registers over AXI
    rd(14'h0000, v); $fwrite(f, "AXI id %h\n", v);
    for (i = 8; i <= 32; i = i + 1) begin rd(i * 4, v); $fwrite(f, "AXI r%0d %0d\n", i, v); end
    // H over AXI
    $fwrite(f, "AXI H"); for (i = 0; i < 28; i = i + 1) begin rd(14'h2000 + i * 4, v); $fwrite(f, " %0d %0d", $signed(v[15:0]), $signed(v[31:16])); end $fwrite(f, "\n");
    $fwrite(f, "AXI CAP"); for (i = 0; i < 1024; i = i + 1) begin rd(14'h1000 + i * 4, v); $fwrite(f, " %0d %0d", $signed(v[15:0]), $signed(v[31:16])); end $fwrite(f, "\n");
    $display("frames = %0d, found = %0d, rejected = %0d, late = %0d", dut.frames, dut.n_found, dut.n_rej, dut.n_late);
    $fclose(f); $finish;
  end
endmodule
