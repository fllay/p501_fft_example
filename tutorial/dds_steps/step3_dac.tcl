# DDS step 3 - amplitude / enable (rtl/dds_scale.v) and the connection to the DAC input of axi_ad9361.
# The DDS replaces the DAC DMA path for TX1 (I0/Q0): the two nets from the DAC FIFO are removed and
# the DDS drives the pins instead. TX2 (I1/Q1) stays connected to the DMA path.
current_bd_design system

create_bd_cell -type module -reference dds_scale dds_out
connect_bd_net [get_bd_pins axi_ad9361/l_clk]         [get_bd_pins dds_out/clk]
connect_bd_net [get_bd_pins dds_rstn_inv/Res]         [get_bd_pins dds_out/resetn]
connect_bd_net [get_bd_pins axi_ad9361/dac_valid_i0]  [get_bd_pins dds_out/ce]
connect_bd_net [get_bd_pins dds_core/m_axis_data_tdata] [get_bd_pins dds_out/dds_tdata]
connect_bd_net [get_bd_pins dds_regs/amp]             [get_bd_pins dds_out/amp]
connect_bd_net [get_bd_pins dds_regs/enable]          [get_bd_pins dds_out/enable]

# disconnect the DMA path from TX1 and put the DDS there
delete_bd_objs [get_bd_nets -of_objects [get_bd_pins axi_ad9361/dac_data_i0]] \
               [get_bd_nets -of_objects [get_bd_pins axi_ad9361/dac_data_q0]]
connect_bd_net [get_bd_pins dds_out/dac_i] [get_bd_pins axi_ad9361/dac_data_i0]
connect_bd_net [get_bd_pins dds_out/dac_q] [get_bd_pins axi_ad9361/dac_data_q0]
