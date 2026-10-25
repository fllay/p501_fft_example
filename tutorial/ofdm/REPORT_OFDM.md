# OFDM on the P501: status report (2026-10-25)

16-QAM OFDM with QPSK training and pilots, Schmidl-and-Cox synchronisation, in the P501 FPGA (overlay `p501_ofdm_rx_sc`), tested against its own DAC, against a USRP B210 and in GNU Radio.
Design and every step: `PLAN_OFDM.md`; raw results: `results_board_loopback.txt`, `results_board_air.txt`, `results_gain_sweep.txt`, `results_iq_image.txt`; GNU Radio: `GRC_OFDM.md`.

## 1. What exists

| part | file | state |
|---|---|---|
| frame and receiver design, float model | `PLAN_OFDM.md`, `ofdm_model.py`, `ofdm_study.py`, `ofdm_sync_compare.py` | done (S&C and the 128-sample STS compared: equal at 22 dB and more, S&C 48 samples shorter) |
| integer model (the specification of the RTL) | `ofdm_fixed.py`, `test_ofdm_fixed.py` | done; within 0.1 to 0.3 dB of the float model |
| RTL: detector, derotator, FFT, channel estimate, data symbols, top level | `rtl/ofdm_detect.v`, `ofdm_derot.v`, `ofdm_fft.v`, `ofdm_chan.v`, `ofdm_data.v`, `ofdm_rx.v` | done, every block bit-exact against the integer model in xsim (`sim/run_*.sh`) |
| overlay | `create_project.tcl ... FFT=0 OFDMRXSC=1` | built twice (before and after the detector guard): 31,426 LUT (26.8 %), 27,599 FF, 9 BRAM, 176 DSP, setup +0.417 ns, hold +0.011 ns, one pulse-width endpoint -0.002 ns as in the base design |
| board driver and live notebook | `notebook/p501_ofdm_rx.py`, `notebook/P501_OFDM_Live.ipynb` | done; 22 self-test checks pass headless on the board |
| B210 transmitter | `ofdm_frame_tx.py`, `ofdm_b210_frame_tx.grc` | done |
| B210 receiver in GNU Radio, block by block | `ofdm_b210_frame_rx.grc`, `GRC_OFDM.md` | done; works on the B210 (checked by you) |
| B210 receiver from the stock gr-digital OFDM blocks | `ofdm_b210_frame_rx_stock.grc`, `GRC_OFDM.md` | done; works on the B210 after three changes (section 2c); you ran it in the GUI |
| not done | 128-sample STS overlay (second synchroniser), FPGA OFDM transmitter, OFDM tutorial chapter, the common soft-output interface, FEC | open |

Throughput: 3840 samples = 1 ms per frame, 44 data symbols x 24 subcarriers x 4 bits = 4224 bits per frame, 4.2 Mb/s; the receiver decodes every frame (2003 per 2 s, nothing late).

## 2. Results

**Digital loopback** (inside the AD9361, nothing radiated; `results_board_loopback.txt`): 2003 frames in 2 s, all found, none rejected, **0 symbol errors in 2,115,168 symbols** at ADC levels of 65, 194 and 389 counts; EVM -38.4, -46.2 and -45.6 dB.

**P501 to P501 over the air** (TX1 to RX1, antennas a few centimetres apart, `results_board_air.txt`): at 20 dB TX attenuation (SNR 23 dB) the symbol error rate is 4.5e-4 to 4.9e-4, EVM -18 to -19 dB; the errors follow the AWGN model above 19 dB SNR (22 dB: 4.9e-3, 24 dB: 2.2e-2, 26 dB: 7.3e-2, 28 dB: 0.17, 30 dB: 0.31 with the level at 24 counts; 40 dB attenuation: no lock).

**B210 to P501 at 850 MHz, gain sweep** (new; `results_gain_sweep.txt`, figure below): 5 gains x 3 restarts of the B210 transmitter x 8 windows of 2 s (2.1 M symbols each), RX gain index 70, rms 0.25, idle slot empty.

| B210 gain | level at the ADC | SNR | EVM | symbol error rate (median of 24 windows) | windows below 1e-4 |
|---|---|---|---|---|---|
| 72 dB | 70 counts | 21 to 23 dB | -18 to -19 dB | 3.0e-3 | 0 % |
| 76 dB | 110 | 24 to 25 dB | -22 dB | 6e-5 | 62 % |
| 79 dB | 160 | 26 dB | -23.5 dB | 0 | 96 % |
| 82 dB | 225 | 27.5 dB | -25 dB | 0 | 100 % |
| 85 dB | 310 | 28 to 29 dB | -24 to -25 dB | 0 (7e-6 in one window) | 100 % |

