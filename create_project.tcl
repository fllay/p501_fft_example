# -----------------------------------------------------------------------------
# P501 FFT example: creates a Vivado 2024.1 project containing the PZSDR P501
# base design (AD9361 + DMA + PS) plus a streaming FFT on the AD9361 ADC data.
#
#   vivado -mode batch -source create_project.tcl -tclargs [key=value ...]
#   (or in the Vivado GUI Tcl console:  source create_project.tcl)
#
# Options (all optional):
#   NFFT_LOG2=10     FFT length = 2**NFFT_LOG2 (4 ... 16)
#   SCALE_SHIFT=6    total FFT scaling in bits (even); default NFFT_LOG2-4. Raise it if the
#                    FFT output overflows, lower it for more dynamic range
#   LIB=<dir>        ADI hdl library with the packaged IP (axi_ad9361, axi_dmac, ...).
#                    Default: ../pzsdr-p501/hdl/library, then $P501_HDL_LIBRARY
#   RUN=none         none | synth | impl | bit   how far to build right away (or run build.tcl later)
#   JOBS=8           parallel jobs for synthesis/implementation
#   FFT=1            add the FFT chain (bd/fft_chain.tcl). 0 = leave it out
#   DDS=0            add the DAC DDS (bd/dds_chain.tcl). 1 = DDS drives TX1 instead of the DAC DMA
#   NAME=...         project name (created in ./build/<NAME>). Default: p501_fft (FFT only), p501_dds (DDS only),
#                    p501_fft_dds (both), p501_fft_tut (neither: the starting point of the tutorials)
# -----------------------------------------------------------------------------
set script_dir [file dirname [file normalize [info script]]]

array set opt {NFFT_LOG2 10 SCALE_SHIFT {} LIB {} RUN none JOBS 8 NAME {} FFT 1 DDS 0 PART xczu5ev-sfvc784-2-i}
foreach a $argv {
  if {[regexp {^(\w+)=(.*)$} $a -> k v]} { set opt($k) $v }
}

if {$opt(NAME) eq {}} {
  set opt(NAME) [expr {$opt(FFT) ? ($opt(DDS) ? "p501_fft_dds" : "p501_fft") : ($opt(DDS) ? "p501_dds" : "p501_fft_tut")}]
}

if {$opt(LIB) eq {}} {
  foreach c [list [file join $script_dir .. pzsdr-p501 hdl library] \
                  [expr {[info exists ::env(P501_HDL_LIBRARY)] ? $::env(P501_HDL_LIBRARY) : {}}]] {
    if {$c ne {} && [file isdirectory $c]} { set opt(LIB) [file normalize $c]; break }
  }
}
if {$opt(LIB) eq {} || ![file isdirectory $opt(LIB)]} {
  error "ADI hdl library not found - pass LIB=<dir> or set P501_HDL_LIBRARY"
}
if {$opt(NFFT_LOG2) < 4 || $opt(NFFT_LOG2) > 16} { error "NFFT_LOG2 must be 4..16" }
if {$opt(SCALE_SHIFT) eq {}} { set opt(SCALE_SHIFT) [expr {($opt(NFFT_LOG2) - 4) & ~1}] }

set proj_dir [file join $script_dir build $opt(NAME)]
puts "== P501 FFT example: NFFT=[expr {1 << $opt(NFFT_LOG2)}], scale shift=$opt(SCALE_SHIFT) bits, library=$opt(LIB), project=$proj_dir"

# ---- project, IP repository, sources ----------------------------------------
create_project $opt(NAME) $proj_dir -part $opt(PART) -force
set_property ip_repo_paths $opt(LIB) [current_project]
update_ip_catalog -rebuild

add_files -norecurse [glob [file join $script_dir src *.v]] [glob [file join $script_dir rtl *.v]]
add_files -fileset constrs_1 -norecurse [file join $script_dir src system_constr.xdc]
set ::P501_MEM_INIT_FILE [file join $script_dir src mem_init_sys.txt]
update_compile_order -fileset sources_1

# ---- block design: base design, then the FFT chain ---------------------------
source [file join $script_dir bd p501_base_bd.tcl]
source [file join $script_dir bd fft_chain.tcl]
source [file join $script_dir bd dds_chain.tcl]
if {$opt(FFT)} { p501_add_fft_chain $opt(NFFT_LOG2) $opt(SCALE_SHIFT) }
if {$opt(DDS)} { p501_add_dds_chain }
regenerate_bd_layout
validate_bd_design
save_bd_design

# ---- wrapper + top -----------------------------------------------------------
set bd_file [get_files system.bd]
generate_target all $bd_file
set wrapper [make_wrapper -files $bd_file -top]
add_files -norecurse $wrapper
set_property top system_top [current_fileset]
update_compile_order -fileset sources_1

puts "== project created. Open it with:  vivado $proj_dir/$opt(NAME).xpr"

# ---- optional build (same as running build.tcl afterwards) -------------------
if {$opt(RUN) ne "none"} {
  set ::P501_BUILD_OPT [array get opt]
  source [file join $script_dir build.tcl]
}
