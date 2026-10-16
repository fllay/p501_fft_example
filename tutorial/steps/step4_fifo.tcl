# Step 4 - AXI-Stream FIFO, two frames deep (the gate may start a frame before the DMA is ready to take it).
# Needs:  set fft_nlog2 10
if {![info exists ::fft_nlog2]} { set ::fft_nlog2 10 }
current_bd_design system
set fdepth [expr {2 * (1 << $::fft_nlog2)}]

create_bd_cell -type ip -vlnv xilinx.com:ip:axis_data_fifo:2.0 fft_fifo
set_property -dict [list \
  CONFIG.TDATA_NUM_BYTES {4} \
  CONFIG.HAS_TLAST       {1} \
  CONFIG.FIFO_DEPTH      $fdepth \
] [get_bd_cells fft_fifo]
connect_bd_net [get_bd_pins axi_ad9361/l_clk]  [get_bd_pins fft_fifo/s_axis_aclk]
connect_bd_net [get_bd_pins fft_rstn_inv/Res]  [get_bd_pins fft_fifo/s_axis_aresetn]
connect_bd_intf_net [get_bd_intf_pins fft_power/m_axis] [get_bd_intf_pins fft_fifo/S_AXIS]
