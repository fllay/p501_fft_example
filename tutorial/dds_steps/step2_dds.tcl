# DDS step 2 - the Xilinx DDS Compiler: 32-bit phase accumulator, 16-bit sine and cosine.
# It advances once per DAC request (clock enable = dac_valid of axi_ad9361), the frequency word comes
# from the register block.
current_bd_design system

create_bd_cell -type ip -vlnv xilinx.com:ip:dds_compiler:6.0 dds_core
set_property -dict [list \
  CONFIG.Parameter_Entry      {Hardware_Parameters} \
  CONFIG.PartsPresent         {Phase_Generator_and_SIN_COS_LUT} \
  CONFIG.Phase_Width          {32} \
  CONFIG.Output_Width         {16} \
  CONFIG.Phase_Increment      {Streaming} \
  CONFIG.Phase_offset         {None} \
  CONFIG.Output_Selection     {Sine_and_Cosine} \
  CONFIG.Noise_Shaping        {Taylor_Series_Corrected} \
  CONFIG.Has_ACLKEN           {true} \
  CONFIG.Has_ARESETn          {true} \
  CONFIG.Latency_Configuration {Auto} \
  CONFIG.DDS_Clock_Rate       {122.88} \
] [get_bd_cells dds_core]

# active-low reset in the l_clk domain, and a constant 'valid' for the phase-increment stream
create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 dds_rstn_inv
set_property -dict [list CONFIG.C_OPERATION {not} CONFIG.C_SIZE {1}] [get_bd_cells dds_rstn_inv]
connect_bd_net [get_bd_pins axi_ad9361/rst] [get_bd_pins dds_rstn_inv/Op1]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 dds_pinc_valid
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] [get_bd_cells dds_pinc_valid]

connect_bd_net [get_bd_pins axi_ad9361/l_clk]         [get_bd_pins dds_core/aclk]
connect_bd_net [get_bd_pins axi_ad9361/dac_valid_i0]  [get_bd_pins dds_core/aclken]
connect_bd_net [get_bd_pins dds_rstn_inv/Res]         [get_bd_pins dds_core/aresetn]
connect_bd_net [get_bd_pins dds_regs/ftw]             [get_bd_pins dds_core/s_axis_phase_tdata]
connect_bd_net [get_bd_pins dds_pinc_valid/dout]      [get_bd_pins dds_core/s_axis_phase_tvalid]