![SER against the B210 gain](../img/ofdm_gain_sweep.png)

**The link is limited by the SNR and nothing else.** The level at the ADC rises by 3 dB for every 3 dB of B210 gain (70, 112, 160, 225, 315 counts), so the B210 does not compress up to 85 dB at rms 0.25 (peaks 0.85 of full scale); at 82 and 85 dB 47 of 48 windows (2.1 M symbols each) have no symbol error (the 48th: 7e-6), at 79 dB 23 of 24 (the 24th: 1e-3).
Three cold starts at 85 dB with the receiver started together with the transmitter (14 windows each) also gave 0 errors in 38 of 42 windows (the other four: 1e-2 with 8 bad frames, 1e-4, 9e-7 and 5e-7).

**Corrections to what I said earlier** (the earlier B210 runs were noisier than these, and I attributed it to the wrong causes):
* *"The B210 compresses above about 78 dB"* (carried over from the single-carrier 16-QAM link at rms 0.5) does not hold for OFDM at rms 0.25: no compression up to 85 dB. The erratic runs of the evening before (SER 6e-3 median at 85 dB, bursts of bad frames at 79 dB) had a level of 100 to 216 counts against 310 now at the same gain:
  a different antenna position or a different state of the B210 or of the AD9361 receiver (its analog state is random after every bring-up), not the gain. I cannot say which; in 15 restarts today there was no bad state.
* *"A -20 dB floor of the TX1 to RX1 path might be the IQ image"*: it is not. A tone through TX1 and RX1 (`p501_iq_image.py`, three bring-ups, +120, +480 and +840 kHz) has its image at **-48 dBc** (the noise floor of the measurement in 7 bins, so the image rejection is at least 48 dB), the second and third harmonics at the noise floor too; the only spur is the **DC at -14 to -17 dBc** (LO leakage of the transmitter plus the DC offset of the receiver). So the EVM of -18 to -19 dB at an SNR of 23 dB is the noise plus the estimation noise
  (the channel is estimated from only two symbols, +1.8 dB), not a distortion.

![tones through TX1 and RX1](../img/ofdm_iq_image.png)

## 2b. A live run: the GNU Radio transmitter and the notebook receiver

The B210 runs `ofdm_b210_frame_tx.grc` (850 MHz, TX gain 79 dB, rms 0.25, antennas a few centimetres apart); the P501 runs `notebook/P501_OFDM_Live.ipynb` (RX gain 70, detector threshold 166 = 0.65, receiver started with *Start receiver*, display on).

![the transmitter in GNU Radio Companion](../img/ofdm_real_grc_tx.png)

The transmitter window: the spectrum of the transmitted signal is the 28 subcarriers (1.7 MHz wide, a notch at 0 where the unused DC subcarrier is) about 20 dB above the skirts that begin at +-1 MHz; the envelope shows two frames of 3840 samples with the idle slot of 80 samples (about 20 us) at the end of each, and peaks of 0.84 of the full scale at an rms of 0.25 (3.4 x the rms).

![the live notebook receiving it](../img/ofdm_real_notebook.png)

What the notebook shows (one picture, after the start-up):

| item | reading |
|---|---|
| frames | 15,678 decoded, 997 per second (of about 1000); every frame the detector finds is decoded |
| EVM, SNR | -19.4 dB for the last frame, -23.8 dB over the 1024 symbols of the picture; SNR 25.1 dB from the channel estimate and the noise sum |
| symbol errors | 5.1e-5 over the last 2 s; the strip of log10 SER is at the floor (1e-7) except for one burst |
| carrier | +8916 Hz (coarse +10099 Hz): the natural offset of the B210 and the P501 |
| level, gain | 188 counts rms at the ADC, gain 2.12 (the receiver brings the samples to 400 counts for the FFT) |
| constellation, channel | 16 clean clusters; |H| flat over the 28 subcarriers; EVM per data subcarrier flat (no weak subcarrier, no tilt) |
| late, overflow | late 0, fft_ovf 0, overrun 0; `ovf` 1 is the sticky flag that the first garbage frames set |

