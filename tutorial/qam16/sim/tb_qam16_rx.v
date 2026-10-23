`timescale 1ns/1ps
// Testbench of qam16_rx.v: ADC samples from a hex file at 3.84 MSPS, the registers from rx_regs.txt, logs of the front end, the engine and the applied events.
module tb;
  parameter NS = 200000;
  reg aclk = 0, adc_clk = 0, aresetn = 0;
  always #5 aclk = ~aclk;
  always #65 adc_clk = ~adc_clk;
  reg [13:0] awaddr = 0; reg awvalid = 0; reg [31:0] wdata = 0; reg wvalid = 0; wire awready, wready, bvalid; wire [1:0] bresp;
  reg [13:0] araddr = 0; reg arvalid = 0; wire arready, rvalid; wire [31:0] rdata; wire [1:0] rresp;
  reg adc_valid = 0; reg [15:0] adc_i = 0, adc_q = 0;
  qam16_rx dut (.aclk(aclk), .aresetn(aresetn), .s_axi_awaddr(awaddr), .s_axi_awvalid(awvalid), .s_axi_awready(awready), .s_axi_wdata(wdata), .s_axi_wstrb(4'hf), .s_axi_wvalid(wvalid),
    .s_axi_wready(wready), .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(1'b1), .s_axi_araddr(araddr), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
    .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(1'b1), .adc_clk(adc_clk), .adc_valid(adc_valid), .adc_i(adc_i), .adc_q(adc_q));
  reg [31:0] samples [0:NS-1];
  integer ff, fe, fv, k, nsamp, code, a, d; reg [1023:0] hexname; reg [31:0] v;
  task wr(input [13:0] ad, input [31:0] dd); begin
    @(posedge aclk); awaddr <= ad; wdata <= dd; awvalid <= 1; wvalid <= 1;
    @(posedge aclk); while (!(awready && wready)) @(posedge aclk);
    awvalid <= 0; wvalid <= 0; @(posedge aclk); while (!bvalid) @(posedge aclk); end endtask
  task rd(input [13:0] ad, output [31:0] dd); begin
    @(posedge aclk); araddr <= ad; arvalid <= 1; @(posedge aclk); while (!arready) @(posedge aclk);
    arvalid <= 0; while (!rvalid) @(posedge aclk); dd = rdata; end endtask
  // front end and engine, once per symbol (state S11 = 14)
  always @(posedge aclk) if (dut.st == 5'd14) begin
    $fwrite(ff, "%0d %0d %0d %0d %0d %0d\n", dut.n_sym, $signed(dut.mi2), $signed(dut.mq2), dut.g, $signed(dut.rate), $signed(dut.e_t));
    if (dut.proc) $fwrite(fe, "%0d %0d %0d %0d %0d %0d %0d %0d\n", $signed(dut.n_sym) - 10, dut.pos, dut.kind, $signed(dut.zi), $signed(dut.zq), $signed(dut.e_c), $signed(dut.omega), dut.theta);
  end
  always @(posedge aclk) if (dut.st == 5'd8 && dut.ev_due) $fwrite(fv, "%0d %0d %0d %0d\n", dut.n_sym, dut.ev_kind, dut.ev_e, dut.ev_known);
  initial begin
    if (!$value$plusargs("hex=%s", hexname)) hexname = "rx_a.hex";
    if (!$value$plusargs("ns=%d", nsamp)) nsamp = NS;
    $readmemh(hexname, samples);
    ff = $fopen("rtl_rx_front.txt", "w"); fe = $fopen("rtl_rx_engine.txt", "w"); fv = $fopen("rtl_rx_events.txt", "w");
    #200 aresetn = 1; #100;
    rd(14'h000, v); $display("ID = %h", v);
    a = $fopen("rx_regs.txt", "r");
    while (!$feof(a)) begin code = $fscanf(a, "%h %h\n", d, v); if (code == 2) wr(d[13:0], v); end
    $fclose(a);
    wr(14'h004, 32'h1);
    #1000;
    for (k = 0; k < nsamp; k = k + 1) begin
      @(posedge adc_clk); #1 adc_valid = 1; adc_i = samples[k][15:0]; adc_q = samples[k][31:16];
      @(posedge adc_clk); #1 adc_valid = 0;
    end
    #20000;
    rd(14'h054, v); $display("symbols = %0d", v); rd(14'h058, v); $display("frames = %0d", v); rd(14'h05C, v); $display("symerr = %0d", v); rd(14'h060, v); $display("biterr = %0d", v);
    rd(14'h064, v); $display("symcnt = %0d", v); rd(14'h068, v); $display("bad = %0d", v); rd(14'h06C, v); $display("evmlo = %0d", v); rd(14'h070, v); $display("evmhi = %0d", v);
    rd(14'h074, v); $display("evmref = %0d", v); rd(14'h078, v); $display("frerr = %0d", v); rd(14'h08C, v); $display("overruns = %0d", v); rd(14'h090, v); $display("npeak = %0d", v);
    rd(14'h094, v); $display("nlock = %0d", v); rd(14'h098, v); $display("nhit = %0d", v); rd(14'h09C, v); $display("nmiss = %0d", v); rd(14'h0A0, v); $display("nlost = %0d", v);
    rd(14'h0A4, v); $display("sylate = %0d", v); rd(14'h0A8, v); $display("evover = %0d", v); rd(14'h0AC, v); $display("evlate = %0d", v); rd(14'h0B0, v); $display("lockw = %0d", $signed(v));
    $fclose(ff); $fclose(fe); $fclose(fv); $finish;
  end
endmodule
