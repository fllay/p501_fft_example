# Step 3 - |X|^2 and the frame gate (rtl/fft_power_gate.v).
current_bd_design system

create_bd_cell -type module -reference fft_power_gate fft_power
connect_bd_net [get_bd_pins axi_ad9361/l_clk]  [get_bd_pins fft_power/clk]
connect_bd_net [get_bd_pins fft_rstn_inv/Res]  [get_bd_pins fft_power/resetn]
connect_bd_intf_net [get_bd_intf_pins fft_core/M_AXIS_DATA] [get_bd_intf_pins fft_power/s_axis]
