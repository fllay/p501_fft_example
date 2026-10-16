# Step 1 - frame generator: ADC samples -> AXI-Stream with a TLAST every 2^N_LOG2 samples.
# Needs (set once in the Tcl console):  set fft_nlog2 10
if {![info exists ::fft_nlog2]} { set ::fft_nlog2 10 }
current_bd_design system

# the RTL block (rtl/adc_frame_gen.v is already a project source) as a module reference
create_bd_cell -type module -reference adc_frame_gen fft_framer
set_property CONFIG.N_LOG2 $::fft_nlog2 [get_bd_cells fft_framer]

# axi_ad9361/rst is active high; the FFT-side blocks want an active-low reset in the same (l_clk) domain
create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 fft_rstn_inv
set_property -dict [list CONFIG.C_OPERATION {not} CONFIG.C_SIZE {1}] [get_bd_cells fft_rstn_inv]
connect_bd_net [get_bd_pins axi_ad9361/rst] [get_bd_pins fft_rstn_inv/Op1]

# clock = the AD9361 interface clock l_clk, reset = inverted axi_ad9361/rst
connect_bd_net [get_bd_pins axi_ad9361/l_clk]  [get_bd_pins fft_framer/clk]
connect_bd_net [get_bd_pins fft_rstn_inv/Res]  [get_bd_pins fft_framer/resetn]

# ADC samples of channel 0 (RX1). These nets also feed the existing ADC FIFO / DMA: the raw capture path is untouched.
connect_bd_net [get_bd_pins axi_ad9361/adc_data_i0]  [get_bd_pins fft_framer/smp_i]
connect_bd_net [get_bd_pins axi_ad9361/adc_data_q0]  [get_bd_pins fft_framer/smp_q]
connect_bd_net [get_bd_pins axi_ad9361/adc_valid_i0] [get_bd_pins fft_framer/smp_valid]
