# -----------------------------------------------------------------------------
# FFT chain added to the P501 base block design "system" (must be open).
#
#   axi_ad9361 (adc_data_i0/q0, adc_valid_i0, l_clk)
#        |  (the existing path to util_ad9361_adc_fifo / adc DMA is untouched)
#        v
#   fft_framer   (adc_frame_gen.v)   {Q,I} -> AXI-S, TLAST every 2^NFFT_LOG2 samples
#        v
#   fft_core     Xilinx FFT v9.1, pipelined streaming, scaled, natural order
#        v
#   fft_power    (fft_power_gate.v)  |X|^2 and frame gate (frames only while the DMA is active)
#        v
#   fft_fifo     AXI-S FIFO, 2 frames deep
#        v
#   fft_dma      ADI axi_dmac, AXI-Stream source -> DDR via HPC0   (PS: 0x9C440000)
#
# Everything on the FFT side runs on the AD9361 interface clock l_clk.
#
# The chain is built by five small scripts in tutorial/steps/, one block each: this proc just
# runs them in order. The tutorial (tutorial/TUTORIAL.md) walks through the same steps by hand.
# Usage: p501_add_fft_chain <log2 of the FFT length> <total scaling shift in bits, even>
# -----------------------------------------------------------------------------
set ::p501_steps_dir [file join [file dirname [file dirname [file normalize [info script]]]] tutorial steps]

proc p501_add_fft_chain {nlog2 scale_shift} {
  set ::fft_nlog2 $nlog2
  set ::fft_scale_shift $scale_shift
  foreach s {step1_framer step2_fft step3_power step4_fifo step5_dma} {
    source [file join $::p501_steps_dir $s.tcl]
  }
}
