# -----------------------------------------------------------------------------
# FPGA 16-QAM receiver with the Zadoff-Chu frame synchroniser and the band-edge FLL on the ADC path of the P501 base block design "system" (must be open).
#   qam16_rx (rtl/qam16_rx.v + qam_zc_sync.v + qpsk_fll.v): samples of RX1 -> FLL -> polyphase matched filter + timing loop + power AGC -> ZC frame synchroniser -> 16-QAM PLL -> slicer -> PRBS-15 checker,
#   registers at 0x9C470000 (16 KB, instance qam16_rx). QAM16RX=1 also replaces the QPSK transmitter by the 16-QAM frame transmitter (rtl/qam16_tx_fr.v) when QPSK=1. Two scripts in tutorial/qam16/steps/.
# -----------------------------------------------------------------------------
set ::p501_qam16_rx_steps_dir [file join [file dirname [file dirname [file normalize [info script]]]] tutorial qam16 steps]

proc p501_add_qam16_rx_chain {} {
  foreach s {step1_rx step2_constraints} {
    source [file join $::p501_qam16_rx_steps_dir $s.tcl]
  }
}
