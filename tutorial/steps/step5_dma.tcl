# Step 5 - a second ADI axi_dmac with an AXI-Stream source, wired to the PS: control registers on
# the CPU interconnect (0x9C440000), data to DDR through the HP1 interconnect (-> HPC0).
current_bd_design system

create_bd_cell -type ip -vlnv analog.com:user:axi_dmac:1.0 fft_dma
set_property -dict [list \
  CONFIG.DMA_TYPE_SRC         {1} \
  CONFIG.DMA_TYPE_DEST        {0} \
  CONFIG.DMA_DATA_WIDTH_SRC   {32} \
  CONFIG.DMA_DATA_WIDTH_DEST  {64} \
  CONFIG.CYCLIC               {false} \
  CONFIG.DMA_2D_TRANSFER      {false} \
  CONFIG.AXI_SLICE_SRC        {false} \
  CONFIG.AXI_SLICE_DEST       {false} \
  CONFIG.SYNC_TRANSFER_START  {false} \
  CONFIG.ALLOW_ASYM_MEM       {1} \
] [get_bd_cells fft_dma]

# stream side: l_clk domain; the DMA's transfer request tells the gate when to let frames through
connect_bd_net [get_bd_pins axi_ad9361/l_clk] [get_bd_pins fft_dma/s_axis_aclk]
connect_bd_intf_net [get_bd_intf_pins fft_fifo/M_AXIS] [get_bd_intf_pins fft_dma/s_axis]
connect_bd_net [get_bd_pins fft_dma/s_axis_xfer_req] [get_bd_pins fft_power/frame_en]

# PS side: one more port on each SmartConnect, PS clock and reset
set cpu [get_bd_cells axi_cpu_interconnect]
set mi [get_property CONFIG.NUM_MI $cpu]            ;# first free master port (4 in the base design)
set_property CONFIG.NUM_MI [expr {$mi + 1}] $cpu
set_property CONFIG.NUM_SI {2} [get_bd_cells axi_hp1_interconnect]
connect_bd_intf_net [get_bd_intf_pins $cpu/[format M%02d_AXI $mi]] [get_bd_intf_pins fft_dma/s_axi]
connect_bd_intf_net [get_bd_intf_pins fft_dma/m_dest_axi]           [get_bd_intf_pins axi_hp1_interconnect/S01_AXI]
connect_bd_net [get_bd_pins sys_ps8/pl_clk0] [get_bd_pins fft_dma/s_axi_aclk] [get_bd_pins fft_dma/m_dest_axi_aclk]
connect_bd_net [get_bd_pins sys_rstgen/peripheral_aresetn] \
               [get_bd_pins fft_dma/s_axi_aresetn] [get_bd_pins fft_dma/m_dest_axi_aresetn]

# addresses: registers at 0x9C440000 (4 KB), DDR_LOW window for the data port
assign_bd_address -offset 0x9C440000 -range 0x00001000 -with_name SEG_data_fft_dma \
  -target_address_space [get_bd_addr_spaces sys_ps8/Data] \
  [get_bd_addr_segs fft_dma/s_axi/axi_lite] -force
assign_bd_address -offset 0x00000000 -range 0x80000000 \
  -target_address_space [get_bd_addr_spaces fft_dma/m_dest_axi] \
  [get_bd_addr_segs sys_ps8/SAXIGP0/HPC0_DDR_LOW] -force