The counters *since the start* look worse than the link: found 81,158, **rejected 65,476**, bad frames 915, symbol errors 905,843 (SER 9.8e-2). They include the first part of the run, which the strips show: the frames per second climbed to 1000 over about 30 s and the carrier reading wandered (-6.9 to +11 kHz) until the signal was stable.
That looks like a receiver that was started before the transmitter was up (the detector fires on noise, the T1/T2 check throws those detections away: 65,476 rejected), but I do not know the order of the starts in this run, so it is the likely reading, not a measured one.
Start the transmitter first and the receiver 10 s later (as the notebook says), or use *Stop receiver* / *Start receiver* once the transmitter runs: the counters then start from zero. After the start-up the SER is 5e-5 (about the value of the gain sweep at 76 dB: the level here, 188 counts, is between its 76 and 79 dB).

## 2c. A receiver from the stock GNU Radio OFDM blocks

Question: can the receiver be built from the OFDM blocks that ship with GNU Radio (`ofdm_sync_sc_cfb`, `header_payload_demux`, `ofdm_chanest_vcvc`, `ofdm_frame_equalizer_vcvc` with `ofdm_equalizer_simpledfe`, `ofdm_serializer_vcc`)? **Yes, with three changes**; the flowgraph is `ofdm_b210_frame_rx_stock.grc`, the description and the block table are in `GRC_OFDM.md`. The frame fits the stock chain closely: the S&C symbol has two equal halves of 32 samples, every symbol (S&C, T1, T2 and the 44 data symbols) is 80 samples with its prefix, so the demux takes S&C, T1 and T2 as its 3 header symbols and T2 plays the role of the header symbol.

| test | stock settings | shipped settings |
|---|---|---|
| model recording (300 frames, 24 dB SNR, 9 kHz, 10 ppm), with and without DC | 2.8e-2 (30 of 300 frames clean) | 235 of 240 clean after the first 60, 7.5e-5 |
| B210 recorded by the P501 ADC (`qam16/sim/adc_ofdm850b.npy`, 273 frames) | 0.59 (almost nothing decodes) | 3.6e-3 after the first 60 frames (the Python receiver: 6.8e-4) |
| 3 s of the B210 receiving the P501 | 0.94 | 1939 of 1939 frames clean after the first 60 |
| live, headless, 50 s | | 45,507 frames, no overflow, no symbol error after the first 100, EVM -28.6 dB |

* **Detector without a guard:** the idle slot of the P501 frame (about -15 dB, not pure noise) fires the stock S&C block twice per frame, 80 samples apart (offsets 2354 and 2434 on the recording); the demux takes the first and every frame is cut one symbol early (symbol error rate 0.94 on the recording; your first GUI run, which had the carrier average and the faster equalizer but not the dither: 0.95). Fix: noise at 0.12 of the signal level added to the detector's input only (level-relative: 1939 of 1939 frames clean at 0.1, 0.3 and 3 times the level), threshold 0.8.
* **Carrier estimate:** the stock block's value scatters by 1 to 2 kHz per frame and the equalizer tolerates about 500 Hz (fixed offsets: 9100 Hz 5e-4, 8600 Hz 0.2, 9600 Hz 0.27); averaged over 13 frames. The first 30 to 60 frames are wrong (about 29,000 symbol errors), so the error rate since the start is 4.2e-4 after a minute while the error rate over the last 2000 frames is 0 (the flowgraph shows both).
* **Equalizer:** `alpha` 0.1 gives 3.9e-2 on the recording with the offset fixed at its best value, 0.6 gives 5e-4.
* **The stock equalizer outputs only its decisions** (scaled by 1.056): its constellation is perfect whatever the noise and any EVM computed from it is the scale factor. **A "-25 dB EVM" that I quoted for this chain during the work was exactly that and is wrong.** A soft equalizer block (channel tag from the stock estimator, 4 pilots, EVM against the known payload) gives the real clusters; the stock static equalizer was rejected for this (no phase tracking: 13 degrees of drift per frame, EVM -11 dB against -26 dB). The soft block sees 1 frame in 8: on every frame the B210 overflowed (40 reports in 50 s) and 27,790 symbol errors followed.
* **Compared with the Python receiver:** all frames decoded in real time instead of 1 in 8, 3 Python blocks instead of 7, but worse on the weak recording (3.6e-3 against 6.8e-4), slower to settle (30 to 60 frames) and it needs the dither because the stock detector cannot be given the energy guard.

## 3. Problems found and fixed

1. **A strong frame ending in an empty idle slot fired the detector** (`results_board_air.txt` E and F). The S&C metric |S|^2 / E^2 divides by the energy of the newer half only: when the older half is a strong signal and the newer half is receiver noise the ratio is large (13 dB between them is enough).
   At 915 MHz the B210 signal was too weak for this to show; at 850 MHz (level 174 counts) nothing decoded. Fix in the RTL and in the integer model: a window counts only if the energy of the older half is at most twice that of the newer (`EA <= 2 E`), new test vector `sc_q.hex`, bit-exact again, overlay rebuilt (same timing), tested in the loopback (0 errors) and with the B210. Commit `d2ea5e6`.
