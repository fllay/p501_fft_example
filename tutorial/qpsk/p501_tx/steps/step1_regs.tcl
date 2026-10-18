# QPSK step 1 - AXI-Lite register block: the same RTL as the DDS (rtl/dds_regs.v), here named qpsk_regs, at 0x9C460000.
#   0x04 CONTROL bit0 = enable (starts the PRBS from its first bit), 0x0C AMP (Q15), 0x14 COMMIT, 0x10 STATUS; the frequency word (0x08) is unused.
current_bd_design system

create_bd_cell -type module -reference dds_regs qpsk_regs
connect_bd_net [get_bd_pins sys_ps8/pl_clk0]               [get_bd_pins qpsk_regs/aclk]
connect_bd_net [get_bd_pins sys_rstgen/peripheral_aresetn] [get_bd_pins qpsk_regs/aresetn]
connect_bd_net [get_bd_pins axi_ad9361/l_clk]              [get_bd_pins qpsk_regs/clk]

set cpu [get_bd_cells axi_cpu_interconnect]
set mi [get_property CONFIG.NUM_MI $cpu]
set_property CONFIG.NUM_MI [expr {$mi + 1}] $cpu
connect_bd_intf_net [get_bd_intf_pins $cpu/[format M%02d_AXI $mi]] [get_bd_intf_pins qpsk_regs/s_axi]

assign_bd_address -offset 0x9C460000 -range 0x00001000 -with_name SEG_qpsk_regs \
  -target_address_space [get_bd_addr_spaces sys_ps8/Data] \
  [get_bd_addr_segs qpsk_regs/s_axi/*] -force
