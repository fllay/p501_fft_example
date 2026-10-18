`timescale 1ns/1ps
module tb;
  localparam NS = 60000;                          // samples fed
  reg aclk = 0, adc_clk = 0, aresetn = 0;
  always #5 aclk = ~aclk;                         // 100 MHz
  always #65 adc_clk = ~adc_clk;                  // 7.69 MHz = l_clk at 3.84 MSPS (dac/adc valid every second clock)
  reg [13:0] awaddr = 0; reg awvalid = 0; reg [31:0] wdata = 0; reg wvalid = 0; wire awready, wready, bvalid; wire [1:0] bresp;
  reg [13:0] araddr = 0; reg arvalid = 0; wire arready, rvalid; wire [31:0] rdata; wire [1:0] rresp;
  reg adc_valid = 0; reg [15:0] adc_i = 0, adc_q = 0;
  qpsk_rx dut (.aclk(aclk), .aresetn(aresetn), .s_axi_awaddr(awaddr), .s_axi_awvalid(awvalid), .s_axi_awready(awready), .s_axi_wdata(wdata), .s_axi_wstrb(4'hf), .s_axi_wvalid(wvalid),
    .s_axi_wready(wready), .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(1'b1), .s_axi_araddr(araddr), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
    .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(1'b1), .adc_clk(adc_clk), .adc_valid(adc_valid), .adc_i(adc_i), .adc_q(adc_q));
  reg [31:0] samples [0:NS-1];
  integer f, k, nlog = 0;
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
  reg [31:0] v; integer tbv;
  initial begin
    $readmemh("samples.hex", samples);
    f = $fopen("rtl_rx_out.txt", "w");
    #200 aresetn = 1; #100;
    rd(14'h000, v); $display("ID = %h", v);
    if ($value$plusargs("tb=%d", tbv)) wr(14'h00C, tbv);       // optional: another timing integral gain (the narrow-loop test)
    wr(14'h004, 32'h1);                           // run
    #1000;
    for (k = 0; k < NS; k = k + 1) begin
      @(posedge adc_clk); #1 adc_valid = 1; adc_i = samples[k][15:0]; adc_q = samples[k][31:16];
      @(posedge adc_clk); #1 adc_valid = 0;
    end
    #20000;
    rd(14'h034, v); $display("symbols = %0d", v); rd(14'h038, v); $display("bits checked = %0d", v); rd(14'h03C, v); $display("mismatches = %0d", v); rd(14'h050, v); $display("overruns = %0d", v);
    $fclose(f); $display("logged %0d symbols", nlog); $finish;
  end
endmodule
