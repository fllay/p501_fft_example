# QPSK receiver step 2 - the two clock crossings of qpsk_rx_fe (src/qpsk_rx_fll_cdc.xdc: the same cells as the FLL receiver): the Gray-coded write counter and the sample RAM.
set xdc [file join [file dirname [file dirname [file dirname [file dirname [file dirname [file normalize [info script]]]]]]] src qpsk_rx_fll_cdc.xdc]
if {[llength [get_files -quiet -of_objects [get_filesets constrs_1] $xdc]] == 0} {
  add_files -fileset constrs_1 -norecurse $xdc
}
