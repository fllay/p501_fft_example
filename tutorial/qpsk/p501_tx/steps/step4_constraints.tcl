# QPSK step 4 - false paths of the parameter hand-over (src/dds_cdc.xdc covers instances named dds_regs and qpsk_regs).
set xdc [file join [file dirname [file dirname [file dirname [file dirname [file dirname [file normalize [info script]]]]]]] src dds_cdc.xdc]
if {[llength [get_files -quiet -of_objects [get_filesets constrs_1] $xdc]] == 0} {
  add_files -fileset constrs_1 -norecurse $xdc
}

# the OFDM transmitter (rtl/ofdm_tx.v) has three more clock crossings: src/ofdm_tx_cdc.xdc
if {[info exists ::p501_qpsk_tx_module] && $::p501_qpsk_tx_module eq "ofdm_tx"} {
  set xdc2 [file join [file dirname $xdc] ofdm_tx_cdc.xdc]
  if {[llength [get_files -quiet -of_objects [get_filesets constrs_1] $xdc2]] == 0} {
    add_files -fileset constrs_1 -norecurse $xdc2
  }
}
