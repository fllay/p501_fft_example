# -----------------------------------------------------------------------------
# FPGA OFDM receiver with the Schmidl-and-Cox synchroniser on the ADC path of the P501 base block design "system" (must be open).
#   ofdm_rx (rtl/ofdm_rx.v + ofdm_detect, ofdm_derot, ofdm_fft, ofdm_chan, ofdm_data, ofdm_div, ofdm_cordic): samples of RX1 -> detector -> carrier and gain -> channel estimate from two QPSK training symbols
#   -> 44 data symbols (FFT, equaliser, pilots, correction, 16-QAM slicer, PRBS-15 checker); registers at 0x9C470000 (16 KB, instance ofdm_rx; the capture RAM at +0x1000, H at +0x2000).
#   The transmitter is the base design's DAC DMA (the host sends the frame as a cyclic buffer). Two scripts in tutorial/ofdm/steps: step1_rx (the block and the bus), step2_constraints (the clock crossings).
# -----------------------------------------------------------------------------
set ::p501_ofdm_rx_steps_dir [file join [file dirname [file dirname [file normalize [info script]]]] tutorial ofdm steps]

# sts = 1: the receiver module is instantiated with its parameter STS = 1 (the 128-sample short training field, ID 0xDD520008); 0: the Schmidl-and-Cox symbol (ID 0xDD520007)
proc p501_add_ofdm_rx_chain {{sts 0}} {
  set ::p501_ofdm_rx_sts $sts
  foreach s {step1_rx step2_constraints} {
    source [file join $::p501_ofdm_rx_steps_dir $s.tcl]
  }
}
