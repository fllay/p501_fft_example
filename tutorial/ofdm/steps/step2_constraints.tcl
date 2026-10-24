# OFDM receiver step 2 - the clock crossings of ofdm_rx (src/ofdm_rx_cdc.xdc): the Gray-coded write counter and the two sample RAMs.
set xdc [file join [file dirname [file dirname [file dirname [file dirname [file normalize [info script]]]]]] src ofdm_rx_cdc.xdc]
if {[llength [get_files -quiet -of_objects [get_filesets constrs_1] $xdc]] == 0} {
  add_files -fileset constrs_1 -norecurse $xdc
}
