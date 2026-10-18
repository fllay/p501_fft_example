# -----------------------------------------------------------------------------
# FPGA QPSK receiver on the ADC path of the P501 base block design "system" (must be open). Chapter 4d.
#   qpsk_rx (rtl/qpsk_rx.v): samples of RX1 -> polyphase matched filter + timing loop + AGC + Costas loop -> bits -> PRBS-15 checker, registers at 0x9C470000.
# Two scripts in tutorial/qpsk/p501_rx/steps/. Independent of the transmitter (QPSK=1) and of the FFT chain: any combination works.
# -----------------------------------------------------------------------------
set ::p501_qpsk_rx_steps_dir [file join [file dirname [file dirname [file normalize [info script]]]] tutorial qpsk p501_rx steps]

proc p501_add_qpsk_rx_chain {} {
  foreach s {step1_rx step2_constraints} {
    source [file join $::p501_qpsk_rx_steps_dir $s.tcl]
  }
}
