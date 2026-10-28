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
#   QPSK=0           add the FPGA QPSK transmitter (bd/qpsk_chain.tcl, chapter 4c); it drives TX1 like the DDS, so DDS=1 and QPSK=1 exclude each other
#   QPSKRX=0         add the FPGA QPSK receiver (bd/qpsk_rx_chain.tcl, chapter 4d); independent of the others (QPSK=1 QPSKRX=1: both ends of the link in one overlay)
#   QPSKRXFLL=0      add the FPGA QPSK receiver WITH the band-edge FLL (bd/qpsk_rx_fll_chain.tcl): FLL -> polyphase -> Costas as in GNU Radio; use it instead of QPSKRX=1
#                    (QPSK=1 QPSKRXFLL=1: transmitter + receiver with the FLL in one overlay, p501_qpsk_trx_fll)
#   QPSKRXFE=0       add the FPGA QPSK receiver with the FLL AND the 4th-power frequency estimator (bd/qpsk_rx_fe_chain.tcl); use it instead of QPSKRX=1 / QPSKRXFLL=1
#                    (QPSK=1 QPSKRXFE=1: transmitter + receiver in one overlay, p501_qpsk_trx_fe)
#   QPSKRX4P=0       add the FPGA QPSK receiver of chain 3: polyphase -> 4th-power estimator -> Costas, the estimator loads the Costas frequency by itself (bd/qpsk_rx_4p_chain.tcl); use it instead of the other QPSKRX* options
#                    (QPSK=1 QPSKRX4P=1: transmitter + receiver in one overlay, p501_qpsk_trx_4p)
#   QPSKRXSYNC=0     add the FPGA QPSK receiver with the m-sequence frame synchroniser (bd/qpsk_rx_sync_chain.tcl, chapter 4e); use it instead of the other QPSKRX* options
#                    (QPSK=1 QPSKRXSYNC=1: transmitter + receiver in one overlay, p501_qpsk_trx_sync)
#   QAM16RX=0        add the FPGA 16-QAM receiver with the Zadoff-Chu frame synchroniser and the band-edge FLL (bd/qam16_rx_chain.tcl); use it instead of the QPSKRX* options
#                    (QPSK=1 QAM16RX=1: the 16-QAM frame transmitter + receiver in one overlay, p501_qam16_trx; the QPSK transmitter is replaced by rtl/qam16_tx_fr.v)
#   OFDMRXSC=0       add the FPGA OFDM receiver with the Schmidl-and-Cox synchroniser (bd/ofdm_rx_chain.tcl, tutorial/ofdm); use it instead of the QPSKRX* / QAM16RX options (project p501_ofdm_rx_sc;
#                    the transmitter is the base design's DAC DMA: the host sends the OFDM frame as a cyclic buffer, so use FFT=0 and no QPSK / DDS)
#   OFDMRXSTS=0      the same OFDM receiver with the 128-sample short training field instead of the Schmidl-and-Cox symbol (rtl parameter STS=1: lag 16, 48 products, preamble 128 samples; ID 0xDD520008;
#                    project p501_ofdm_rx_sts); it shares the address 0x9C470000 with OFDMRXSC, so use one of the two (the host sends the matching frame, tutorial/ofdm/make_ofdm_frame.py sts)
#   OFDMTXSC=0       add the FPGA OFDM transmitter of the Schmidl-and-Cox frame (rtl/ofdm_tx.v, STS = 0): the frame is made in the PL (PRBS-15 payload, IFFT, prefix) and replaces the DAC DMA path for TX1 through the
#                    register block of the QPSK chain (bd/qpsk_chain.tcl: 0x9C460000 enable, amplitude); alone: project p501_ofdm_tx_sc; with OFDMRXSC=1: transmitter + receiver in one overlay, p501_ofdm_trx_sc
#   OFDMTXSTS=0      the same for the frame with the 128-sample short training field (rtl/ofdm_tx.v, STS = 1; p501_ofdm_tx_sts, with OFDMRXSTS=1 p501_ofdm_trx_sts)
#   NAME=...         project name (created in ./build/<NAME>). Default: p501_fft (FFT only), p501_dds (DDS only),
#                    p501_fft_dds (both), p501_fft_tut (neither: the starting point of the tutorials)
# -----------------------------------------------------------------------------
set script_dir [file dirname [file normalize [info script]]]

array set opt {NFFT_LOG2 10 SCALE_SHIFT {} LIB {} RUN none JOBS 8 NAME {} FFT 1 DDS 0 QPSK 0 QPSKRX 0 QPSKRXFLL 0 QPSKRXFE 0 QPSKRX4P 0 QPSKRXSYNC 0 QAM16RX 0 OFDMRXSC 0 OFDMRXSTS 0 OFDMTXSC 0 OFDMTXSTS 0 PART xczu5ev-sfvc784-2-i}
foreach a $argv {
  if {[regexp {^(\w+)=(.*)$} $a -> k v]} { set opt($k) $v }
}

