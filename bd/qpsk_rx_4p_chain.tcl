# -----------------------------------------------------------------------------
# FPGA QPSK receiver, chain 3: polyphase matched filter -> 4th-power frequency estimator -> Costas loop (no FLL, no software in the loop) on the ADC path of the P501 base block design "system" (must be open).
#   qpsk_rx_4p (rtl/qpsk_rx_4p.v + qpsk_fe_auto.v + qpsk_fe.v): samples of RX1 -> polyphase matched filter + timing loop + AGC -> [estimator -> atan2 CORDIC -> loads the Costas frequency] -> Costas loop -> bits -> PRBS-15 checker,
#   registers at 0x9C470000 (the same place and instance name as the other receivers, so the same drivers find it). Use QPSKRX4P=1 instead of QPSKRX=1 / QPSKRXFLL=1.
# Two scripts in tutorial/qpsk/p501_rx_4p/steps/.
# -----------------------------------------------------------------------------
set ::p501_qpsk_rx_4p_steps_dir [file join [file dirname [file dirname [file normalize [info script]]]] tutorial qpsk p501_rx_4p steps]

proc p501_add_qpsk_rx_4p_chain {} {
  foreach s {step1_rx_4p step2_constraints} {
    source [file join $::p501_qpsk_rx_4p_steps_dir $s.tcl]
  }
}
