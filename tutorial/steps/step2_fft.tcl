# Step 2 - the Xilinx FFT IP (v9.1, pipelined streaming) and its constant configuration word.
# Needs:  set fft_nlog2 10 ;  set fft_scale_shift 6   (total scaling in bits, even; default nlog2-4)
if {![info exists ::fft_nlog2]} { set ::fft_nlog2 10 }
if {![info exists ::fft_scale_shift]} { set ::fft_scale_shift [expr {($::fft_nlog2 - 4) & ~1}] }
current_bd_design system
set nfft [expr {1 << $::fft_nlog2}]

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

# The core wants a configuration word per frame. The length is fixed, so the word is constant:
# bit 0 = FWD_INV (1 = forward), then SCALE_SCH = 2 bits per radix-2^2 stage, first stage in the
# least significant bits; a field value of 2 divides by 4 in that stage. fft_scale_shift (even, bits)
# = total right shift: the first fft_scale_shift/2 stages divide by 4, the rest do not scale.
# A full-scale complex tone then gives a bin amplitude of about A * N / 2^shift: keep it below 2^15
# (raise the shift if the FFT output overflows) but high enough that the noise floor is not
# quantised to zero (N / 2^shift ~ 1..64).
set cfg_w [expr {[get_property LEFT [get_bd_pins fft_core/s_axis_config_tdata]] + 1}]
set stages [expr {($::fft_nlog2 + 1) / 2}]
set k [expr {$::fft_scale_shift / 2}]
if {$k > $stages} { set k $stages }
set sched 0
for {set i 0} {$i < $k} {incr i} { set sched [expr {$sched | (2 << (2 * $i))}] }
set cfg_val [expr {($sched << 1) | 1}]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 fft_cfg_data
set_property -dict [list CONFIG.CONST_WIDTH $cfg_w CONFIG.CONST_VAL $cfg_val] [get_bd_cells fft_cfg_data]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 fft_cfg_valid
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] [get_bd_cells fft_cfg_valid]

# clock / reset (same l_clk domain as the framer)
connect_bd_net [get_bd_pins axi_ad9361/l_clk]  [get_bd_pins fft_core/aclk]
connect_bd_net [get_bd_pins fft_rstn_inv/Res]  [get_bd_pins fft_core/aresetn]

# data in, configuration (TVALID tied high: the core's config FIFO consumes one copy per frame)
connect_bd_intf_net [get_bd_intf_pins fft_framer/m_axis] [get_bd_intf_pins fft_core/S_AXIS_DATA]
connect_bd_net [get_bd_pins fft_cfg_data/dout]  [get_bd_pins fft_core/s_axis_config_tdata]
connect_bd_net [get_bd_pins fft_cfg_valid/dout] [get_bd_pins fft_core/s_axis_config_tvalid]
