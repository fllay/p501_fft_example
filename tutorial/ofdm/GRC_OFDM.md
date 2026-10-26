# OFDM in GNU Radio Companion: transmitter and receiver, block by block

Two flowgraphs for the B210 (run them from this folder, `tutorial/ofdm`, after `source ../../tools/gnuradio_env.sh`):

| file | what it does |
|---|---|
| `ofdm_b210_frame_tx.grc` | the B210 transmits the OFDM frames (the same frame as the P501 receiver `p501_ofdm_rx_sc` expects, 850 MHz, 3.84 MS/s) |
| `ofdm_b210_frame_rx.grc` | the B210 receives and decodes them with **separate blocks**, one plot tab per stage; for teaching |
| `ofdm_b210_frame_rx_stock.grc` | the same receiver built from the **stock gr-digital OFDM blocks** (Schmidl & Cox, header/payload demux, channel estimator, frame equalizer, serializer); see *The same receiver with the stock OFDM blocks* below |
| `ofdm_b210_frame_tx_stock.grc` | the transmitter built from the **stock gr-digital OFDM blocks** (carrier allocator, IFFT, cyclic prefixer) and tagged-stream blocks; the same frame, sample for sample, as `ofdm_b210_frame_tx.grc`; see *The transmitter with the stock OFDM blocks* below |
| `ofdm_b210_frame_tx_sts_stock.grc` | the transmitter of the **128-sample STS frame** (overlay `p501_ofdm_rx_sts`): the preamble from a vector source, the 44 data symbols from the stock blocks; see *The STS frame in GNU Radio* below |
| `ofdm_b210_frame_rx_sts_stock.grc` | the receiver of the STS frame: stock blocks and **one synchroniser block of its own** (`sts_sync.py`), because the stock Schmidl-and-Cox block cannot find a preamble that repeats every 16 samples |

```bash
gnuradio-companion ofdm_b210_frame_rx.grc
```

