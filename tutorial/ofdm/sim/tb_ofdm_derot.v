`timescale 1ns/1ps
// Testbench of ofdm_derot.v: vectors "xi xq m w G" (hex, one per line, packed in 96 bit) in a hex file; the outputs yr, yi are logged.
module tb_ofdm_derot;
  reg clk = 0; always #5 clk = ~clk;
  reg valid = 0; reg signed [11:0] xi = 0, xq = 0; reg [11:0] m = 0; reg signed [31:0] w = 0; reg [15:0] g = 0;
  wire ov; wire signed [15:0] yr, yi;
  ofdm_derot dut (.clk(clk), .in_valid(valid), .xi(xi), .xq(xq), .m(m), .w(w), .gain(g), .out_valid(ov), .yr(yr), .yi(yi));
  parameter NV = 4000;
  reg [95:0] vec [0:NV-1];
  integer f, k, nv; reg [1023:0] hexname;
  always @(posedge clk) if (ov) $fwrite(f, "%0d %0d\n", yr, yi);
  initial begin
    if (!$value$plusargs("hex=%s", hexname)) hexname = "derot_vec.hex";
    if (!$value$plusargs("nv=%d", nv)) nv = NV;
    $readmemh(hexname, vec); f = $fopen("rtl_ofdm_derot.txt", "w");
    #100;
    for (k = 0; k < nv; k = k + 1) begin
      @(posedge clk); #1 valid = 1; xi = vec[k][11:0]; xq = vec[k][27:16]; m = vec[k][43:32]; w = vec[k][79:48]; g = vec[k][95:80];
    end
    @(posedge clk); #1 valid = 0;
    repeat (20) @(posedge clk);
    $fclose(f); $finish;
  end
endmodule
