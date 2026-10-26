// OFDM receiver (PLAN_OFDM.md section 12): ID 0xDD520007 with the Schmidl-and-Cox synchroniser (STS = 0), 0xDD520008 with the 128-sample short training field (STS = 1: the same blocks, another detector, preamble and
// window offsets). Bit-exact model: tutorial/ofdm/ofdm_fixed.py (receive_fixed with the variant SC or STS).
// Offsets after s0 (the start of the preamble, S&C symbol of 80 samples | STS of 128 samples): T1 window 90 | 154, T2 window 170 | 218 (T1 + 80 | T1 + 64: the lag of the fine carrier), first data window 250 | 298;
// the fine carrier word is turns(P) x 2^12 / lag = x 52429 / 1024 | x 65536 / 1024.
//
//   adc samples (adc_clk) -> two sample RAMs of 1024 x {q, i} (12 bit): one read by the detector as a stream, one read by the window reader
//   ofdm_detect (S&C detector, plateau, coarse carrier, gain) -> found: s0, w_c, G
//   frame controller: fine carrier from the two training windows (T1, T2 derotated by w_c, 64 products, CORDIC, the check that they repeat), then T1 and T2 through the FFT into the channel module (H, noise, weights),
//   then the 44 data windows through the FFT into the data module (equaliser, pilots, averaging, correction, slicer, checker). The detector is re-armed when the last window has been read.
//   window reader + derotator (ofdm_derot): gain and the NCO from the carrier word; the window of a symbol starts 6 samples inside its prefix.
// Registers (AXI-Lite, word index = addr[7:2]):
//   00 ID   01 CTRL (bit0 run, bit1 capture arm (0 -> 1), bit2 continuous: re-arm after every frame, default 1)   02 THR (166 = 0.65)   03 EMIN (4)   04 TARGET (400)   05 GAIN_OVR (0 = from the detector)
//   08 STATUS (bit0 running, bit1 capture done, bit2 a frame found, bit3 frame busy, bit4 detector late, bit5 overflow (data), bit6 FFT overflow, bit7 window overrun)
//   09 FRAMES (complete)  0A FOUND  0B REJECTED (the training symbols did not repeat)  0C BAD_FRAMES (more than 20 % symbol errors)  0D TOT_SYM  0E TOT_SYM_ERR  0F TOT_BIT_ERR
//   10 SYM_CNT (last frame)  11 SYM_ERR  12 BIT_ERR  13 EVM_ERR_LO  14 EVM_ERR_HI  15 EVM_REF_LO  16 EVM_REF_HI   (sums as in the 16-QAM receiver: unit RMS = 12953 counts, inner level 4096)
//   18 S0 (absolute sample index of the start of the S&C symbol)  19 W_C  1A W_F  1B W (carrier, turns x 2^32 per sample)  1C GAIN used (Q8)  1D NOISE_LO  1E NOISE_HI (sum of |A - B|^2)  1F WR_COUNT (samples written)  20 SAMPLES_LATE
//   0x1000 .. 0x1FFC: capture RAM, the first 1024 corrected data symbols of a frame {zq[15:0], zi[15:0]} (saturated),   0x2000 .. 0x206C: H of the 28 used subcarriers {hi[15:0], hr[15:0]} (saturated)
`timescale 1ns/1ps
module ofdm_rx #(parameter STS = 0) (
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axi, ASSOCIATED_RESET aresetn" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 aclk CLK" *)
  input  wire        aclk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input  wire        aresetn,
  input  wire [13:0] s_axi_awaddr,
  input  wire        s_axi_awvalid,
  output wire        s_axi_awready,
  input  wire [31:0] s_axi_wdata,
  input  wire [3:0]  s_axi_wstrb,
  input  wire        s_axi_wvalid,
  output wire        s_axi_wready,
  output reg  [1:0]  s_axi_bresp,
  output reg         s_axi_bvalid,
  input  wire        s_axi_bready,
  input  wire [13:0] s_axi_araddr,
  input  wire        s_axi_arvalid,
  output wire        s_axi_arready,
  output reg  [31:0] s_axi_rdata,
  output reg  [1:0]  s_axi_rresp,
  output reg         s_axi_rvalid,
  input  wire        s_axi_rready,
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 adc_clk CLK" *)
  input  wire        adc_clk,
  input  wire        adc_valid,
  input  wire [15:0] adc_i,
  input  wire [15:0] adc_q
);
  localparam [31:0] T1OFF = STS ? 32'd154 : 32'd90, T2OFF = STS ? 32'd218 : 32'd170, FWEND = STS ? 32'd282 : 32'd234, BASE = STS ? 32'd298 : 32'd250;
  localparam signed [31:0] WFMUL = STS ? 32'sd65536 : 32'sd52429;
  // ======================= registers =======================
  reg [31:0] r_ctrl, r_thr, r_emin, r_target, r_gain;
  wire do_write = s_axi_awvalid & s_axi_wvalid & ~s_axi_bvalid;
  assign s_axi_awready = do_write;
  assign s_axi_wready  = do_write;
  always @(posedge aclk) begin
    if (!aresetn) begin
      r_ctrl <= 32'd4; r_thr <= 32'd166; r_emin <= 32'd4; r_target <= 32'd400; r_gain <= 32'd0; s_axi_bvalid <= 1'b0; s_axi_bresp <= 2'b00;
    end else begin
      if (do_write) begin
        case (s_axi_awaddr[7:2])
          6'h01: r_ctrl <= s_axi_wdata; 6'h02: r_thr <= s_axi_wdata; 6'h03: r_emin <= s_axi_wdata; 6'h04: r_target <= s_axi_wdata; 6'h05: r_gain <= s_axi_wdata;
          default: ;
        endcase
        s_axi_bvalid <= 1'b1;
      end else if (s_axi_bvalid & s_axi_bready) s_axi_bvalid <= 1'b0;
    end
  end

  // ======================= sample RAMs, adc_clk side =======================
  reg [23:0] sram_s [0:1023];
  reg [23:0] sram_w [0:1023];
  reg [31:0] wr_cnt = 32'd0, wr_gray = 32'd0;
  always @(posedge adc_clk) begin
    if (adc_valid) begin
      sram_s[wr_cnt[9:0]] <= {adc_q[11:0], adc_i[11:0]}; sram_w[wr_cnt[9:0]] <= {adc_q[11:0], adc_i[11:0]};
      wr_cnt <= wr_cnt + 32'd1;
    end
    wr_gray <= wr_cnt ^ (wr_cnt >> 1);
  end
  (* ASYNC_REG = "TRUE" *) reg [31:0] g_s1 = 32'd0, g_s2 = 32'd0;
  always @(posedge aclk) begin g_s1 <= wr_gray; g_s2 <= g_s1; end
  function [31:0] gray2bin(input [31:0] gg);
    integer gi;
    begin gray2bin[31] = gg[31]; for (gi = 30; gi >= 0; gi = gi - 1) gray2bin[gi] = gray2bin[gi + 1] ^ gg[gi]; end
  endfunction
  wire [31:0] wr_sync = gray2bin(g_s2);

  // ======================= the detector and its stream reader =======================
  wire run = r_ctrl[0] & aresetn;
  reg        rearm_req;
  reg [2:0]  rearm_hold;
  reg [31:0] rd_ptr, det_base;
  reg        rs_pend, s_valid;
  reg [23:0] ss_q;
  wire       det_ready;
  wire [31:0] avail = wr_sync - rd_ptr;
  wire        have = (avail != 32'd0) && !avail[31];
  wire        det_run = run && (rearm_hold == 3'd0);
  wire        found; wire [31:0] d_n0; wire [7:0] d_first, d_last, d_pkidx; wire signed [31:0] d_s0, d_wc; wire [15:0] d_gain; wire [28:0] d_epk; wire signed [39:0] d_sr, d_si; wire [10:0] d_pk; wire det_late;
  wire        w_pulse_unused; wire [31:0] w_n_unused; wire w_cond_unused; wire signed [29:0] w_sr_u, w_si_u; wire [28:0] w_e_u;
  ofdm_detect #(.STS(STS)) u_det (.clk(aclk), .run(det_run), .s_valid(s_valid), .xi(ss_q[11:0]), .xq(ss_q[23:12]), .r_thr(r_thr[7:0]), .r_emin(r_emin[7:0]), .r_target(r_target[15:0]), .found(found),
    .o_n0(d_n0), .o_first(d_first), .o_last(d_last), .o_pkidx(d_pkidx), .o_s0(d_s0), .o_wc(d_wc), .o_gain(d_gain), .o_epk(d_epk), .o_sr(d_sr), .o_si(d_si), .o_pk(d_pk), .late(det_late), .ready(det_ready),
    .w_pulse(w_pulse_unused), .w_n(w_n_unused), .w_cond(w_cond_unused), .w_sr(w_sr_u), .w_si(w_si_u), .w_e(w_e_u));
  always @(posedge aclk) begin
    s_valid <= 1'b0;
    ss_q <= sram_s[rd_ptr[9:0]];
    if (rearm_hold != 3'd0) rearm_hold <= rearm_hold - 3'd1;
    if (!run) begin rd_ptr <= wr_sync; det_base <= wr_sync; rs_pend <= 1'b0; rearm_hold <= 3'd0; end
    else if (rearm_req) begin rd_ptr <= wr_sync; det_base <= wr_sync; rs_pend <= 1'b0; rearm_hold <= 3'd3; end
    else if (rs_pend) begin s_valid <= 1'b1; rd_ptr <= rd_ptr + 32'd1; rs_pend <= 1'b0; end
    else if (det_ready && have && rearm_hold == 3'd0) rs_pend <= 1'b1;
  end

  // ======================= window reader and derotator =======================
  reg [31:0] f_b1, f_b2, raddr; reg f_pair, f_busy, f_go; reg [7:0] f_n, f_k;
  reg iss, iss_d; reg [23:0] sw_q; reg [11:0] m_d;
  reg signed [31:0] w_use; reg [15:0] g_use; reg [31:0] l_s0;
  always @(posedge aclk) begin
    iss <= 1'b0; iss_d <= iss; sw_q <= sram_w[raddr[9:0]]; m_d <= raddr[11:0] - l_s0[11:0];
    if (f_go) begin f_busy <= 1'b1; f_k <= 8'd0; end
    else if (f_busy) begin
      raddr <= f_pair ? (f_k[0] ? (f_b2 + {24'd0, f_k[7:1]}) : (f_b1 + {24'd0, f_k[7:1]})) : (f_b1 + {24'd0, f_k});
      iss <= 1'b1; f_k <= f_k + 8'd1;
      if (f_k == f_n - 8'd1) f_busy <= 1'b0;
    end
    if (!run) f_busy <= 1'b0;
  end
  wire d_ov; wire signed [15:0] yr, yi;
  ofdm_derot u_derot (.clk(aclk), .in_valid(iss_d), .xi(sw_q[11:0]), .xq(sw_q[23:12]), .m(m_d), .w(w_use), .gain(g_use), .out_valid(d_ov), .yr(yr), .yi(yi));

  // ======================= FFT, channel, data =======================
  reg fft_start, cm_fft, cmd_a, cmd_b, sym_go, frame_start;
  reg [5:0] sl;
  wire f_busy_fft, f_done_fft, f_ovf_fft; wire signed [19:0] fr_re, fr_im;
  wire [5:0] ch_addr, da_addr; wire sel_data;
  wire [5:0] fft_ra = sel_data ? da_addr : ch_addr;
  ofdm_fft u_fft (.clk(aclk), .start(fft_start), .in_valid(d_ov & cm_fft), .in_re(yr), .in_im(yi), .busy(f_busy_fft), .done(f_done_fft), .ovf(f_ovf_fft), .rd_addr(fft_ra), .rd_re(fr_re), .rd_im(fr_im));
  wire ch_busy, ch_done; wire [47:0] ch_noise; wire [4:0] da_waddr; reg hc_active; reg [4:0] hc_idx;
  wire signed [20:0] ch_hre, ch_him; wire signed [31:0] ch_wre, ch_wim;
  ofdm_chan u_chan (.clk(aclk), .cmd_a(cmd_a), .cmd_b(cmd_b), .rd_addr(ch_addr), .rd_re(fr_re), .rd_im(fr_im), .busy(ch_busy), .done(ch_done), .noise(ch_noise), .x_addr(hc_active ? hc_idx : da_waddr),
    .h_re(ch_hre), .h_im(ch_him), .w_re(ch_wre), .w_im(ch_wim));
  wire da_busy, da_done; wire [31:0] da_cnt, da_err, da_bit; wire [63:0] da_evm_e, da_evm_r; wire da_ov; wire [10:0] da_oidx; wire signed [23:0] da_ore, da_oim; wire da_ovf;
  ofdm_data u_data (.clk(aclk), .frame_start(frame_start), .sym_go(sym_go), .sym(sl), .rd_addr(da_addr), .rd_re(fr_re), .rd_im(fr_im), .w_addr(da_waddr), .w_re(ch_wre), .w_im(ch_wim),
    .busy(da_busy), .done(da_done), .sym_cnt(da_cnt), .sym_err(da_err), .bit_err(da_bit), .evm_err(da_evm_e), .evm_ref(da_evm_r), .o_valid(da_ov), .o_idx(da_oidx), .o_re(da_ore), .o_im(da_oim), .ovf(da_ovf));

  // fine carrier: the two training windows alternate at the derotator output
  reg cm_pair, ph, pair_init; reg signed [15:0] a_r, a_i; reg signed [63:0] pr_acc, pi_acc, e1_acc, e2_acc; reg [6:0] pair_cnt;
  always @(posedge aclk) begin
    if (pair_init) begin ph <= 1'b0; pair_cnt <= 7'd0; pr_acc <= 64'sd0; pi_acc <= 64'sd0; e1_acc <= 64'sd0; e2_acc <= 64'sd0; end
    else if (d_ov && cm_pair) begin
      if (!ph) begin a_r <= yr; a_i <= yi; ph <= 1'b1; e1_acc <= e1_acc + yr * yr + yi * yi; end
      else begin
        pr_acc <= pr_acc + yr * a_r + yi * a_i; pi_acc <= pi_acc + yi * a_r - yr * a_i; e2_acc <= e2_acc + yr * yr + yi * yi; ph <= 1'b0; pair_cnt <= pair_cnt + 7'd1;
      end
    end
  end
  reg cord_start; wire cord_done; wire [19:0] cord_ang;
  ofdm_cordic u_cf (.clk(aclk), .start(cord_start), .re(pr_acc[39:0]), .im(pi_acc[39:0]), .done(cord_done), .ang(cord_ang));

  // ======================= controller =======================
  localparam [4:0] C_OFF = 0, C_WDET = 1, C_FW = 2, C_FINE = 3, C_FINEC = 4, C_T1S = 5, C_T1W = 6, C_T1X0 = 7, C_T1X = 8, C_T2S = 9, C_T2W = 10, C_T2X = 11, C_HC = 12, C_SYMW = 13, C_SYMF = 14, C_SYMD = 15, C_FIN = 16, C_FINE0 = 17;
  reg [4:0] c_st;
  reg found_seen, found_lost; reg signed [31:0] l_wc; reg [15:0] l_gain; reg [31:0] ws; reg [3:0] dly;
  reg signed [31:0] w_c_last, w_f_last; reg [31:0] s0_last, g_last;
  reg [31:0] frames, n_found, n_rej, n_bad, tot_sym, tot_err, tot_bit, ls_cnt, ls_err, ls_bit; reg [63:0] ls_ee, ls_er; reg [47:0] ls_noise;
  reg [31:0] n_late; reg ovf_any, fft_ovf_any, overrun;
  reg cap_pend, cap_active, cap_done; reg ctrl_q;
  reg [31:0] cap_mem [0:1023]; reg [31:0] h_mem [0:31];
  assign sel_data = (c_st == C_SYMF) || (c_st == C_SYMD);
  wire signed [63:0] ck_l = 2 * ((pr_acc >>> 10) * (pr_acc >>> 10) + (pi_acc >>> 10) * (pi_acc >>> 10)), ck_r = (e1_acc >>> 10) * (e2_acc >>> 10);
  wire signed [31:0] wf_new = ($signed({{12{cord_ang[19]}}, cord_ang}) * WFMUL) >>> 10;
  function [15:0] sat16(input signed [31:0] v); sat16 = (v > 32'sd32767) ? 16'h7FFF : (v < -32'sd32768) ? 16'h8000 : v[15:0]; endfunction
  initial begin c_st = C_OFF; found_seen = 0; found_lost = 0; frames = 0; end
  always @(posedge aclk) begin
    fft_start <= 1'b0; cmd_a <= 1'b0; cmd_b <= 1'b0; sym_go <= 1'b0; frame_start <= 1'b0; f_go <= 1'b0; rearm_req <= 1'b0; cord_start <= 1'b0; pair_init <= 1'b0;
    ctrl_q <= r_ctrl[1]; if (r_ctrl[1] && !ctrl_q) cap_pend <= 1'b1;
    if (det_late) n_late <= n_late + 32'd1;
    if (found && found_seen) found_lost <= 1'b1;
    if (found && !found_seen) begin l_s0 <= det_base + d_s0; l_wc <= d_wc; l_gain <= (r_gain[15:0] != 16'd0) ? r_gain[15:0] : d_gain; found_seen <= 1'b1; n_found <= n_found + 32'd1; end
    if (da_ovf) ovf_any <= 1'b1; if (f_ovf_fft) fft_ovf_any <= 1'b1;
    if (da_ov && cap_active && da_oidx < 11'd1024) cap_mem[da_oidx[9:0]] <= {sat16(da_oim), sat16(da_ore)};
    if (!run) begin
      c_st <= C_OFF; found_seen <= 1'b0; found_lost <= 1'b0; cap_pend <= 1'b0; cap_active <= 1'b0; cm_fft <= 1'b0; cm_pair <= 1'b0; hc_active <= 1'b0;
      if (!aresetn) begin frames <= 0; n_found <= 0; n_rej <= 0; n_bad <= 0; tot_sym <= 0; tot_err <= 0; tot_bit <= 0; n_late <= 0; ovf_any <= 0; fft_ovf_any <= 0; overrun <= 0; cap_done <= 0; end
    end else case (c_st)
      C_OFF:  c_st <= C_WDET;
      C_WDET: if (found_seen) begin
                frame_start <= 1'b1; cap_active <= cap_pend; cap_pend <= 1'b0; if (cap_pend) cap_done <= 1'b0;
                w_use <= l_wc; g_use <= l_gain; c_st <= C_FW;
              end
      C_FW:   if (wr_sync >= l_s0 + FWEND) begin
                f_b1 <= l_s0 + T1OFF; f_b2 <= l_s0 + T2OFF; f_pair <= 1'b1; f_n <= 8'd128; cm_pair <= 1'b1; cm_fft <= 1'b0; pair_init <= 1'b1; f_go <= 1'b1; c_st <= C_FINE0;
              end
      C_FINE0: c_st <= C_FINE;                                                                       // the accumulators are cleared by pair_init one clock after it was set
      C_FINE: if (pair_cnt == 7'd64) begin cm_pair <= 1'b0; cord_start <= 1'b1; c_st <= C_FINEC; end
      C_FINEC: if (cord_done) begin
                if (ck_l < ck_r) begin n_rej <= n_rej + 32'd1; found_seen <= 1'b0; rearm_req <= 1'b1; cap_active <= 1'b0; c_st <= C_WDET; end
                else begin w_use <= l_wc + wf_new; w_c_last <= l_wc; w_f_last <= wf_new; s0_last <= l_s0; g_last <= {16'd0, l_gain}; c_st <= C_T1S; end
              end
      C_T1S:  begin f_b1 <= l_s0 + T1OFF; f_pair <= 1'b0; f_n <= 8'd64; cm_fft <= 1'b1; fft_start <= 1'b1; f_go <= 1'b1; c_st <= C_T1W; end
      C_T1W:  if (f_done_fft) begin cmd_a <= 1'b1; dly <= 4'd3; c_st <= C_T1X0; end
      C_T1X0: begin if (dly != 4'd0) dly <= dly - 4'd1; else c_st <= C_T1X; end
      C_T1X:  if (!ch_busy) c_st <= C_T2S;
      C_T2S:  begin f_b1 <= l_s0 + T2OFF; f_pair <= 1'b0; f_n <= 8'd64; cm_fft <= 1'b1; fft_start <= 1'b1; f_go <= 1'b1; c_st <= C_T2W; end
      C_T2W:  if (f_done_fft) begin cmd_b <= 1'b1; c_st <= C_T2X; end
      C_T2X:  if (ch_done) begin hc_active <= 1'b1; hc_idx <= 5'd0; c_st <= C_HC; end
      C_HC:   begin
                h_mem[hc_idx] <= {sat16(ch_him), sat16(ch_hre)};
                if (hc_idx == 5'd27) begin hc_active <= 1'b0; sl <= 6'd0; ws <= l_s0 + BASE; c_st <= C_SYMW; end else hc_idx <= hc_idx + 5'd1;
              end
      C_SYMW: if (wr_sync >= ws + 32'd64) begin
                if (wr_sync - ws >= 32'd1000) overrun <= 1'b1;
                f_b1 <= ws; f_pair <= 1'b0; f_n <= 8'd64; cm_fft <= 1'b1; fft_start <= 1'b1; f_go <= 1'b1; c_st <= C_SYMF;
              end
      C_SYMF: if (f_done_fft) begin
                if (sl == 6'd43 && r_ctrl[2]) rearm_req <= 1'b1;
                sym_go <= 1'b1; c_st <= C_SYMD;
              end
      C_SYMD: if (da_done) begin
                if (sl == 6'd43) c_st <= C_FIN;
                else begin sl <= sl + 6'd1; ws <= ws + 32'd80; c_st <= C_SYMW; end
              end
      C_FIN:  begin
                frames <= frames + 32'd1; ls_cnt <= da_cnt; ls_err <= da_err; ls_bit <= da_bit; ls_ee <= da_evm_e; ls_er <= da_evm_r; ls_noise <= ch_noise;
                tot_sym <= tot_sym + da_cnt; tot_err <= tot_err + da_err; tot_bit <= tot_bit + da_bit; if (da_err * 5 > da_cnt) n_bad <= n_bad + 32'd1;
                if (cap_active) begin cap_active <= 1'b0; cap_done <= 1'b1; end
                found_seen <= 1'b0; cm_fft <= 1'b0; c_st <= C_WDET;
                if (found_lost && r_ctrl[2]) rearm_req <= 1'b1; found_lost <= 1'b0;
              end
      default: c_st <= C_OFF;
    endcase
  end

  // ======================= AXI-Lite read =======================
  reg [31:0] cap_rd, h_rd; reg [13:0] araddr_q; reg ar_cap, ar_h, ar_pending;
  reg det_late_seen; always @(posedge aclk) det_late_seen <= (n_late != 0);
  wire [31:0] status = {24'd0, overrun, fft_ovf_any, ovf_any, det_late_seen, (c_st > C_WDET), found_seen, cap_done, run};
  assign s_axi_arready = s_axi_arvalid & ~s_axi_rvalid & ~ar_pending;
  always @(posedge aclk) begin
    cap_rd <= cap_mem[s_axi_araddr[11:2]]; h_rd <= h_mem[s_axi_araddr[6:2]];
    if (!aresetn) begin s_axi_rvalid <= 1'b0; s_axi_rdata <= 32'd0; s_axi_rresp <= 2'b00; ar_pending <= 1'b0; ar_cap <= 1'b0; ar_h <= 1'b0; end
    else begin
      if (s_axi_arready) begin ar_cap <= s_axi_araddr[12]; ar_h <= s_axi_araddr[13]; ar_pending <= 1'b1; end
      else if (ar_pending) begin
        ar_pending <= 1'b0; s_axi_rvalid <= 1'b1;
        if (ar_h) s_axi_rdata <= h_rd;
        else if (ar_cap) s_axi_rdata <= cap_rd;
        else case (araddr_q[7:2])
          6'h00: s_axi_rdata <= STS ? 32'hDD520008 : 32'hDD520007;
          6'h01: s_axi_rdata <= r_ctrl; 6'h02: s_axi_rdata <= r_thr; 6'h03: s_axi_rdata <= r_emin; 6'h04: s_axi_rdata <= r_target; 6'h05: s_axi_rdata <= r_gain;
          6'h08: s_axi_rdata <= status; 6'h09: s_axi_rdata <= frames; 6'h0A: s_axi_rdata <= n_found; 6'h0B: s_axi_rdata <= n_rej; 6'h0C: s_axi_rdata <= n_bad;
          6'h0D: s_axi_rdata <= tot_sym; 6'h0E: s_axi_rdata <= tot_err; 6'h0F: s_axi_rdata <= tot_bit;
          6'h10: s_axi_rdata <= ls_cnt; 6'h11: s_axi_rdata <= ls_err; 6'h12: s_axi_rdata <= ls_bit; 6'h13: s_axi_rdata <= ls_ee[31:0]; 6'h14: s_axi_rdata <= ls_ee[63:32];
          6'h15: s_axi_rdata <= ls_er[31:0]; 6'h16: s_axi_rdata <= ls_er[63:32];
          6'h18: s_axi_rdata <= s0_last; 6'h19: s_axi_rdata <= w_c_last; 6'h1A: s_axi_rdata <= w_f_last; 6'h1B: s_axi_rdata <= w_c_last + w_f_last; 6'h1C: s_axi_rdata <= g_last;
          6'h1D: s_axi_rdata <= ls_noise[31:0]; 6'h1E: s_axi_rdata <= {16'd0, ls_noise[47:32]}; 6'h1F: s_axi_rdata <= wr_sync; 6'h20: s_axi_rdata <= n_late;
          default: s_axi_rdata <= 32'd0;
        endcase
      end else if (s_axi_rvalid & s_axi_rready) s_axi_rvalid <= 1'b0;
    end
  end
  always @(posedge aclk) if (s_axi_arready) araddr_q <= s_axi_araddr;
endmodule
