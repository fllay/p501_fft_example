// Turns the AD9361 ADC sample stream (one channel: I and Q, qualified by a
// valid strobe, in the ADC clock domain) into AXI-Stream frames of
// 2**N_LOG2 samples: TDATA = {Q[15:0], I[15:0]}, TLAST on the last sample of
// each frame. Free-running: it never stalls the ADC (the FFT downstream
// must keep up, which a pipelined-streaming FFT does at one sample/clock).
`timescale 1ns/1ps
module adc_frame_gen #(
  parameter integer N_LOG2 = 10
) (
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF m_axis, ASSOCIATED_RESET resetn" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
  input  wire        clk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input  wire        resetn,

  input  wire [15:0] smp_i,
  input  wire [15:0] smp_q,
  input  wire        smp_valid,

  output wire [31:0] m_axis_tdata,
  output wire        m_axis_tvalid,
  input  wire        m_axis_tready,   // unused: the ADC cannot be stalled
  output wire        m_axis_tlast
);
  reg [N_LOG2-1:0] cnt;
  reg [31:0]       tdata;
  reg              tvalid;
  reg              tlast;

  always @(posedge clk) begin
    if (!resetn) begin
      cnt    <= {N_LOG2{1'b0}};
      tvalid <= 1'b0;
      tlast  <= 1'b0;
      tdata  <= 32'd0;
    end else begin
      tvalid <= smp_valid;
      if (smp_valid) begin
        tdata <= {smp_q, smp_i};
        tlast <= (cnt == {N_LOG2{1'b1}});
        cnt   <= cnt + 1'b1;          // wraps at 2**N_LOG2
      end
    end
  end

  assign m_axis_tdata  = tdata;
  assign m_axis_tvalid = tvalid;
  assign m_axis_tlast  = tlast;
endmodule
