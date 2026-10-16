# P501 FFT example - a streaming FFT on the AD9361 data, as a PYNQ overlay

A starting point for doing signal processing in the FPGA on the PZSDR P501 (Zynq UltraScale+ XCZU5EV + AD9361).
One Tcl script creates a Vivado 2024.1 project that contains

* the **P501 base design** (Zynq PS, `axi_ad9361`, the ADI RX/TX DMAs, the RGMII Ethernet bridge) - recreated
  from the libiio/IIO reference project, which stays untouched (`../pzsdr-p501`), and
* a small **FFT chain** hanging off the AD9361 ADC data: frame generator -> Xilinx FFT -> |X|^2 -> FIFO -> DMA -> DDR.

The result is a PYNQ overlay (`.bit` + `.hwh`) from which Python reads FFT frames computed in the FPGA.

```
axi_ad9361 (clock l_clk = 2 x sample rate in 1R1T)
  adc_data_i0 / adc_data_q0 / adc_valid_i0
        |-----------------------> util_ad9361_adc_fifo -> cpack -> axi_ad9361_adc_dma   (unchanged raw capture)
        v
  fft_framer  (rtl/adc_frame_gen.v)    {Q,I} -> AXI-Stream, TLAST every N samples
        v
  fft_core    Xilinx FFT 9.1           pipelined streaming, 16 bit, scaled, natural order
        v                              (config word held constant: forward, fixed scaling)
  fft_power   (rtl/fft_power_gate.v)   |X|^2 (32 bit) + frame gate: a frame passes only while the DMA is running
        v
  fft_fifo    AXI-S FIFO, 2 frames
        v
  fft_dma     ADI axi_dmac, AXI-Stream source  ->  DDR through HPC0        control registers at 0x9C440000
```

Everything on the FFT side runs on `l_clk`; the DMA crosses into the PS clock internally.

## Quick start

