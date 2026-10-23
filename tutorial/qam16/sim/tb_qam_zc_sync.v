`timescale 1ns/1ps
// Testbench of qam_zc_sync.v: symbols from a hex file, one every SPACING clocks, events acknowledged at once; per-symbol metric log and event log.
module tb;
  parameter NS = 40000;
  reg aclk = 0; always #5 aclk = ~aclk;
  reg run = 0, go = 0; reg signed [15:0] mi = 0, mq = 0; reg [31:0] sym_idx = 0;
  wire ev_pend; wire [1:0] ev_kind; wire [31:0] ev_e, ev_known; wire ev_miss; wire signed [31:0] ev_w; wire [31:0] ev_th0; reg ev_ack = 0;
  wire locked; wire [31:0] n_peak, n_lock, n_hit, n_miss, n_lost, late, ev_over; wire signed [39:0] snap_cr, snap_ci; wire [23:0] snap_e; wire [41:0] snap_m;
  reg [7:0] thr_s = 154, thr_l = 115; reg [31:0] tol = 3, win = 4, missmax = 3;
  qam_zc_sync dut (.aclk(aclk), .run(run), .go(go), .mi(mi), .mq(mq), .sym_idx(sym_idx), .r_thr_s(thr_s), .r_thr_l(thr_l), .r_tol(tol), .r_window(win), .r_missmax(missmax),
    .ev_pend(ev_pend), .ev_kind(ev_kind), .ev_e(ev_e), .ev_known(ev_known), .ev_miss(ev_miss), .ev_w(ev_w), .ev_th0(ev_th0), .ev_ack(ev_ack), .locked(locked),
    .n_peak(n_peak), .n_lock(n_lock), .n_hit(n_hit), .n_miss(n_miss), .n_lost(n_lost), .late(late), .ev_over(ev_over), .snap_cr(snap_cr), .snap_ci(snap_ci), .snap_e(snap_e), .snap_m(snap_m));
  reg [31:0] samples [0:NS-1];
  integer fm, fe, k, spacing, nsym; reg [1023:0] hexname;
  reg pend_q = 0;
  always @(posedge aclk) begin ev_ack <= ev_pend; pend_q <= ev_pend; end
  // per symbol (S_TRK = 9): n, C, E, M and the candidate flags of the symbol just processed
  always @(posedge aclk) if (dut.st == 4'd9) $fwrite(fm, "%0d %0d %0d %0d %0d %0d %0d\n", dut.n, dut.full ? $signed(dut.c_r) : 0, dut.full ? $signed(dut.c_i) : 0, dut.e_sum, $signed(dut.m_cur), dut.cs, dut.cl);
  always @(posedge aclk) if (ev_pend && !pend_q) $fwrite(fe, "%0d %0d %0d %0d %0d %0d\n", ev_kind, ev_e, ev_known, ev_miss, $signed(ev_w), ev_th0);
  initial begin
    if (!$value$plusargs("hex=%s", hexname)) hexname = "zc_a.hex";
    if (!$value$plusargs("ns=%d", nsym)) nsym = NS;
    if (!$value$plusargs("sp=%d", spacing)) spacing = 104;
    $readmemh(hexname, samples);
    fm = $fopen("rtl_zc_metric.txt", "w"); fe = $fopen("rtl_zc_events.txt", "w");
    #100 run = 1; #100;
    for (k = 0; k < nsym; k = k + 1) begin
      @(posedge aclk); #1 go = 1; mi = samples[k][15:0]; mq = samples[k][31:16]; sym_idx = k;
      @(posedge aclk); #1 go = 0;
      repeat (spacing - 2) @(posedge aclk);
    end
    #2000;
    $display("peaks = %0d", n_peak); $display("locks = %0d", n_lock); $display("hits = %0d", n_hit); $display("misses = %0d", n_miss); $display("lost = %0d", n_lost); $display("late = %0d", late); $display("evover = %0d", ev_over);
    $fclose(fm); $fclose(fe); $finish;
  end
endmodule
