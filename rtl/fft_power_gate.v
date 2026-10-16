// FFT output stage: |X|^2 = re^2 + im^2 (unsigned 32 bit) plus a frame gate.
//
// Input : FFT output frames, TDATA = {im[15:0], re[15:0]}, TLAST on the last bin.
// Output: one 32-bit power value per bin. A whole frame is forwarded only if
//         `frame_en` (the DMA is running a transfer) is high when the frame's
//         first bin arrives; otherwise the whole frame is dropped. So a DMA
//         transfer always starts on a frame boundary and receives only whole
//         frames - the FFT itself runs free and is never stalled.
// The output FIFO behind this block must be at least one frame deep.
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
  output reg         m_axis_tlast
);
  assign s_axis_tready = 1'b1;

  // frame gate: decided on the first bin of each frame
  reg in_frame, pass_q;
  wire pass_now = in_frame ? pass_q : frame_en;

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
      m_axis_tlast  <= l2;
      m_axis_tdata  <= re2 + im2;      // <= 2^31, fits in 32 bit unsigned
    end
  end
endmodule
