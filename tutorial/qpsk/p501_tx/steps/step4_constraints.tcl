# QPSK step 4 - false paths of the parameter hand-over (src/dds_cdc.xdc covers instances named dds_regs and qpsk_regs).
set xdc [file join [file dirname [file dirname [file dirname [file dirname [file dirname [file normalize [info script]]]]]]] src dds_cdc.xdc]
if {[llength [get_files -quiet -of_objects [get_filesets constrs_1] $xdc]] == 0} {
  add_files -fileset constrs_1 -norecurse $xdc
}
