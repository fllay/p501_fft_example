# -----------------------------------------------------------------------------
# DDS added to the DAC path of the P501 base block design "system" (must be open).
#
#   dds_regs   (dds_regs.v)       AXI-Lite registers 0x9C450000: frequency word, amplitude, enable
#      v   (hand-over to l_clk)
#   dds_core   Xilinx DDS Compiler 32-bit phase, 16-bit sin/cos, clock enable = dac_valid
#      v
#   dds_out    (dds_scale.v)      x amplitude, enable -> axi_ad9361 dac_data_i0 / dac_data_q0 (TX1)
#
# Four small scripts in tutorial/dds_steps/ (three blocks and the constraints); this proc runs them in order.
# The tutorial (tutorial/TUTORIAL_DDS.md) walks through the same steps by hand.
# -----------------------------------------------------------------------------
set ::p501_dds_steps_dir [file join [file dirname [file dirname [file normalize [info script]]]] tutorial dds_steps]

proc p501_add_dds_chain {} {
  foreach s {step1_regs step2_dds step3_dac step4_constraints} {
    source [file join $::p501_dds_steps_dir $s.tcl]
  }
}
