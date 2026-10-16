# -----------------------------------------------------------------------------
# Builds the project created by create_project.tcl.
#
#   vivado -mode batch -source build.tcl -tclargs RUN=bit [JOBS=8] [NAME=p501_fft]
#
#   RUN=synth   synthesis only
#   RUN=impl    synthesis + implementation
#   RUN=bit     ... + bitstream, and collects the PYNQ overlay files in
#               build/overlay/: <NAME>.bit and <NAME>.hwh
#               (then run  python3 tools/fix_hwh.py build/overlay/<NAME>.hwh )
# -----------------------------------------------------------------------------
set script_dir [file dirname [file normalize [info script]]]
if {[info exists ::P501_BUILD_OPT]} {
  array set opt $::P501_BUILD_OPT
} else {
  array set opt {RUN bit JOBS 8 NAME p501_fft}
  foreach a $argv { if {[regexp {^(\w+)=(.*)$} $a -> k v]} { set opt($k) $v } }
}
set proj_dir [file join $script_dir build $opt(NAME)]
if {[llength [get_projects -quiet]] == 0} { open_project [file join $proj_dir $opt(NAME).xpr] }

switch -- $opt(RUN) {
  synth { launch_runs synth_1 -jobs $opt(JOBS); wait_on_run synth_1 }
  impl  { launch_runs impl_1 -jobs $opt(JOBS); wait_on_run impl_1 }
  bit   {
    launch_runs impl_1 -to_step write_bitstream -jobs $opt(JOBS)
    wait_on_run impl_1
    if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "implementation did not complete" }
    set out [file join $script_dir build overlay]
    file mkdir $out
    file copy -force [file join $proj_dir $opt(NAME).runs impl_1 system_top.bit] [file join $out $opt(NAME).bit]
    file copy -force [file join $proj_dir $opt(NAME).gen sources_1 bd system hw_handoff system.hwh] [file join $out $opt(NAME).hwh]
    puts "== overlay files: $out/$opt(NAME).bit  $out/$opt(NAME).hwh"
  }
  default { error "RUN must be synth, impl or bit" }
}
