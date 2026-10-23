# 16-QAM receiver, step 1 - rtl/qam16_rx.v on the ADC samples of axi_ad9361 (RX1) and on the AXI-Lite bus, registers at 0x9C470000 (16 KB: the capture RAM is at +0x1000).
#   engine and registers run on the PS clock (pl_clk0, 100 MHz); the samples cross from l_clk through a dual-clock RAM and a Gray-coded write counter.
current_bd_design system

create_bd_cell -type module -reference qam16_rx qam16_rx
connect_bd_net [get_bd_pins sys_ps8/pl_clk0]                [get_bd_pins qam16_rx/aclk]
connect_bd_net [get_bd_pins sys_rstgen/peripheral_aresetn]  [get_bd_pins qam16_rx/aresetn]
connect_bd_net [get_bd_pins axi_ad9361/l_clk]               [get_bd_pins qam16_rx/adc_clk]
connect_bd_net [get_bd_pins axi_ad9361/adc_valid_i0]        [get_bd_pins qam16_rx/adc_valid]
connect_bd_net [get_bd_pins axi_ad9361/adc_data_i0]         [get_bd_pins qam16_rx/adc_i]
connect_bd_net [get_bd_pins axi_ad9361/adc_data_q0]         [get_bd_pins qam16_rx/adc_q]

set cpu [get_bd_cells axi_cpu_interconnect]
set mi [get_property CONFIG.NUM_MI $cpu]
set_property CONFIG.NUM_MI [expr {$mi + 1}] $cpu
connect_bd_intf_net [get_bd_intf_pins $cpu/[format M%02d_AXI $mi]] [get_bd_intf_pins qam16_rx/s_axi]

assign_bd_address -offset 0x9C470000 -range 0x00004000 -with_name SEG_qam16_rx \
  -target_address_space [get_bd_addr_spaces sys_ps8/Data] \
  [get_bd_addr_segs qam16_rx/s_axi/*] -force