Requirements: Vivado 2024.1, and the packaged ADI hdl library (the `library/` folder of the
[puzi501iio / pzsdr-p501](https://github.com/fllay/puzi501iio) repository). The script looks for it at
`../pzsdr-p501/hdl/library`; otherwise pass `LIB=` or set `P501_HDL_LIBRARY`.

```bash
# create the project, then look at it in the GUI
vivado -mode batch -source create_project.tcl
vivado build/p501_fft/p501_fft.xpr          # open the block design "system": FFT chain is the fft_* cells

# or build everything through the bitstream and collect the overlay files
vivado -mode batch -source create_project.tcl -tclargs RUN=bit
python3 tools/fix_hwh.py build/overlay/p501_fft.hwh        # make the HWH loadable by PYNQ (see below)
```

`create_project.tcl` options (`key=value` after `-tclargs`):

| option | default | meaning |
|---|---|---|
| `NFFT_LOG2` | 10 | FFT length 2^NFFT_LOG2 (4 ... 13 useful: the demo buffers hold 8192 samples) |
| `SCALE_SHIFT` | NFFT_LOG2-4 | total FFT scaling in bits (even). Raise it if the FFT output overflows, lower it for more dynamic range |
| `LIB` | `../pzsdr-p501/hdl/library` | ADI hdl library |
| `RUN` | none | `synth`, `impl` or `bit`: build right away. Or run `build.tcl` later (`-tclargs RUN=bit`) |
| `JOBS`, `NAME` | 8, `p501_fft` | parallel jobs, project name |

## Files

| path | purpose |
|---|---|
| `create_project.tcl` | entry point: project, sources, base block design, FFT chain, wrapper |
| `build.tcl` | synthesis / implementation / bitstream, collects `build/overlay/p501_fft.{bit,hwh}` |
| `bd/p501_base_bd.tcl` | the base block design, exported with `write_bd_tcl` from the reference project |
| `bd/fft_chain.tcl` | **the part to read and modify**: adds the FFT chain to that design |
| `rtl/adc_frame_gen.v`, `rtl/fft_power_gate.v` | the two small RTL blocks |
| `src/` | top level (`system_top.v`), constraints, and the helper RTL the base design needs (copied from the reference) |
| `tools/fix_hwh.py` | post-export fix of the `.hwh` for PYNQ |
| `notebook/P501_FFT_Example.ipynb` | PYNQ notebook that runs the overlay and plots the spectrum |

## How it works

* **Framing.** `adc_frame_gen` registers `{Q,I}` and a valid strobe from `axi_ad9361`. In 1R1T the valid is high every
  second `l_clk`, which the FFT core accepts (gaps in TVALID). It counts samples and raises TLAST every N, free-running.
* **FFT.** Pipelined streaming FFT, one sample per valid, natural-order output, bin *j* = frequency *j*·fs/N (negative
  frequencies in the upper half: `fftshift` it). The core wants one configuration word per frame; the length is fixed, so a
  constant is held on the config channel with TVALID high (forward transform + scaling schedule `SCALE_SHIFT`).
* **Power + frame gate.** `fft_power_gate` computes re^2+im^2 and passes a frame only if the DMA's `xfer_req` was high on
  its first bin. A DMA transfer therefore always starts on a frame boundary and gets whole frames; the FFT is never stalled.
  Program the DMA for `frames x N x 4` bytes and the next frames land in memory. The per-frame TLAST is *not* forwarded to
  the DMA: the ADI `axi_dmac` ends a transfer at the first TLAST, which would cut a multi-frame transfer after one frame.
* **Output.** 32-bit unsigned power per bin. Take `10*log10(avg + 1)` in Python.

## Verified

Built with Vivado 2024.1 (default options: N=1024, scale shift 6) and run on the board: the tone transmitted on bin 267 appears
on bin 267, 66 dB above the median floor, and the FPGA power matches NumPy's FFT of a raw ADC capture to 0.00 dB at the tone
(`notebook/P501_FFT_Example.ipynb` is saved with its outputs, `notebook/fft_result.png` is the figure). Post-route timing is met
(WNS +0.42 ns, WHS +0.01 ns); one minimum-pulse-width endpoint shows -0.002 ns, which comes from the reference base design.

## Using it from PYNQ

Copy `build/overlay/p501_fft.bit` and the fixed `p501_fft.hwh` to the board (same base name, same folder) and open
`notebook/P501_FFT_Example.ipynb`. In short:

```python
ol  = Overlay("/home/xilinx/jupyter_notebooks/p501_fft/p501_fft.bit")   # the FPGA now contains the FFT chain
# ... bring up the AD9361 exactly as in P501_AD9361_Test.ipynb (software side, unchanged) ...
dma = AxiDmac(ol.fft_dma)                       # same driver as for the ADC/DAC DMAs
buf = allocate(shape=(FRAMES, N), dtype=np.uint32)
dma.transfer_to_memory(buf.physical_address, buf.nbytes)     # FRAMES FFT frames of |X|^2
```

The AD9361 itself is still configured from software (SPI), so the notebook reuses the `ad9361_driver.py` flow.

## Things to know

* **`.hwh` fix.** PYNQ's metadata parser rejects two things Vivado emits for this design (orphan `sys_ps8` tie-off
  connections and the PS<->`gmii_to_rgmii` MDIO nets). `tools/fix_hwh.py` removes them; it reproduces the hand-fixed file used
  on the board (checked), and is idempotent.
* **Keep the whole base design.** Loading an overlay replaces the PL. The Ethernet port of this board runs through the PL
  (`gmii_to_rgmii`), so an overlay without it would take `eth0` down; USB networking is unaffected.
* **Clock `l_clk` = 2 x sample rate (1R1T).** Fine up to 61.44 MSPS (122.88 MHz). In 2R2T it is 4 x and the second channel
  would need a second chain (`adc_data_i1`, `adc_valid_i1`).
* **Limits of this starting point.** Rectangular window; fixed scaling; no averaging; the FFT is not back-pressured, so if the
  DMA stalls mid-frame (it should not at these rates) the frame is lost; the DMA interrupt is not wired to the PS.
  Natural next steps: a Hann window ROM before the FFT, K-frame averaging in BRAM, a CIC/FIR decimator for zoom FFT,
  run-time length and scaling via an AXI-Lite register block, two channels.
* **Warnings.** Vivado prints "connection ... overridden by the user" for a few pins of the new cells and one CRITICAL
  WARNING about `adf_spi_clk` having no FREQ_HZ; both come from interface inference / the reference design and are harmless.
