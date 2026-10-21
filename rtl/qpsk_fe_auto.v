// The autonomous 4th-power estimator: qpsk_fe.v (the accumulators) + an atan2 CORDIC + a gate + the load request for the Costas frequency. No software in the loop.
// Model: tutorial/qpsk/p501_rx_all/qpsk_fe_auto_fixed.py (bit-exact).
//   FE_AUTO bit 0 enable, bit 1 continuous. Once: windows of N symbols follow each other until one passes the gate; its frequency is loaded; then idle until FE_AUTO is written 0, 1.
//   Continuous: every window that passes loads the frequency. The window arms itself (the first window starts with the first symbol after the enable, the next one right after the last symbol of the previous one).
//   atan2 of (ACC_IM, ACC_RE): CORDIC, 18 iterations, angle in turns x 2^20;  w = signed(angle) << 10  (turns per symbol x 2^32, the OMEGA register's unit);
//   gate: CORDIC magnitude >= cnt x QMIN  (QMIN = q_min x 32767 x 1.6468).  The engine takes ld_w at its S7 state, instead of the integrator update, and answers with ld_ack.
`timescale 1ns/1ps
module qpsk_fe_auto (
  input  wire        aclk,
  input  wire        run,
  input  wire        go,
  input  wire signed [15:0] mi, mq,
  input  wire [31:0] sym_idx,
  input  wire        arm_man,
  input  wire [31:0] r_n,
  input  wire [31:0] r_auto,
  input  wire [31:0] r_qmin,
  output wire        active, done,
  output wire [31:0] cnt, first,
  output wire signed [31:0] acc_re, acc_im,
  output wire [31:0] acc_abs,
  output reg         ld_pend,
  output reg  [31:0] ld_w,
  input  wire        ld_ack,
  output reg  [31:0] w_last,                 // the last window's frequency, gate or not
  output reg  [31:0] w_est,                  // the last frequency that passed the gate (and was loaded)
  output reg  [31:0] n_load, n_win
);
  reg arm_a;
  qpsk_fe u_f (.aclk(aclk), .run(run), .go(go), .mi(mi), .mq(mq), .sym_idx(sym_idx), .arm(arm_a | arm_man), .r_n(r_n),
               .active(active), .done(done), .cnt(cnt), .first(first), .acc_re(acc_re), .acc_im(acc_im), .acc_abs(acc_abs));

  localparam [3:0] A_OFF = 4'd0, A_GAP = 4'd1, A_WIN = 4'd2, A_PRE = 4'd3, A_CORD = 4'd4, A_G1 = 4'd5, A_G2 = 4'd6, A_DEC = 4'd7;
  reg [3:0]  as;
  reg [2:0]  gap;
  reg        lock_once;
  reg signed [34:0] x, y;
  reg [19:0] ang;
  reg [4:0]  it;
  reg [31:0] ccnt;
  reg [40:0] prod;
  reg        pass;
  wire en = r_auto[0], cont = r_auto[1];
  wire signed [34:0] ysh = y >>> it, xsh = x >>> it;
  reg [19:0] atab;
  always @(*) case (it)
    5'd0: atab = 20'd131072; 5'd1: atab = 20'd77376; 5'd2: atab = 20'd40884; 5'd3: atab = 20'd20753; 5'd4: atab = 20'd10417; 5'd5: atab = 20'd5213;
    5'd6: atab = 20'd2607;   5'd7: atab = 20'd1304;  5'd8: atab = 20'd652;   5'd9: atab = 20'd326;   5'd10: atab = 20'd163;  5'd11: atab = 20'd81;
    5'd12: atab = 20'd41;    5'd13: atab = 20'd20;   5'd14: atab = 20'd10;   5'd15: atab = 20'd5;    5'd16: atab = 20'd3;    default: atab = 20'd1;
  endcase

  always @(posedge aclk) begin
    arm_a <= 1'b0;
    if (ld_ack) ld_pend <= 1'b0;
    if (!run) begin
      as <= A_OFF; ld_pend <= 1'b0; ld_w <= 32'd0; w_last <= 32'd0; w_est <= 32'd0; n_load <= 32'd0; n_win <= 32'd0; lock_once <= 1'b0; gap <= 3'd0;
    end else begin
      if (!en) lock_once <= 1'b0;
      case (as)
        A_OFF: if (en && !lock_once) begin arm_a <= 1'b1; gap <= 3'd0; as <= A_GAP; end
        A_GAP: begin gap <= gap + 3'd1; if (gap == 3'd3) as <= A_WIN; end                // the arm reaches qpsk_fe and clears its done flag
        A_WIN: begin
                 if (!en) as <= A_OFF;
                 else if (done) begin x <= {{3{acc_re[31]}}, acc_re}; y <= {{3{acc_im[31]}}, acc_im}; ccnt <= cnt; as <= A_PRE; end
               end
        A_PRE: begin                                                                     // fold into the right half plane; in continuous mode the next window starts now
                 if (x[34]) begin x <= -x; y <= -y; ang <= 20'h80000; end else ang <= 20'd0;
                 it <= 5'd0; as <= A_CORD;
                 if (cont && en) arm_a <= 1'b1;
               end
        A_CORD: begin
                 if (y[34] == 1'b0) begin x <= x + ysh; y <= y - xsh; ang <= ang + atab; end
                 else               begin x <= x - ysh; y <= y + xsh; ang <= ang - atab; end
                 it <= it + 5'd1;
                 if (it == 5'd17) as <= A_G1;
               end
        A_G1:  begin prod <= ccnt * r_qmin[20:0]; as <= A_G2; end
        A_G2:  begin pass <= ({6'd0, x} >= prod); as <= A_DEC; end
        A_DEC: begin
                 w_last <= {{2{ang[19]}}, ang[19:0], 10'd0};
                 n_win <= n_win + 32'd1;
                 if (pass) begin
                   ld_w <= {{2{ang[19]}}, ang[19:0], 10'd0}; w_est <= {{2{ang[19]}}, ang[19:0], 10'd0}; ld_pend <= 1'b1; n_load <= n_load + 32'd1;
                   if (!cont) begin lock_once <= 1'b1; as <= A_OFF; end else as <= A_WIN;
                 end else begin
                   if (!cont && en) begin arm_a <= 1'b1; gap <= 3'd0; as <= A_GAP; end else as <= A_WIN;      // once: try again; continuous: the next window is running already
                 end
               end
        default: as <= A_OFF;
      endcase
    end
  end
endmodule
