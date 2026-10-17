# DDS step 1 - AXI-Lite register block (rtl/dds_regs.v): the parameters of the DDS live here and
# are set from PYNQ. Registers appear on the PS-side bus at 0x9C450000.
current_bd_design system

create_bd_cell -type module -reference dds_regs dds_regs

# the AXI side runs on the PS clock; `clk` is the sample clock (l_clk) the parameters are handed over to
connect_bd_net [get_bd_pins sys_ps8/pl_clk0]                    [get_bd_pins dds_regs/aclk]
connect_bd_net [get_bd_pins sys_rstgen/peripheral_aresetn]      [get_bd_pins dds_regs/aresetn]
connect_bd_net [get_bd_pins axi_ad9361/l_clk]                   [get_bd_pins dds_regs/clk]

# one more port on the CPU interconnect: the first free one
set cpu [get_bd_cells axi_cpu_interconnect]
set mi [get_property CONFIG.NUM_MI $cpu]
set_property CONFIG.NUM_MI [expr {$mi + 1}] $cpu
connect_bd_intf_net [get_bd_intf_pins $cpu/[format M%02d_AXI $mi]] [get_bd_intf_pins dds_regs/s_axi]

assign_bd_address -offset 0x9C450000 -range 0x00001000 -with_name SEG_dds_regs \
  -target_address_space [get_bd_addr_spaces sys_ps8/Data] \
  [get_bd_addr_segs dds_regs/s_axi/*] -force
