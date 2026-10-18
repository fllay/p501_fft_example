# Plan: tutorial 4 - a QPSK link between the P501 and a USRP B210 (GNU Radio)

Status: **plan only**, nothing of this is built yet. Same method as tutorials 1-3: a trusted reference first, then one block at a time into the FPGA, each step checked against the reference.

## Test setup

```
  P501 (PYNQ, FPGA modem)  <---- cable + attenuators ---->  USRP B210 (USB 3) + GNU Radio on the host PC
        TX1 / RX1                                              TX/RX or RX2 / TX2
```

* **GNU Radio is the golden reference on the other end.** The B210 is an AD9361 radio too (70 MHz - 6 GHz), driven by GNU Radio's standard blocks. We do not have to trust our own receiver to test our own transmitter, and the other way round.
* **Two radios, two independent clocks.** This is the real situation, and it changes the synchronisation problem (next section): there *is* a carrier frequency offset and a sample-clock drift, and the receivers need their loops.
* **Host setup (done):** GNU Radio 3.10.12 and UHD 4.8.0 from **radioconda** in `~/radioconda` (use `source tools/gnuradio_env.sh`), the B210 (serial 3275461, "MyB210") on the USB 3 root port `Bus 04`. UHD uses the images of the system UHD in `/usr/local/share/uhd/images`; it reports *Operating over USB 3*, FPGA 16.0, and streams 3.84 MSPS (master clock 61.44 MHz) without overruns. The clock source is the internal TCXO (no GPSDO), so the offset to the P501 will be a real, uncorrected one.
* **Cable, not antennas**, with at least 30-40 dB of attenuators and the lowest TX gain first: check the maximum output of one radio against the maximum input of the other before connecting anything. A cable also keeps the link clean for measuring.
* Common settings: LO e.g. 915 MHz (tested on the P501), sample rate 3.84 MSPS on both (B210: UHD picks the master clock, 61.44 MHz with decimation 16 was measured), 4 samples per symbol, RRC roll-off 0.35.
* Connection to the host for data: first **files** (a capture from the P501 as `complex64`, a bit file for its transmitter), later a **stream** over the P501's Ethernet (15 MB/s for 3.84 MSPS of 16-bit I/Q is small for gigabit; ZeroMQ or UDP).

## What has to be synchronised

A receiver gets complex samples with unknown *when*, unknown *phase* and, between two radios, unknown *frequency* and a slightly different *sample rate*. The standard GNU Radio QPSK receiver chain, with what each block recovers:

| block (GNU Radio) | recovers | how |
|---|---|---|
| AGC | amplitude | a gain that tracks the signal power: the later loops need a constant level |
| **FLL band-edge** | coarse carrier **frequency** offset | filters at both band edges of the RRC spectrum; a loop drives the difference of their powers to zero |
| **Polyphase clock sync** | **symbol timing**: the best sample, and the slow drift | a bank of e.g. 32 matched (RRC) filters, each with a different fractional-sample delay, plus a bank of their derivatives. The *derivative* of the matched-filter output is the timing error; a loop filter steers which sub-filter is used, and slips a whole sample when it wraps. Output: **one sample per symbol** |
| equaliser (CMA / LMS) | the channel (cable, filter ripple) | adaptive FIR on the symbol-rate samples (optional here) |
| **Costas loop** (order 4) | carrier **phase** and the fine frequency | a numerically controlled oscillator (NCO) de-rotates the symbols; the phase error is the angle between each symbol and its nearest QPSK point, a 2nd-order loop filter drives it to zero. Order 4 = QPSK: it cannot tell the four rotations by 90° apart |
| differential decoding, or a known word | the **4-fold phase ambiguity** left by the Costas loop | encode the data as phase *changes*, or use the preamble to pick the rotation |
| correlate access code | **frame start** | correlation of the bit stream with a known preamble |

(GNU Radio also has an all-in-one *Constellation Receiver* and a *Symbol Sync* block with Gardner / Mueller-Müller / maximum-likelihood timing detectors and an interpolating resampler instead of the polyphase bank: same job.)

### What the two-radio link needs of that

* **Carrier frequency offset.** Each radio's LO comes from its own reference, typically a few ppm: at 915 MHz that is a couple of kHz per radio, so up to roughly +-4 kHz between them (0.4 % of the 960 ksym/s symbol rate). The FLL plus Costas loop must pull this in; or a **coarse estimate from a preamble tone with the FFT chain of tutorial 1** can pre-set the NCO. Measuring this offset is the first experiment (chapter 4.0): **done, both directions agree on 10.4 ppm = about 9.5 kHz at 915 MHz** (`tutorial/qpsk/link_up/RESULTS.md`).
* **Sample-clock offset.** A few ppm of 960 ksym/s is a few symbols of slip per second: the symbol-timing loop is not optional, a preamble alone only works for packets short enough that the drift stays well under a sample.
* **Latency is not a synchronisation problem** once there is a preamble, the receiver finds the packet by correlation. We still measure it (round trip P501 -> B210 -> P501) because it sets the turnaround time of any acknowledgement protocol.

## Chapters

