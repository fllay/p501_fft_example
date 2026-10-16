# -----------------------------------------------------------------------------
# FFT chain added to the P501 base block design "system" (must be open).
#
#   axi_ad9361 (adc_data_i0/q0, adc_valid_i0, l_clk)
#        |  (the existing path to util_ad9361_adc_fifo / adc DMA is untouched)
#        v
#   fft_framer   (adc_frame_gen.v)   {Q,I} -> AXI-S, TLAST every 2^NFFT_LOG2 samples
#        v
#   fft_core     Xilinx FFT v9.1, pipelined streaming, scaled, natural order
#        v
#   fft_power    (fft_power_gate.v)  |X|^2 and frame gate (frames only while the DMA is active)
#        v
#   fft_fifo     AXI-S FIFO, 2 frames deep
#        v
#   fft_dma      ADI axi_dmac, AXI-Stream source -> DDR via HPC0   (PS: 0x9C440000)
#
# Everything on the FFT side runs on the AD9361 interface clock l_clk.
# Usage: p501_add_fft_chain <log2 of the FFT length> <total scaling shift in bits, even>
# -----------------------------------------------------------------------------
proc p501_add_fft_chain {nlog2 scale_shift} {
  set nfft   [expr {1 << $nlog2}]
  set fdepth [expr {2 * $nfft}]
  current_bd_design system

  # ---- RTL helpers -----------------------------------------------------------
  create_bd_cell -type module -reference adc_frame_gen fft_framer
  set_property CONFIG.N_LOG2 $nlog2 [get_bd_cells fft_framer]
  create_bd_cell -type module -reference fft_power_gate fft_power

  # ---- Xilinx FFT ------------------------------------------------------------
  create_bd_cell -type ip -vlnv xilinx.com:ip:xfft:9.1 fft_core
  set_property -dict [list \
    CONFIG.transform_length          $nfft \
    CONFIG.implementation_options    {pipelined_streaming_io} \
    CONFIG.input_width               {16} \
    CONFIG.phase_factor_width        {16} \
    CONFIG.scaling_options           {scaled} \
    CONFIG.rounding_modes            {convergent_rounding} \
    CONFIG.output_ordering           {natural_order} \
    CONFIG.throttle_scheme           {nonrealtime} \
    CONFIG.target_clock_frequency    {150} \
    CONFIG.aresetn                   {true} \
  ] [get_bd_cells fft_core]

  # The core wants a configuration word per frame. The length is fixed, so the
  # word is constant: bit 0 = FWD_INV (1 = forward), then SCALE_SCH = 2 bits per
  # radix-2^2 stage, first stage in the least significant bits; a field value of
  # 2 divides by 4 in that stage. scale_shift (even, bits) = total right shift:
  # the first scale_shift/2 stages divide by 4, the rest do not scale. The
  # bin amplitude of a full-scale complex tone is then about A * N / 2^shift:
  # keep it below 2^15 (raise scale_shift if the FFT output overflows) but low
  # enough that the noise floor is not quantised to zero (N / 2^shift ~ 1..64).
  # TVALID is tied high: the core's config FIFO simply consumes one copy per frame.
  # (The width is padded to whole bytes by the core.)
  set cfg_w [expr {[get_property LEFT [get_bd_pins fft_core/s_axis_config_tdata]] + 1}]
  set stages [expr {($nlog2 + 1) / 2}]
  set k [expr {$scale_shift / 2}]
  if {$k > $stages} { set k $stages }
  set sched 0
  for {set i 0} {$i < $k} {incr i} { set sched [expr {$sched | (2 << (2 * $i))}] }
  set cfg_val [expr {($sched << 1) | 1}]
  create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 fft_cfg_data
  set_property -dict [list CONFIG.CONST_WIDTH $cfg_w CONFIG.CONST_VAL $cfg_val] [get_bd_cells fft_cfg_data]
  create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 fft_cfg_valid
  set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] [get_bd_cells fft_cfg_valid]

  # ---- output FIFO + DMA -----------------------------------------------------
  create_bd_cell -type ip -vlnv xilinx.com:ip:axis_data_fifo:2.0 fft_fifo
  set_property -dict [list \
    CONFIG.TDATA_NUM_BYTES {4} \
    CONFIG.HAS_TLAST       {1} \
    CONFIG.FIFO_DEPTH      $fdepth \
  ] [get_bd_cells fft_fifo]

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

  # active-low reset for the l_clk domain
  create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 fft_rstn_inv
  set_property -dict [list CONFIG.C_OPERATION {not} CONFIG.C_SIZE {1}] [get_bd_cells fft_rstn_inv]

  # ---- l_clk domain wiring ---------------------------------------------------
  connect_bd_net [get_bd_pins axi_ad9361/rst] [get_bd_pins fft_rstn_inv/Op1]
  set l_clk  [get_bd_pins axi_ad9361/l_clk]
  set l_rstn [get_bd_pins fft_rstn_inv/Res]
  connect_bd_net $l_clk  [get_bd_pins fft_framer/clk] [get_bd_pins fft_power/clk] \
                         [get_bd_pins fft_core/aclk]  [get_bd_pins fft_fifo/s_axis_aclk] \
                         [get_bd_pins fft_dma/s_axis_aclk]
  connect_bd_net $l_rstn [get_bd_pins fft_framer/resetn] [get_bd_pins fft_power/resetn] \
                         [get_bd_pins fft_core/aresetn]  [get_bd_pins fft_fifo/s_axis_aresetn]

  # ADC samples (channel 0 = RX1): fan out in addition to the existing ADC FIFO
  connect_bd_net [get_bd_pins axi_ad9361/adc_data_i0]  [get_bd_pins fft_framer/smp_i]
  connect_bd_net [get_bd_pins axi_ad9361/adc_data_q0]  [get_bd_pins fft_framer/smp_q]
  connect_bd_net [get_bd_pins axi_ad9361/adc_valid_i0] [get_bd_pins fft_framer/smp_valid]

  # stream
  connect_bd_intf_net [get_bd_intf_pins fft_framer/m_axis]    [get_bd_intf_pins fft_core/S_AXIS_DATA]
  connect_bd_net [get_bd_pins fft_cfg_data/dout]  [get_bd_pins fft_core/s_axis_config_tdata]
  connect_bd_net [get_bd_pins fft_cfg_valid/dout] [get_bd_pins fft_core/s_axis_config_tvalid]
  connect_bd_intf_net [get_bd_intf_pins fft_core/M_AXIS_DATA] [get_bd_intf_pins fft_power/s_axis]
  connect_bd_intf_net [get_bd_intf_pins fft_power/m_axis]     [get_bd_intf_pins fft_fifo/S_AXIS]
  connect_bd_intf_net [get_bd_intf_pins fft_fifo/M_AXIS]      [get_bd_intf_pins fft_dma/s_axis]
  connect_bd_net [get_bd_pins fft_dma/s_axis_xfer_req] [get_bd_pins fft_power/frame_en]

  # ---- PS side: control register bus and DDR access ---------------------------
  set_property CONFIG.NUM_MI {5} [get_bd_cells axi_cpu_interconnect]
  set_property CONFIG.NUM_SI {2} [get_bd_cells axi_hp1_interconnect]
  connect_bd_intf_net [get_bd_intf_pins axi_cpu_interconnect/M04_AXI] [get_bd_intf_pins fft_dma/s_axi]
  connect_bd_intf_net [get_bd_intf_pins fft_dma/m_dest_axi]           [get_bd_intf_pins axi_hp1_interconnect/S01_AXI]
  connect_bd_net [get_bd_pins sys_ps8/pl_clk0] [get_bd_pins fft_dma/s_axi_aclk] [get_bd_pins fft_dma/m_dest_axi_aclk]
  connect_bd_net [get_bd_pins sys_rstgen/peripheral_aresetn] \
                 [get_bd_pins fft_dma/s_axi_aresetn] [get_bd_pins fft_dma/m_dest_axi_aresetn]

  assign_bd_address -offset 0x9C440000 -range 0x00001000 -with_name SEG_data_fft_dma \
    -target_address_space [get_bd_addr_spaces sys_ps8/Data] \
    [get_bd_addr_segs fft_dma/s_axi/axi_lite] -force
  assign_bd_address -offset 0x00000000 -range 0x80000000 \
    -target_address_space [get_bd_addr_spaces fft_dma/m_dest_axi] \
    [get_bd_addr_segs sys_ps8/SAXIGP0/HPC0_DDR_LOW] -force
}
