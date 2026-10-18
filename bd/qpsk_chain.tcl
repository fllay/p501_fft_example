# -----------------------------------------------------------------------------
# FPGA QPSK transmitter on the DAC path of the P501 base block design "system" (must be open). Chapter 4c.
#
#   qpsk_regs  (dds_regs.v)      AXI-Lite registers 0x9C460000: enable (starts the pattern), amplitude
#      v   (hand-over to l_clk)
#   qpsk_tx    (qpsk_tx.v)       PRBS-15 -> differential QPSK -> RRC pulse, 4 samples per symbol -> axi_ad9361 dac_data_i0 / dac_data_q0 (TX1)
#
# Four scripts in tutorial/qpsk/p501_tx/steps/. It replaces the DAC DMA path for TX1 like the DDS does: use one or the other.
# -----------------------------------------------------------------------------
set ::p501_qpsk_steps_dir [file join [file dirname [file dirname [file normalize [info script]]]] tutorial qpsk p501_tx steps]

proc p501_add_qpsk_chain {} {
  foreach s {step1_regs step2_tx step3_dac step4_constraints} {
    source [file join $::p501_qpsk_steps_dir $s.tcl]
  }
}
