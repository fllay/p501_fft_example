// AXI4-Lite register block for the DAC DDS, with a safe hand-over of the parameters to the
// sample clock domain (l_clk, unrelated to the AXI clock).
//
//   0x00  ID       (R)   0xDD500001
//   0x04  CONTROL  (RW)  bit0 = enable (0: DAC gets zeros, 1: DDS output)
//   0x08  FTW      (RW)  frequency word: f_out = FTW / 2^32 * f_sample (two's complement for negative f)
//   0x0C  AMP      (RW)  amplitude, Q15: 0x7FFF = full scale (bits 14:0 used)
//   0x10  STATUS   (R)   bit0 = 1: the last COMMIT has been taken over by the sample clock domain
//   0x14  COMMIT   (W)   any write: the values of CONTROL / FTW / AMP go live (all three at the same sample)
//
// Software writes the three parameter registers, then COMMIT, then (optionally) polls STATUS.
// Hand-over: COMMIT toggles a flag; the l_clk side sees the toggle through a 2-flop synchroniser and
// only then loads the (long stable) parameter registers; it toggles an acknowledge back the same way.
`timescale 1ns/1ps
module dds_regs (
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axi, ASSOCIATED_RESET aresetn" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 aclk CLK" *)
  input  wire        aclk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input  wire        aresetn,

  input  wire [5:0]  s_axi_awaddr,
  input  wire        s_axi_awvalid,
  output wire        s_axi_awready,
  input  wire [31:0] s_axi_wdata,
  input  wire [3:0]  s_axi_wstrb,
  input  wire        s_axi_wvalid,
  output wire        s_axi_wready,
  output reg  [1:0]  s_axi_bresp,
  output reg         s_axi_bvalid,
  input  wire        s_axi_bready,
  input  wire [5:0]  s_axi_araddr,
  input  wire        s_axi_arvalid,
  output wire        s_axi_arready,
  output reg  [31:0] s_axi_rdata,
  output reg  [1:0]  s_axi_rresp,
  output reg         s_axi_rvalid,
  input  wire        s_axi_rready,

  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
  input  wire        clk,            // sample clock (l_clk)
  output reg  [31:0] ftw,            // l_clk domain
  output reg  [15:0] amp,            // l_clk domain
  output reg         enable          // l_clk domain
);
  localparam [31:0] ID = 32'hDD500001;

  // ---------------- AXI-Lite (aclk) ----------------
  reg [31:0] ctrl_a = 32'd0, ftw_a = 32'd0, amp_a = 32'd0;
  reg        commit_tog = 1'b0;
  wire       applied;

  wire do_write = s_axi_awvalid & s_axi_wvalid & ~s_axi_bvalid;
  assign s_axi_awready = do_write;
  assign s_axi_wready  = do_write;

  always @(posedge aclk) begin
    if (!aresetn) begin
      ctrl_a <= 32'd0; ftw_a <= 32'd0; amp_a <= 32'd0; commit_tog <= 1'b0;
      s_axi_bvalid <= 1'b0; s_axi_bresp <= 2'b00;
    end else begin
      if (do_write) begin
        case (s_axi_awaddr[5:2])
          4'd1: ctrl_a <= s_axi_wdata;
          4'd2: ftw_a  <= s_axi_wdata;
          4'd3: amp_a  <= s_axi_wdata;
          4'd5: commit_tog <= ~commit_tog;
          default: ;
        endcase
        s_axi_bvalid <= 1'b1;
      end else if (s_axi_bvalid & s_axi_bready) begin
        s_axi_bvalid <= 1'b0;
      end
    end
  end

  assign s_axi_arready = s_axi_arvalid & ~s_axi_rvalid;
  always @(posedge aclk) begin
    if (!aresetn) begin
      s_axi_rvalid <= 1'b0; s_axi_rdata <= 32'd0; s_axi_rresp <= 2'b00;
    end else if (s_axi_arready) begin
      case (s_axi_araddr[5:2])
        4'd0:    s_axi_rdata <= ID;
        4'd1:    s_axi_rdata <= ctrl_a;
        4'd2:    s_axi_rdata <= ftw_a;
        4'd3:    s_axi_rdata <= amp_a;
        4'd4:    s_axi_rdata <= {31'd0, applied};
        default: s_axi_rdata <= 32'd0;
      endcase
      s_axi_rvalid <= 1'b1;
    end else if (s_axi_rvalid & s_axi_rready) begin
      s_axi_rvalid <= 1'b0;
    end
  end

  // ---------------- hand-over to clk ----------------
  (* ASYNC_REG = "TRUE" *) reg [1:0] commit_sync = 2'b00;   // clk domain
  reg ack_tog = 1'b0;                                         // clk domain
  (* ASYNC_REG = "TRUE" *) reg [1:0] ack_sync = 2'b00;      // aclk domain
  assign applied = (ack_sync[1] == commit_tog);

  always @(posedge aclk) ack_sync <= {ack_sync[0], ack_tog};

  always @(posedge clk) begin
    commit_sync <= {commit_sync[0], commit_tog};
    if (commit_sync[1] != ack_tog) begin       // a new COMMIT: take over the parameters
      ftw    <= ftw_a;
      amp    <= {1'b0, amp_a[14:0]};
      enable <= ctrl_a[0];
      ack_tog <= commit_sync[1];
    end
  end

  initial begin ftw = 32'd0; amp = 16'd0; enable = 1'b0; end
endmodule