| # | chapter | what you build | check |
|---|---|---|---|
| 4.0 | **Link-up and offset measurement** (no new HDL) | tone from GNU Radio (B210) into the P501 and read it with the **FFT chain** (tutorial 1/3); tone from the P501's **DDS** into the B210 and look at it in a GNU Radio FFT sink. Gain settings and levels for both directions | the P501 FFT sees the B210's tone at the expected bin; the **carrier offset in kHz** between the two radios, and its drift over minutes; the B210 sees the DDS tone |
| 4a | **GNU Radio QPSK reference** | a flowgraph with the standard transmitter (bits -> constellation modulator -> RRC) and receiver (AGC, FLL, polyphase clock sync, Costas, differential decode, access-code correlation); first on the **B210 alone** (TX to RX with a cable) | 0 bit errors, constellation and eye diagram; the flowgraphs (`.grc`) go into the repository |
| 4b | **P501 receives GNU Radio's QPSK** | the P501 captures I/Q (ADC DMA) while the B210 transmits; the file goes to GNU Radio / NumPy for **offline** decoding with the same receiver; then the NumPy reference receiver (polyphase sync, Costas) used later as the model for the FPGA | BER of the offline decode; the offsets and drift the loops have to track; BER versus attenuation |
| 4c | **Transmitter in the FPGA** | AXI-Stream chain: bit FIFO -> QPSK mapper -> RRC interpolating FIR (Xilinx FIR Compiler, x4) -> connected to `dac_data_i0/q0` like `dds_out` in tutorial 2; register block for gain and enable; bits arrive over a DMA | **the B210 + GNU Radio standard receiver decodes it** (BER, constellation); and the FPGA samples equal a NumPy-generated waveform for the same bits |
| 4d | **Receiver in the FPGA** | RX chain: matched FIR -> timing recovery (Gardner, or the polyphase bank as a multi-coefficient-set FIR) -> Costas loop (the **DDS Compiler as NCO** from tutorial 2, a complex multiplier, a small RTL phase detector and loop filter) -> slicer -> bits over a DMA; loop gains and initial NCO frequency from registers (the FFT chain can estimate the coarse offset) | the bits from the FPGA equal the NumPy reference receiver's; BER against the GNU Radio transmitter on the B210 |
| 4e | **Both directions, packets** (optional) | preamble detector and header/CRC in RTL, back-to-back packets, a loop P501 -> B210 -> P501 with an acknowledgement, throughput and round-trip latency | CRC pass rate, sustained bit rate, turnaround time |

## Why this order

1. **Chapters 4.0 and 4a need no new FPGA work** and remove the doubts early: do the two radios hear each other, what is the offset, does the standard GNU Radio link work on this B210.
2. **The reference receiver (4b) before the FPGA receiver (4d)**: the loops need tuning (bandwidths, damping, lock-in range) against the real offset and drift measured in 4.0; NumPy shows every internal signal.
3. **TX in the FPGA (4c) before RX (4d)**: it is feed-forward (no loops), and GNU Radio's receiver is an independent, trusted judge of it.

## Things to decide tonight

* Samples per symbol 4 (1.92 Mbit/s) or 8 (easier timing recovery, 0.96 Mbit/s)? Roll-off 0.35 or 0.25?
* Differential encoding (no phase ambiguity at all, ~2 dB worse) or a known preamble to resolve the 4-fold ambiguity?
* Carrier frequency: 915 MHz (tested on the P501) with cables only, or an ISM-band over-the-air test later (power and licensing rules!).
* Does the B210 get a better clock reference (an external 10 MHz / GPSDO) to separate the two radios' offsets, or do we live with the TCXO offsets (more realistic)?
* Fixed-point formats in the FPGA: 16-bit samples (as everywhere), loop filter in 24 bits.
* Packet format for 4e: preamble length, header, CRC.

## Risks and what we already know

* **Levels.** Two AD9361 radios facing each other through a cable can destroy a front end if the TX power is too high: attenuators first, TX gain minimal, then step up (both directions).
* **Stale data and pipeline latency** (tutorial 3): a stream through a FIFO needs a flush at the start of a packet, and the first frames after a change are old. A preamble makes this harmless, but the TX FIFO must start empty and end with zeros (the DAC replays its last samples after a DMA stop).
* **The AD9361's analog state** after a start is random on the P501 (image rejection 40-60 dB): `settle` stays in the bring-up; QPSK tolerates 40 dB image rejection but not 25 dB. The B210 does its own calibration in UHD.
* **USB / host timing on the B210 side.** Overruns and underruns on the host (GNU Radio) look like symbol-timing errors: use a modest rate (3.84 MSPS is easy) and a wired USB 3 port.
* **Sample-rate limit of the DMAs**: 1 sample = 4 bytes at 3.84 MSPS = 15 MB/s, trivial; the modem in the FPGA only moves *bits*.
* **Clocking in the FPGA.** In 1R1T `l_clk` = 2 x the sample rate = 7.68 MHz: only 2 clock cycles per sample. The multipliers of a 44-tap RRC at 4 samples per symbol and of the Costas loop fit, but a loop with a long feedback delay (loop filter, NCO, phase detector in series) should be pipelined with care, or the modem can run on a faster PL clock with a small FIFO at the boundary. Decide in 4d with the numbers of 4b.
