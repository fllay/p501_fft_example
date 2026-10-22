# -----------------------------------------------------------------------------
# FPGA QPSK receiver with the m-sequence FRAME SYNCHRONISER (chapter 4e, part 1) on the ADC path of the P501 base block design "system" (must be open).
#   qpsk_rx_sync (rtl/qpsk_rx_sync.v + qpsk_sync.v): samples of RX1 -> polyphase matched filter + timing loop + AGC -> Costas loop -> bits -> PRBS-15 checker (counting only inside the payload gate),
#   and, beside the engine: phase steps -> correlation with the 63-chip m-sequence -> peaks -> frame tracker -> payload gate. Registers at 0x9C470000 (the same place and instance name as the other receivers).
#   Use QPSKRXSYNC=1 instead of QPSKRX=1 / QPSKRXFLL=1 / QPSKRX4P=1. Two scripts in tutorial/qpsk/p501_sync/steps/.
# -----------------------------------------------------------------------------
set ::p501_qpsk_rx_sync_steps_dir [file join [file dirname [file dirname [file normalize [info script]]]] tutorial qpsk p501_sync steps]

proc p501_add_qpsk_rx_sync_chain {} {
  foreach s {step1_rx_sync step2_constraints} {
    source [file join $::p501_qpsk_rx_sync_steps_dir $s.tcl]
  }
}
