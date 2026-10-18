// FFT output stage: |X|^2 = re^2 + im^2 (unsigned 32 bit) plus a frame gate and a FIFO flush.
//
// Input : FFT output frames, TDATA = {im[15:0], re[15:0]}, TLAST on the last bin.
// Output: one 32-bit power value per bin. A whole frame is forwarded only if
//         `frame_en` (the DMA is running a transfer) is high when the frame's
//         first bin arrives; otherwise the whole frame is dropped. So a DMA
//         transfer always starts on a frame boundary and receives only whole
//         frames - the FFT itself runs free and is never stalled.
// The output FIFO behind this block must be at least one frame deep.
//
// Fresh data: while no transfer is pending the FIFO behind this block is held in
//         reset (`fifo_resetn` low), so it cannot keep frames of an earlier time that the DMA
//         did not take (the gate admits one or two frames more than the DMA reads, because
//         `frame_en` stays high a little after the last beat). Without the flush the first
//         frames of the next transfer would be old, up to seconds old. After `frame_en`
//         rises, the gate waits 64 clock cycles (FIFO out of reset) before it admits
//         a frame, and a frame cut short by `frame_en` falling is dropped.
// m_axis_tlast is held low on purpose: the ADI axi_dmac ends a transfer at the first TLAST
// it sees (it treats it as an end-of-packet), so forwarding the per-frame TLAST would stop
// a multi-frame DMA transfer after one frame. Frame alignment is guaranteed by the gate.
`timescale 1ns/1ps
module fft_power_gate (
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axis:m_axis, ASSOCIATED_RESET resetn" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
  input  wire        clk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input  wire        resetn,

  input  wire        frame_en,

  input  wire [31:0] s_axis_tdata,
  input  wire        s_axis_tvalid,
  output wire        s_axis_tready,
  input  wire        s_axis_tlast,

  output reg  [31:0] m_axis_tdata,
  output reg         m_axis_tvalid,
  input  wire        m_axis_tready,   // unused: output FIFO absorbs a frame
  output reg         m_axis_tlast,

  output wire        fifo_resetn      // active-low reset for the output FIFO: low while no transfer is pending
);
  assign s_axis_tready = 1'b1;

  // FIFO flush and arming: the FIFO is in reset while frame_en is low and
  // frames are admitted only 64 cycles after it came out of reset
  reg        fifo_rst_n_r = 1'b0;
  reg [6:0]  arm_cnt = 7'd0;
  always @(posedge clk) begin
    fifo_rst_n_r <= resetn & frame_en;
    if (!resetn || !frame_en)  arm_cnt <= 7'd0;
    else if (!arm_cnt[6])      arm_cnt <= arm_cnt + 7'd1;
  end
  assign fifo_resetn = fifo_rst_n_r;
  wire armed = arm_cnt[6];

  // frame gate: decided on the first bin of each frame
  reg in_frame, pass_q;
  wire pass_now = armed & (in_frame ? pass_q : frame_en);

  always @(posedge clk) begin
    if (!resetn) begin
      in_frame <= 1'b0;
      pass_q   <= 1'b0;
    end else if (s_axis_tvalid) begin
      pass_q   <= pass_now;
      in_frame <= ~s_axis_tlast;
    end
  end

  // stage 1: register inputs
  reg signed [15:0] re_q, im_q;
  reg v1, l1, p1;
  // stage 2: squares (DSP)
  reg [31:0] re2, im2;
  reg v2, l2, p2;

  always @(posedge clk) begin
    if (!resetn) begin
      v1 <= 1'b0; v2 <= 1'b0; m_axis_tvalid <= 1'b0;
    end else begin
      v1 <= s_axis_tvalid;
      l1 <= s_axis_tlast;
      p1 <= pass_now;
      re_q <= s_axis_tdata[15:0];
      im_q <= s_axis_tdata[31:16];

      v2  <= v1;
      l2  <= l1;
      p2  <= p1;
      re2 <= re_q * re_q;
      im2 <= im_q * im_q;

      m_axis_tvalid <= v2 & p2;
      m_axis_tlast  <= 1'b0;
      m_axis_tdata  <= re2 + im2;      // <= 2^31, fits in 32 bit unsigned
    end
  end
endmodule
