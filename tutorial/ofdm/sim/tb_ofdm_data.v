`timescale 1ns/1ps
// Testbench of ofdm_fft.v + ofdm_data.v: per case 28 weights, then 44 windows; the FFT of each window, then sym_go; the corrected symbols and the counters are logged.
module tb_ofdm_data;
  reg clk = 0; always #5 clk = ~clk;
  reg start = 0, valid = 0; reg signed [15:0] xr = 0, xi = 0; reg frame_start = 0, sym_go = 0; reg [5:0] sym = 0;
  wire fbusy, fdone, fovf; wire signed [19:0] rr, ri; wire [5:0] ra; wire [4:0] wa;
  wire busy, done; wire [31:0] sym_cnt, sym_err, bit_err; wire [63:0] evm_err, evm_ref; wire o_valid; wire [10:0] o_idx; wire signed [23:0] o_re, o_im; wire ovf;
  reg signed [31:0] wre [0:27], wim [0:27];
  ofdm_fft fft (.clk(clk), .start(start), .in_valid(valid), .in_re(xr), .in_im(xi), .busy(fbusy), .done(fdone), .ovf(fovf), .rd_addr(ra), .rd_re(rr), .rd_im(ri));
  ofdm_data dut (.clk(clk), .frame_start(frame_start), .sym_go(sym_go), .sym(sym), .rd_addr(ra), .rd_re(rr), .rd_im(ri), .w_addr(wa), .w_re(wre[wa]), .w_im(wim[wa]), .busy(busy), .done(done),
    .sym_cnt(sym_cnt), .sym_err(sym_err), .bit_err(bit_err), .evm_err(evm_err), .evm_ref(evm_ref), .o_valid(o_valid), .o_idx(o_idx), .o_re(o_re), .o_im(o_im), .ovf(ovf));
  parameter NC = 12;
  reg [31:0] mem [0:(56 + 44 * 64) * NC - 1];
  integer f, c, k, l, nc, base, nfo, no, fd; time tg; reg shown = 0; reg [1023:0] hexname;
  reg signed [23:0] ob_r [0:1055], ob_i [0:1055];
  always @(posedge clk) if (o_valid) begin ob_r[o_idx] <= o_re; ob_i[o_idx] <= o_im; no = no + 1; end
  initial begin
    if (!$value$plusargs("hex=%s", hexname)) hexname = "data_in.hex";
    if (!$value$plusargs("nc=%d", nc)) nc = NC;
    $readmemh(hexname, mem); f = $fopen("rtl_ofdm_data.txt", "w"); fd = $fopen("rtl_ofdm_dbg.txt", "w"); nfo = 0;
    #100;
    for (c = 0; c < nc; c = c + 1) begin
      base = c * (56 + 44 * 64); no = 0;
      for (k = 0; k < 28; k = k + 1) begin wre[k] = mem[base + 2 * k]; wim[k] = mem[base + 2 * k + 1]; end
      @(posedge clk); #1 frame_start = 1; @(posedge clk); #1 frame_start = 0;
      for (l = 0; l < 44; l = l + 1) begin
        @(posedge clk); #1 start = 1; @(posedge clk); #1 start = 0;
        for (k = 0; k < 64; k = k + 1) begin @(posedge clk); #1 valid = 1; xr = mem[base + 56 + l * 64 + k][15:0]; xi = mem[base + 56 + l * 64 + k][31:16]; end
        @(posedge clk); #1 valid = 0; wait (fdone); if (fovf) nfo = nfo + 1; @(posedge clk); #1;
        sym = l; sym_go = 1; tg = $time; @(posedge clk); #1 sym_go = 0; wait (done); if (!shown && l == 1) $display("clocks of symbol 1 (phase 1 only): %0d", ($time - tg) / 10); if (!shown && l == 10) begin $display("clocks of symbol 10 (phase 1 and phase 2): %0d", ($time - tg) / 10); shown = 1; end @(posedge clk); #1;
      end
      for (k = 0; k < 1056; k = k + 1) $fwrite(f, "%0d %0d\n", ob_r[k], ob_i[k]);
      $fwrite(f, "%0d %0d %0d %0d %0d\n", sym_cnt, sym_err, bit_err, evm_err, evm_ref);
      for (l = 0; l < 44; l = l + 1) $fwrite(fd, "%0d %0d %0d\n", dut.g_r[l], dut.g_i[l], dut.sl_m[l]);
      for (l = 0; l < 4; l = l + 1) for (k = 0; k < 24; k = k + 1) $fwrite(fd, "%0d %0d\n", dut.zm_r[l * 24 + k], dut.zm_i[l * 24 + k]);
      if (ovf) $display("case %0d: ovf flag set", c);
    end
    $display("cases = %0d, FFT overflow flags = %0d", nc, nfo);
    $fclose(f); $finish;
  end
endmodule