if {$opt(NAME) eq {}} {
  set opt(NAME) [expr {$opt(OFDMTXSTS) ? ($opt(OFDMRXSTS) ? "p501_ofdm_trx_sts" : "p501_ofdm_tx_sts") : $opt(OFDMTXSC) ? ($opt(OFDMRXSC) ? "p501_ofdm_trx_sc" : "p501_ofdm_tx_sc") : $opt(OFDMRXSTS) ? "p501_ofdm_rx_sts" : $opt(OFDMRXSC) ? "p501_ofdm_rx_sc" : $opt(QAM16RX) ? ($opt(QPSK) ? "p501_qam16_trx" : "p501_qam16_rx") : $opt(QPSKRXSYNC) ? ($opt(QPSK) ? "p501_qpsk_trx_sync" : "p501_qpsk_rx_sync") : $opt(QPSKRX4P) ? ($opt(QPSK) ? "p501_qpsk_trx_4p" : "p501_qpsk_rx_4p") : $opt(QPSKRXFE) ? ($opt(QPSK) ? "p501_qpsk_trx_fe" : "p501_qpsk_rx_fe") : $opt(QPSKRXFLL) ? ($opt(QPSK) ? "p501_qpsk_trx_fll" : "p501_qpsk_rx_fll") : $opt(QPSKRX) ? ($opt(QPSK) ? "p501_qpsk_trx" : "p501_qpsk_rx") : $opt(QPSK) ? ($opt(FFT) ? "p501_fft_qpsk" : "p501_qpsk") : ($opt(FFT) ? ($opt(DDS) ? "p501_fft_dds" : "p501_fft") : ($opt(DDS) ? "p501_dds" : "p501_fft_tut"))}]
}

if {($opt(QPSKRX) + $opt(QPSKRXFLL) + $opt(QPSKRXFE) + $opt(QPSKRX4P) + $opt(QPSKRXSYNC) + $opt(QAM16RX) + $opt(OFDMRXSC) + $opt(OFDMRXSTS)) > 1} { error "QPSKRX, QPSKRXFLL, QPSKRXFE, QPSKRX4P, QPSKRXSYNC, QAM16RX, OFDMRXSC and OFDMRXSTS all instantiate the receiver at 0x9C470000: choose one" }
if {$opt(OFDMTXSC) && $opt(OFDMTXSTS)} { error "OFDMTXSC and OFDMTXSTS both instantiate the transmitter: choose one" }
if {$opt(OFDMTXSC) && $opt(OFDMRXSTS)} { error "OFDMTXSC sends the Schmidl-and-Cox frame: pair it with OFDMRXSC, not OFDMRXSTS" }
if {$opt(OFDMTXSTS) && $opt(OFDMRXSC)} { error "OFDMTXSTS sends the STS frame: pair it with OFDMRXSTS, not OFDMRXSC" }
if {($opt(OFDMTXSC) || $opt(OFDMTXSTS)) && ($opt(QPSK) || $opt(DDS) || $opt(QAM16RX))} { error "the OFDM transmitter drives TX1 through the register block of the QPSK chain: do not combine it with QPSK, DDS or QAM16RX" }
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
source [file join $script_dir bd qpsk_chain.tcl]
source [file join $script_dir bd qpsk_rx_chain.tcl]
source [file join $script_dir bd qpsk_rx_fll_chain.tcl]
source [file join $script_dir bd qpsk_rx_fe_chain.tcl]
source [file join $script_dir bd qpsk_rx_4p_chain.tcl]
source [file join $script_dir bd qpsk_rx_sync_chain.tcl]
source [file join $script_dir bd qam16_rx_chain.tcl]
source [file join $script_dir bd ofdm_rx_chain.tcl]
if {$opt(DDS) && $opt(QPSK)} { error "DDS=1 and QPSK=1 both drive TX1: choose one" }
if {$opt(FFT)} { p501_add_fft_chain $opt(NFFT_LOG2) $opt(SCALE_SHIFT) }
if {$opt(DDS)} { p501_add_dds_chain }
if {$opt(QPSKRXSYNC)} { set ::p501_qpsk_tx_module qpsk_tx_fr }     ;# the overlay with the frame synchroniser transmits frames too (cfg = the FTW register: bit 31 frames, bits 15:0 payload symbols; 0 = the continuous PRBS-15)
if {$opt(QAM16RX)} { set ::p501_qpsk_tx_module qam16_tx_fr }        ;# the 16-QAM overlay transmits 16-QAM frames (rtl/qam16_tx_fr.v, same ports as qpsk_tx_fr)
if {$opt(OFDMTXSC) || $opt(OFDMTXSTS)} {
  set ::p501_qpsk_tx_module ofdm_tx                                  ;# the OFDM overlay transmits OFDM frames (rtl/ofdm_tx.v, same ports as qpsk_tx_fr plus the AXI clock for the IFFT)
  set ::p501_ofdm_tx_sts $opt(OFDMTXSTS)
  p501_add_qpsk_chain
}
if {$opt(QPSK)} { p501_add_qpsk_chain }
if {$opt(QPSKRX)} { p501_add_qpsk_rx_chain }
if {$opt(QPSKRXFLL)} { p501_add_qpsk_rx_fll_chain }
if {$opt(QPSKRXFE)} { p501_add_qpsk_rx_fe_chain }
if {$opt(QPSKRX4P)} { p501_add_qpsk_rx_4p_chain }
if {$opt(QPSKRXSYNC)} { p501_add_qpsk_rx_sync_chain }
if {$opt(QAM16RX)} { p501_add_qam16_rx_chain }
if {$opt(OFDMRXSC)} { p501_add_ofdm_rx_chain 0 }
if {$opt(OFDMRXSTS)} { p501_add_ofdm_rx_chain 1 }
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