2. **The constellation of the live notebook froze** after a rejected frame: the receiver consumes the capture arm at the start of the next detected frame, and a frame that is then rejected leaves `capture_done` at 0 for good. Reproduced on the board with a frame whose T2 symbol is noise (old loop: 0 captures in 3 s, new: 48);
   fix in the driver (`poll_capture()` arms again after 0.25 s). The RTL could re-arm in the reject path instead (needs a rebuild; not done). Commit `ce65fce`.
3. **The GNU Radio receiver showed empty tabs on the B210**: the B210 leaves its DC (LO leakage) and almost no noise in the idle slot, a constant looks periodic to the S&C metric, and M reached 1 one symbol before the real S&C symbol (two spikes per frame in tab 2); the frames were cut wrongly and all failed the T1/T2 check.
   Fix: the DC is estimated by a slow low-pass and subtracted, and M = |S|^2 / (Ea Eb + guard) with a guard of (0.1 x 32 x the average power)^2. In a recording with a DC offset and 60 dB SNR: 867 frames decoded with the DC removal alone, 3535 with the guard. Commit `3758884`. The FPGA has the same weakness in principle (a constant fills a window with M = 1): its guard is the absolute `EMIN` and the `EA <= 2 E` test;
   a DC of the ADC larger than the signal in the idle slot would still fire it. The relative energy guard would be the clean fix there too.
4. **The stock S&C block fired in the idle slot** (section 2c): the same weakness as 3 in a block that cannot be changed; the fix is a dither on its input. Your GUI run without the dither gave a symbol error rate of 0.95, the same as my headless run on the B210 (0.937), so it could be reproduced offline on a 3 s recording (`raw_live`, not in the repository).

## 4. Open items (what I would do next, in this order)

1. **Relative energy guard in `rtl/ofdm_detect.v`** (an average of the window energy, a comparison, no divider; the model and `sc_q`-like vectors with DC; one overlay rebuild of 11 minutes) and the capture re-arm in the reject path, in the same rebuild.
2. **The STS variant** (128 samples, period 16, 48 products) as the second overlay `p501_ofdm_rx_sts`, the same blocks with another delay; then the comparison of the two synchronisers on the air, as planned (`PLAN_OFDM.md` section 12).
3. **The tutorial chapter** (`TUTORIAL_OFDM.md`, like `TUTORIAL_QAM16.md`): the frame, the S&C metric (the figures `img/ofdm_fig_*.png` exist), the GNU Radio receiver as the lab, the FPGA receiver as the reference, the results above.
4. **FPGA OFDM transmitter** (an IFFT and a cyclic prefix instead of the DMA buffer), then the **common soft-output interface** for the FEC stage (signed 8-bit soft values per coded bit and a frame flag): the equaliser already has the per-subcarrier weights; the soft values are the data values scaled by the noise estimate.
5. **A wired lab setup**: the TX1 to RX1 cable with an attenuator removes the antenna dependence (the level changed by 4 dB between sessions with the antennas) and makes the SNR a number that can be set.

## 5. Not verified

* The B210 as a receiver was run by you, not by me: the six tabs of `ofdm_b210_frame_rx.grc` with the P501 transmitting are in `img/ofdm_real_grc_rx_*.png` and read in `TUTORIAL_OFDM.md` section C.5 (one spike of M per frame, accepted = 1, carrier -8447 Hz, 25,212 frames decoded, SER 1.4e-3 since the start); the SNR of that session was not measured.
* The stock-block receiver: my numbers are from recordings and from headless runs on the B210 (50 and 60 s, Qt off screen); the GUI run was yours and I did not record the values on the screen (you reported a reading of 4.5e-4, most likely the value since the start, and "no O in the terminal"). Its EVM (-28.6 dB) is not comparable with the -17 dB estimated from the screenshots of the other receiver (other day, other antenna position). The behaviour at other RX gains than 45 was tested only on rescaled recordings (the dither follows the level), not on the B210. The average of the carrier offset assumes stable oscillators; a drifting offset was not tested.
* The gain sweep is one antenna position and 15 restarts; the earlier bad states did not reappear, so their cause is still not known.
* The SER of 6e-5 at 76 dB and 3e-3 at 72 dB is the SNR floor of this antenna position; a cable with a step attenuator would give a real SER against SNR curve (the AWGN model predicts the P501 to P501 curve above 19 dB; the B210 curve was not compared).
