# DDS step 4 - timing constraints for the parameter hand-over between the AXI clock and l_clk
# (src/dds_cdc.xdc): the hand-over is made safe by the toggle handshake in dds_regs.v, so the paths
# are declared false paths. Add the file to the constraints set (GUI: Add Sources -> Add or create constraints).
set xdc [file join [file dirname [file dirname [file dirname [file normalize [info script]]]]] src dds_cdc.xdc]
if {[llength [get_files -quiet -of_objects [get_filesets constrs_1] $xdc]] == 0} {
  add_files -fileset constrs_1 -norecurse $xdc
}