The P501 can be the transmitter (notebook `notebook/P501_OFDM_Live.ipynb`, *P501 transmits* = OFDM frame, *Level* 500, *TX atten* 20 to 30 dB, antennas a few centimetres apart, **LO 850 MHz**) or the receiver; the B210 is the other end.
Without hardware: `python3 make_ofdm_capture.py` writes `ofdm_b210_capture.c64` (60 frames from the model with a 9 kHz carrier offset and 24 dB SNR; `python3 make_ofdm_capture.py ofdm_b210_capture.c64 35 9000 0.014` adds a DC offset like the B210's); in the receiver enable *File Source 0* and *Throttle 0*, disable the *UHD: USRP Source*.

The transmitter flowgraph and the P501 notebook receiving it (the live run of `REPORT_OFDM.md` section 2b):

![the transmitter in GNU Radio Companion](../img/ofdm_real_grc_tx.png)

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

## A real run

The six tabs on the B210 (the P501 transmitting through TX1, antennas a few centimetres apart, default controls), with a reading of each, are in [`TUTORIAL_OFDM.md`](../TUTORIAL_OFDM.md) section C.5: one spike of M per frame, accepted = 1, a carrier offset of -8447 Hz (the sign is opposite to the P501-receiving tests), the channel flat with a linear phase, 16 clusters and 25,212 frames decoded with a symbol error rate of 1.4e-3 since the start.

![tab 2 of the receiver on the B210](../img/ofdm_real_grc_rx_2.png)

![tab 6 of the receiver on the B210](../img/ofdm_real_grc_rx_6.png)

## What differs from the FPGA receiver

* **Only 1 frame in N is decoded** (default 8: 125 frames per second, 132 thousand symbols per second). The transmitter repeats the same frame 1000 times per second and the Python blocks cannot decode all of them in real time on an ordinary PC;
  the FPGA decodes every frame (2003 per 2 s). With *N = 1* run the flowgraph from a recording and not from the B210 (an overflow shows as *O* in the terminal).
* **M is normalised by Ea Eb** (the energies of the two 32-sample halves). The FPGA divides by Eb^2 only and has the guard `EA <= 2 E` instead (`rtl/ofdm_detect.v`, commit `d2ea5e6`): a strong frame that ends in noise would fire a detector with Eb^2 alone.
* Floating point instead of the integer model; the channel is estimated from T1 and T2 only (the S&C symbol is not used), and the noise estimate and the weights `W = conj(H) R / |H|^2` of the FPGA are replaced by a plain division `Y / H`.
* The frame start is taken at the centre of the plateau, as in the FPGA, and 6 samples early (`back`).

## The same receiver with the stock OFDM blocks

`ofdm_b210_frame_rx_stock.grc` decodes the same frame with the OFDM blocks that ship with GNU Radio (`gr-digital`, the blocks of the stock `rx_ofdm.grc` example) instead of my seven Python blocks. It is a second implementation to compare with, and it decodes **every** frame (1000 per second) in real time because the blocks are C++.

```bash
gnuradio-companion ofdm_b210_frame_rx_stock.grc
```

| stage | stock block | what it does here |
|---|---|---|
| frame detection and fine carrier | **Schmidl & Cox synchroniser** (`ofdm_sync_sc_cfb`, *even* carriers) | output 0: the carrier offset (read at one sample of the metric's plateau, held until the next frame); output 1: a pulse at the start of the first symbol after the S&C symbol |
| cut the frame | **Header/Payload Demux** (header 3 symbols = S&C, T1, T2; 64 values per symbol, the cyclic prefix removed) | waits for the message `header_data` that says how many data symbols follow |
| FFT | *FFT* with shift (twice: header and payload) | the bin k + 32 holds subcarrier k |
| channel | **OFDM Channel Estimation** (`ofdm_chanest_vcvc`, sync words = our S&C and T1 spectra) | H[k] = received / known, as a tag on its output |
| equalizer | **OFDM Frame Equalizer** with `ofdm_equalizer_simpledfe` (our 4 pilots and their PRBS-7 polarity, `eq_alpha` 0.6) | divides by the taps, corrects phase and slope with the pilots, **updates the taps from its own decisions** |
| data | **OFDM Serializer**, **Constellation Decoder** (16-QAM with our Gray code) | 24 values per symbol, 44 symbols per frame, one byte (0 to 15) per symbol |

The six tabs follow the other receiver (received signal; frame detection with the stock block's pulses; carrier offset; FFT; channel; equalizer and decisions). The controls on top: **RX gain**, **S&C threshold** (0.8), **carrier offset averaging (frames)** (13) and **detector dither** (0.12).

Three Python blocks are still needed; none is a receiver step the stock chain could do for this frame:

* **Header stand-in.** The stock chain reads the packet length from a header symbol; this frame has none (always 44 data symbols). The block sends the message `header_data` (`frame_length` = 44, and the tags of the channel estimator that the equalizer needs) for every frame, and outputs the channel estimate for tab 5.
* **Error counter** (the block of the other flowgraph with a fourth output: the error rate over the **last 2000 frames**, "SER now"; the first number counts from the start and includes the start-up).
* **Soft equalizer**, for tab 6 only (see *Why a soft branch* below). It sees 1 frame in 8 (`soft_n`).

### What the stock chain needed to work on the B210 (three changes, each found on a recording)

With its stock settings the chain decoded **nothing** on the P501 to B210 link (symbol error rate 0.94 live, reproduced offline on a 3 s recording of the B210). Three things were wrong, in this order:

1. **The stock S&C block has no energy guard, so the idle slot fires it.** The idle slot of the P501 frame (80 samples at about -15 dB of the signal, with a leakage that is not noise) is, after DC removal, still periodic enough for the block: it fires **twice per frame, 80 samples apart** (offsets 2354 and 2434 in the recording), the demux takes the first, and every frame is cut one symbol early.
   The FPGA and the other receiver prevent this with the guard of `A.5` (3); the stock block is closed. The fix is **noise added to the detector's input only** (the data path does not get it) at 0.12 of the signal level, measured by a one-pole average of |x|: the noise destroys the periodicity of the idle slot, the S&C symbol is about 15 dB stronger and keeps M near 1 (threshold 0.8 instead of 0.9 leaves room). On the recording: 1939 of 1939 frames without a symbol error after the first 60, and the same at 0.1, 0.3 and 3 times the signal level for dither 0.08, 0.12 and 0.2 (a fixed noise level would have broken when the RX gain slider moves).
2. **The carrier offset of the stock block scatters by 1 to 2 kHz from frame to frame** (it is read at whichever sample of the plateau the peak detector picks), and this equalizer tolerates only about **+-500 Hz** (fixed offsets on a recording of the B210: 9100 Hz gave a symbol error rate of 5e-4, 8600 Hz 0.2, 9600 Hz 0.27, 8000 and 10200 Hz 0.9). The oscillators of the two radios are stable, so the offset is **averaged over about 13 frames** (a one-pole low-pass on the output of the block, tab 3 shows the scattered value and the average). The price: the first 30 to 60 frames after the start are wrong while the average settles (about 29,000 symbol errors on the B210, which is why "SER since the start" reads 4e-4 after a minute and "SER now" reads 0).
3. **The equalizer is too slow at its default.** `eq_alpha` 0.1 follows the phase drift of this link badly: on a recording of the B210 with the offset fixed at its best value, 0.1 gave 3.9e-2 and 0.6 gave 5e-4. 0.6 is the shipped value (0.8 and 1 were worse; it is read when the flowgraph starts).

### Why a soft branch

The stock equalizer's decision-directed loop **outputs the decided constellation point** (scaled by 1.056, the outer points at +-1), not the received value: against its own scale the error of its output is -155 dB, that is zero. Its constellation is **always 16 perfect dots**, whatever the noise; a frame with symbol errors looks the same as a clean one, and any EVM computed from its output is just the scale factor (an early "-25 dB" figure of mine was exactly that and is wrong).
The error counters are the only quality measure of the stock path, so tab 6 has a **soft equalizer** next to it: the same FFT output divided by the channel estimate (the tag of the stock channel estimator), the 4 pilots giving the slope and the common gain (as in the other receiver, smoothing over 5 symbols), the received values kept. It also measures the **EVM against the PRBS-15 payload that the transmitter sends**, a running average over about 30 frames. Left: the soft clusters and the decided points, right: the five numbers (SER since the start, errors, frames decoded, SER now, EVM).
The stock static equalizer (`ofdm_equalizer_static`) was tried for this and rejected: it does not track the phase, the common phase drifts by 13 degrees over the 44 symbols and the EVM reads -11 dB when it is -26 dB. The soft block sees 1 frame in 8: on every frame it made the B210 overflow (40 `O` in 50 s, 27,790 symbol errors after the start), a Python block does not keep up with 1000 frames per second.

### Results (the P501 transmitting through TX1 at 850 MHz, the B210 receiving, RX gain 45, antennas a few centimetres apart)

| test | stock settings | shipped settings |
|---|---|---|
| model recording, 300 frames, 24 dB SNR, 9 kHz, 10 ppm, with and without DC | symbol error rate 2.8e-2 (30 of 300 frames clean) | 235 of 240 frames clean after the first 60, 7.5e-5 |
| B210 recorded by the P501 ADC (`qam16/sim/adc_ofdm850b.npy`, 273 frames) | almost nothing decodes (0.59) | 3.6e-3 after the first 60 frames, 88 of 212 clean (the other receiver: 6.8e-4 on this recording: **worse here**) |
| 3 s of the B210 receiving the P501 (2000 frames) | 0.94 | 1939 of 1939 frames clean after the first 60 |
| live, headless, 50 s, soft branch on 1 frame in 8 | | 45,507 frames, no overflow, **no symbol error after the first 100 frames**, EVM -28.6 dB (-28.9 to -28.1 over the run) |
| live, headless, 60 s, before the soft branch was added | | 65,977 frames, no error after the first 100; SER since the start 4.2e-4 (29,100 errors, all in the start-up) |

You ran the flowgraph in the GNU Radio window: your first run with the stock settings gave a symbol error rate of 0.95 (what led to the dither), and with the shipped settings and the soft branch tab 6 shows real clusters and an EVM value (you confirmed it; I did not record the numbers shown there). The EVM of my headless session (-28.6 dB) is **not comparable** with the -17 dB that I estimated from the screenshots of the other receiver: other day, other antenna position, and the EVM here is measured against the known payload.

### Comparison with the other receiver

| | `ofdm_b210_frame_rx.grc` | `ofdm_b210_frame_rx_stock.grc` |
|---|---|---|
| receiver steps in Python | 7 (detector, 2 carrier corrections, estimator, equalizer, slicer, counter) | 3 (header stand-in, soft equalizer for the plots, counter), none of them a receiver step the stock chain could do |
| frames decoded in real time | 1 in 8 (default) | all |
| idle slot, DC | energy guard in M, DC removal | DC removal and the dither (the stock block cannot be changed) |
| carrier | coarse from S&C, fine from T1/T2 of every frame | the stock block's offset, **averaged over 13 frames**, the equalizer's pilots do the rest |
| equalizer | one tap, pilots; **soft** output | decision directed; **decisions only** |
| weak recording (`adc_ofdm850b`) | 6.8e-4 | 3.6e-3 |
| first frames after the start | usable at once | wrong for 30 to 60 frames |

## The transmitter with the stock OFDM blocks

`ofdm_b210_frame_tx_stock.grc` builds the frame of the P501 receiver from the transmit blocks that ship with GNU Radio, with **no Python block at all**, and the B210 transmits it at 850 MHz.

```bash
gnuradio-companion ofdm_b210_frame_tx_stock.grc
```

| stage | stock block | what it does here |
|---|---|---|
| payload | *Vector Source* (1056 numbers of 4 bits, repeated), *Stream to Tagged Stream* (1056) | the 44 x 24 symbols of one frame (the PRBS-15 payload of the other transmitter and of the error counters, restarted in every frame); the tag `packet_len` marks the frame |
| mapping | *Chunks to Symbols* (16 points) | number 0 .. 15 to 16-QAM with the Gray code of the receivers |
| subcarriers | **OFDM Carrier Allocator** (sync words S&C, T1, T2; 24 data carriers; 4 pilots with the PRBS-7 polarity) | one vector of 64 per OFDM symbol, 47 per frame: the three sync words first, then the 44 data symbols |
| time signal | *FFT* (inverse, shift), **OFDM Cyclic Prefixer** (prefix 16) | 80 samples per symbol, 3760 per frame |
| idle slot | *Stream to Tagged Stream* on a zero source (80), *Tagged Stream Mux* | frame (3760) + 80 zeros = 3840 samples = 1 ms |
| level | *Multiply Const* (1/8 and the amplitude, times the ON switch), *Tag Gate*, UHD sink | the stock IFFT has no 1/N: its output is 8 times the frame of the model |

The controls are those of the other transmitter: **Transmit OFF/ON** (OFF at start), **B210 TX gain** (79 dB), **TX digital amplitude** (rms 0.25). Four tabs: the 16-QAM symbols, the mean |X[k]| of the 47 OFDM symbols before the IFFT (the 28 used subcarriers), the frame in time (the gap is the idle slot) and the spectrum (1.7 MHz wide, a notch at 0 Hz where no subcarrier is used).

**Check against the other transmitter** (offline, the UHD sink replaced by a file): 12 consecutive frames of the output differ from the model frame (`ofdm_frame.npy`, the frame of `ofdm_b210_frame_tx.grc`) by at most 3e-7, the rms of the active part is 0.2500, the peak 0.837 and the idle slot exactly zero; in a longer run all 3000 frames out of 3000 are identical to the reference. The same frame means that every receiver of this chapter decodes it.

Two things that cost me time, and that the block help does not say:

* **The Cyclic Prefixer parameter is the prefix only** (16). The block adds the FFT length itself; with `fft_len + cp_len` the symbols have 144 samples and the output looks like noise.
* **Its output buffer must hold a whole frame.** The prefixer and the mux need a *minimum output buffer* of 32768 items (8192 was not enough): without it the prefixer stops with "Buffer too small for min_noutput_items".

**On the air** (the P501 receiving with the notebook, B210 at 79 dB, rms 0.25, RX gain 70; I did not run this, the screenshots are yours):

| antenna position | level | SNR | EVM | frames | error rate |
|---|---|---|---|---|---|
| a few centimetres | 237 counts | 25.5 dB | -19.8 dB (last frame), -21.6 dB (picture) | 156,434 at 1001 per second, 9,432 bad frames (6 %) | 1.0e-3 since the start and in the last 2 s |
| closer | 394 counts | 28.2 dB | -25.2 dB, -24.0 dB | 476,050 at 1000 per second; between the two screenshots 319,616 frames with 154 more bad frames and 2 more rejected | 0 in the last 2 s, the error strip at its floor |

At the closer position the stock transmitter is as clean as the other one at 82 dB in the gain sweep (`REPORT_OFDM.md` 2). At the first position the error rate is 1e-3 with an EVM of -20 dB and 6 % bad frames; the earlier run with `ofdm_b210_frame_tx.grc` (report 2b) had 5e-5 at an SNR of 25 dB, **but on another day and at another position, so the two are not a like-for-like comparison**. I looked for a fault of the stock chain and did not find one: no `U` (underflow) in its terminal, the offline output equals the reference in every one of 3000 frames, and the chain used 2.4 s of CPU for 3 s of signal. A run of the old transmitter at the first position, in the same session, was not made.

## The STS frame in GNU Radio

The overlay `p501_ofdm_rx_sts` (the same RTL as the Schmidl-and-Cox overlay with the parameter `STS = 1`, `PLAN_OFDM.md` sections 4b and 14) receives a frame with the **128-sample short training field**: `STS (128) | LTS (32 prefix, T1 64, T2 64) | 44 data symbols of 80 | 32 idle` = 3840 samples.
The STS is a 64-sample IFFT of 6 QPSK subcarriers (k = +-4, +-8, +-12) sent twice, so it repeats every 16 samples; the LTS is the training symbol twice with a prefix of 32 samples. Two flowgraphs and a notebook (`notebook/P501_OFDM_STS_Live.ipynb`) match it. **I made them without the hardware, so the numbers below are from the model and from offline runs; you then ran both flowgraphs and the notebook with the B210 and the P501 and found that they work (the readings of that run were not recorded).**

### Transmitter: `ofdm_b210_frame_tx_sts_stock.grc`

The data part is the chain of `ofdm_b210_frame_tx_stock.grc` unchanged (vector source of 1056 numbers, chunks to symbols, OFDM Carrier Allocator without sync words, inverse FFT, OFDM Cyclic Prefixer): 44 symbols of 80 samples. The preamble is **not** an OFDM symbol with the usual 16-sample prefix, so it comes from a *Vector Source* of its own
(288 samples: a variable `preamble_samples` in the units of the stock IFFT, 8 x the model), and a *Tagged Stream Mux* with **three** inputs joins `preamble (288) | data (3520) | idle (32)` = 3840 samples.
**Check** (offline, the UHD sink replaced by a file): 12 frames differ from the model frame `ofdm_frame_sts.npy` by at most 2.5e-7, the rms of the active part is 0.2500 (the 3808 samples before the idle slot), the peak 0.837 and the idle slot exactly zero. The controls are those of the other transmitters;
the default **B210 gain is 60 dB** (the amplifier after the B210 of our lab: 65 dB gave 82 counts at the P501 with RX gain index 50; without an amplifier 79 dB is the value of the other transmitters): raise it step by step, the radiated power is yours to check.

### Receiver: `ofdm_b210_frame_rx_sts_stock.grc`

| stage | block | what it does |
|---|---|---|
| input | UHD source, DC removal | as in the other receivers |
| metric | *Delay 16*, *Conjugate*, *Multiply*, *Moving Average 48* (S), the energies, the guard, *Divide* (the chain of `ofdm_b210_frame_rx.grc`, retuned from lag 32 / 32 products to **lag 16 / 48 products**) | M = |S|^2 / (Ea Eb + guard): a plateau of 65 samples near 1 inside the STS; the guard (0.1 of the long-term power, squared) keeps the idle slot of the P501 frame below the threshold, so **no dither is needed** (the stock Schmidl-and-Cox block has no guard) |
| synchroniser | **`sts_sync`** (Python, `tutorial/ofdm/sts_sync.py`) | takes the plateau of M (the windows above 24/32 of the maximum, as the FPGA does), the start of the STS from it, the coarse carrier from the angle of S (unambiguous to +-120 kHz) and the fine carrier from the two training symbols (64 samples apart, they must repeat or the frame is dropped); outputs the carrier offset and the trigger in the form of the stock block (`ofdm_sync_sc_cfb`) |
| frame | *Delay 384*, *Frequency Modulator* + *Multiply* (the carrier corrector), **Header/Payload Demux** (header 2 symbols, guard 16) | the trigger comes 122 samples after the start of the STS: the demux takes the two header windows at s0 + 138 and s0 + 218 and the 44 data windows at s0 + 298 + 80 l, the windows of the FPGA receiver (the data windows start 6 samples inside the prefix) |
| channel | *FFT*, **OFDM Channel Estimation** (one training symbol), the header stand-in | H[k] from the window at s0 + 138, which is a circular shift of the training symbol: the sync word is `TRAIN[k] (-j)^k`, the symbol with the phase slope of the 16 samples between this window and the one 6 samples before T1, so that H has the same slope as the data windows |
| data | *FFT*, **OFDM Frame Equalizer** (decision directed, `alpha` 0.6), **Serializer**, **Constellation Decoder**, the error counter, the soft equalizer | as in `ofdm_b210_frame_rx_stock.grc` (the stock equalizer outputs only its decisions: the soft block gives the clusters and the EVM) |

**What is different from the stock receiver of the Schmidl-and-Cox frame, and why:** no dither on the detector (the guard of the metric does that job) and no averaging of the carrier offset (the synchroniser measures the carrier of every frame with the two training symbols, error 100 Hz rms in the model; the stock block's offset scattered by 1 to 2 kHz).
The delay is longer (384 samples against 80) because the carrier is known only after the second training symbol, 282 samples after the start of the STS.

**Offline results** (the model's frames through a channel with 10 ppm and a delay of 3.4 samples; the generated flowgraph on a recording at real time, Qt off screen): 24 dB SNR and +9 kHz: 8,338 frames in 15 s, all found, none dropped, symbol error rate 2.2e-4, EVM -19.4 dB (the S&C stock receiver gives the same at that SNR). The carrier estimate has an error of 100 to 120 rms Hz (mean below 45 Hz) at 9 kHz and at 50 kHz.
In a Python flowgraph of the same blocks at 26 dB SNR: **no symbol error in 299 frames at 0, +9, +30 and -30 kHz**; at 50 kHz a symbol error rate of 5.6e-3 (the EVM is only 0.7 dB worse; 50 kHz is far beyond the 9 kHz of the P501 and the B210); with a DC offset of 20 % of the rms the first 20 frames (the DC filter settling) have 975 symbol errors, the remaining 279 the same 70 as without the DC.
**Tested by you on the B210, readings not recorded:** both flowgraphs and the notebook work. My own checks of the transmitter were against the model frame, sample by sample (not against the P501 receiving it); the receiver's numbers above are from model recordings.

### Notebook: `notebook/P501_OFDM_STS_Live.ipynb`

The notebook of `P501_OFDM_Live.ipynb` for the STS overlay (the overlay `p501_ofdm_rx_sts.bit`, the frame `ofdm_frame_sts.npy`, an assertion that the overlay really is the STS one, and a last cell **RX gain sweep** that steps the RX gain index down while a transmitter is on and prints the error rate, the bad frames and the ADC level).
Copy `p501_ofdm_rx_sts.bit`, its `.hwh` (after `tools/fix_hwh.py`), `ofdm_frame_sts.npy`, `p501_ofdm_rx.py` and the notebook to `/home/xilinx/jupyter_notebooks/p501_ofdm/`. **Executed headless on the board: all 22 checks pass** (no transmitter: no false alarm; digital loopback at three levels: every frame found, 0 errors in 2.1 M symbols, EVM -40 to -45 dB, nothing late; capture RAM and channel estimate; live pictures; the controls).
A recording for the receiver without hardware: `python3 make_ofdm_capture.py ofdm_b210_capture_sts.c64 24 9000 0 sts` (the File Source and the Throttle are disabled in the flowgraph: enable them and disable the B210 as in the other receivers).

## Tests

* The seven blocks and the stock blocks in a Python flowgraph on the B210 recording `sim/adc_ofdm850b.npy` (273 frames, 850 MHz, B210 gain 79 dB, received by the P501 ADC): 269 frames decoded, symbol error rate 6.8e-4, EVM -17.8 dB,
  carrier +9050 Hz (the integer model of the FPGA gave 9.5e-4 and -16 to -19 dB on the same recording).
* The generated flowgraph (`grcc`) with the File Source on the synthetic recording of `make_ofdm_capture.py` (24 dB, 9 kHz), Qt offscreen, 30 s: 3821 frames decoded in real time, SER 3.9e-5 (the errors are at the seams of the replay loop).
* Recordings with a DC offset of 0.02 (0.2 of the rms): at 35 dB SNR without the DC removal 38 frames in 20 s are decoded (the idle slot fires the detector, as in the first B210 test of the flowgraph), with it 3295; at 60 dB SNR (the B210 and the P501 are this clean) the DC removal alone gives 867 frames, with the energy guard 3535
  (the replay is faster than real time: about 170 frames per second; about 1000 symbol errors in all are the first frames, while the DC estimate settles).
* On the B210: run by you with the P501 as the transmitter (screenshots in *A real run* above); not run by me.
