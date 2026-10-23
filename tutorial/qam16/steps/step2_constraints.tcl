# 16-QAM receiver step 2 - the two clock crossings of qam16_rx (src/qam16_rx_cdc.xdc): the Gray-coded write counter and the raw sample RAM.
set xdc [file join [file dirname [file dirname [file dirname [file dirname [file normalize [info script]]]]]] src qam16_rx_cdc.xdc]
if {[llength [get_files -quiet -of_objects [get_filesets constrs_1] $xdc]] == 0} {
  add_files -fileset constrs_1 -norecurse $xdc
}
