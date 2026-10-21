# -----------------------------------------------------------------------------
# FPGA QPSK receiver with the band-edge FLL AND the 4th-power frequency estimator on the ADC path of the P501 base block design "system" (must be open). Chapter 4d, extension 2.
#   qpsk_rx_fe (rtl/qpsk_rx_fe.v + qpsk_fll.v + qpsk_fe.v): samples of RX1 -> FLL -> polyphase matched filter + timing loop + AGC -> [estimator] -> Costas loop -> bits -> PRBS-15 checker,
#   registers at 0x9C470000 (the same place and instance name as the other receivers, so the same drivers find it). Use QPSKRXFE=1 instead of QPSKRX=1 / QPSKRXFLL=1.
# Two scripts in tutorial/qpsk/p501_rx_fe/steps/.
# -----------------------------------------------------------------------------
set ::p501_qpsk_rx_fe_steps_dir [file join [file dirname [file dirname [file normalize [info script]]]] tutorial qpsk p501_rx_fe steps]

proc p501_add_qpsk_rx_fe_chain {} {
  foreach s {step1_rx_fe step2_constraints} {
    source [file join $::p501_qpsk_rx_fe_steps_dir $s.tcl]
  }
}
