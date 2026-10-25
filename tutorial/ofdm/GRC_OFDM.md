# OFDM in GNU Radio Companion: transmitter and receiver, block by block

Two flowgraphs for the B210 (run them from this folder, `tutorial/ofdm`, after `source ../../tools/gnuradio_env.sh`):

| file | what it does |
|---|---|
| `ofdm_b210_frame_tx.grc` | the B210 transmits the OFDM frames (the same frame as the P501 receiver `p501_ofdm_rx_sc` expects, 850 MHz, 3.84 MS/s) |
| `ofdm_b210_frame_rx.grc` | the B210 receives and decodes them with **separate blocks**, one plot tab per stage; for teaching |

```bash
gnuradio-companion ofdm_b210_frame_rx.grc
```

The P501 can be the transmitter (notebook `notebook/P501_OFDM_Live.ipynb`, *P501 transmits* = OFDM frame, *Level* 500, *TX atten* 20 to 30 dB, antennas a few centimetres apart, **LO 850 MHz**) or the receiver; the B210 is the other end.
Without hardware: `python3 make_ofdm_capture.py` writes `ofdm_b210_capture.c64` (60 frames from the model with a 9 kHz carrier offset and 24 dB SNR; `python3 make_ofdm_capture.py ofdm_b210_capture.c64 35 9000 0.014` adds a DC offset like the B210's); in the receiver enable *File Source 0* and *Throttle 0*, disable the *UHD: USRP Source*.

## The receiver, stage by stage

The frame: S&C symbol | T1 | T2 | 44 data symbols (80 samples each, 16 of them the cyclic prefix) | 80 idle = 3840 samples = 1 ms (`PLAN_OFDM.md` section 12).

| tab | blocks | what to look at | in the FPGA (`rtl/`) / model |
|---|---|---|---|
| **1 Received signal** | UHD source, DC removal (*Single pole IIR* and *Subtract*), `|x|`, frequency sink | the spectrum is 28 subcarriers = 1.7 MHz wide, the spike at 0 Hz is the DC (the LO leakage of the B210); `|x|` (after the DC removal) shows frames of 3760 samples and the idle slot | ADC |
| **2 Frame detection** | *Delay 32*, *Conjugate*, *Multiply*, *Moving average 32* (S), *Complex to Mag^2*, the same for the energy (Eb and its delayed copy Ea), the energy guard (a one-pole average of |x|^2, squared, times a constant, *Add*), *Divide*, then the epy block **S&C frame detector** | M = &#124;S&#124;^2 / (Ea Eb) is a plateau of about 17 samples near 1 at the start of the S&C symbol (two equal halves of 32 samples), and below 0.35 elsewhere; the red line is the threshold | `ofdm_detect.v`, `ofdm_model.detect_sc` |
| **3 Frame and carrier correction** | **Coarse CFO correction**, **Fine CFO correction and T1/T2 check**, `|frame|`, number sinks | arg(S) / 32 is the coarse carrier offset (unambiguous to +-60 kHz); the two equal training symbols give the fine one; a false detection fails the T1/T2 repeat test | `ofdm_derot.v`, C_FINE states of `ofdm_rx.v` |
| **4 FFT** | *Keep M in N* (64 of 80: the cyclic prefix goes), *Stream to vector*, *FFT 64*, *Multiply const* (1/8), *Complex to Mag* | the mean |FFT| shows the 28 used bins; the constellation of the used bins before the equalizer is rotated and scaled by the channel (points on circles) | `ofdm_fft.v` |
| **5 Channel estimate** | **Channel estimator** | H[k] = (T1[k] + T2[k]) / 2 conj(TRAIN[k]): |H| is flat on a cable; arg H is a line (a delay: the FFT window starts 6 samples early, inside the cyclic prefix) | `ofdm_chan.v` |
| **6 Equalizer and decisions** | **Equalizer and pilot tracking**, **16-QAM slicer**, **Symbol error counter** | 16 clusters; arg g and |g| of the 4 pilots per symbol (the common phase error left by the carrier estimate); SER, errors, frames decoded against the PRBS-15 payload | `ofdm_data.v` |

**Why the DC is removed and the energy guard is there:** in the idle slot (80 samples) the B210 leaves only noise and the DC, and a constant is two equal halves of 32 samples: M reaches 1 in the idle slot, one symbol before the real S&C symbol (two spikes per frame in tab 2),
the frame is then cut at the wrong place and every frame fails the T1/T2 check (tabs 3 to 6 stay empty). The slow low-pass (time constant 10000 samples) estimates the DC and the subtraction removes most of it, but what is left (the mean of the frame itself, the noise of the slot) is still a constant
when the signal is clean, and M does not depend on the level. So M = |S|^2 / (Ea Eb + guard) has a **guard**: the square of 0.1 x 32 x the long-term average power. A window whose energy is below 10 % of the average (the idle slot) cannot reach M = 1;
the S&C symbol, which has the average power, is not changed. The FPGA has the same guard as an absolute level (`EMIN`) and the comparison `EA <= 2 E`.

The seven blocks written in Python (embedded blocks, their source is in the flowgraph: open them with a double click) are the ones that have no stock GNU Radio block: frame detector, the two carrier corrections, channel estimator, equalizer, slicer, error counter. The controls on top: **RX gain**, **S&C threshold** (the FPGA uses 0.65), **decode 1 frame in N**, **pilot smoothing** (the FPGA averages 5 symbols).

## What differs from the FPGA receiver

* **Only 1 frame in N is decoded** (default 8: 125 frames per second, 132 thousand symbols per second). The transmitter repeats the same frame 1000 times per second and the Python blocks cannot decode all of them in real time on an ordinary PC;
  the FPGA decodes every frame (2003 per 2 s). With *N = 1* run the flowgraph from a recording and not from the B210 (an overflow shows as *O* in the terminal).
* **M is normalised by Ea Eb** (the energies of the two 32-sample halves). The FPGA divides by Eb^2 only and has the guard `EA <= 2 E` instead (`rtl/ofdm_detect.v`, commit `d2ea5e6`): a strong frame that ends in noise would fire a detector with Eb^2 alone.
* Floating point instead of the integer model; the channel is estimated from T1 and T2 only (the S&C symbol is not used), and the noise estimate and the weights `W = conj(H) R / |H|^2` of the FPGA are replaced by a plain division `Y / H`.
* The frame start is taken at the centre of the plateau, as in the FPGA, and 6 samples early (`back`).

## Tests

* The seven blocks and the stock blocks in a Python flowgraph on the B210 recording `sim/adc_ofdm850b.npy` (273 frames, 850 MHz, B210 gain 79 dB, received by the P501 ADC): 269 frames decoded, symbol error rate 6.8e-4, EVM -17.8 dB,
  carrier +9050 Hz (the integer model of the FPGA gave 9.5e-4 and -16 to -19 dB on the same recording).
* The generated flowgraph (`grcc`) with the File Source on the synthetic recording of `make_ofdm_capture.py` (24 dB, 9 kHz), Qt offscreen, 30 s: 3821 frames decoded in real time, SER 3.9e-5 (the errors are at the seams of the replay loop).
* Recordings with a DC offset of 0.02 (0.2 of the rms): at 35 dB SNR without the DC removal 38 frames in 20 s are decoded (the idle slot fires the detector, as in the first B210 test of the flowgraph), with it 3295; at 60 dB SNR (the B210 and the P501 are this clean) the DC removal alone gives 867 frames, with the energy guard 3535
  (the replay is faster than real time: about 170 frames per second; about 1000 symbol errors in all are the first frames, while the DC estimate settles).
* **Not tested on the B210 by me** (the B210 was the transmitter of the other flowgraph): open the receiver with the P501 as transmitter and check the six tabs.
