# -----------------------------------------------------------------------------
# FPGA QPSK receiver WITH THE BAND-EDGE FLL on the ADC path of the P501 base block design "system" (must be open). Chapter 4d, extension.
#   qpsk_rx_fll (rtl/qpsk_rx_fll.v + qpsk_fll.v): samples of RX1 -> FLL (derotation + band-edge error) -> polyphase matched filter + timing loop + AGC -> Costas loop -> bits -> PRBS-15 checker,
#   registers at 0x9C470000 (the same place and instance name as the receiver without the FLL, so the same driver and notebook find it). Use QPSKRXFLL=1 instead of QPSKRX=1.
# Two scripts in tutorial/qpsk/p501_rx_fll/steps/.
# -----------------------------------------------------------------------------
set ::p501_qpsk_rx_fll_steps_dir [file join [file dirname [file dirname [file normalize [info script]]]] tutorial qpsk p501_rx_fll steps]

proc p501_add_qpsk_rx_fll_chain {} {
  foreach s {step1_rx_fll step2_constraints} {
    source [file join $::p501_qpsk_rx_fll_steps_dir $s.tcl]
  }
}
