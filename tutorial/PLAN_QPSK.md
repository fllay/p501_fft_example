# Plan: tutorial 4 - a QPSK link over the P501

Status: **plan only**, nothing of this is built yet. Same method as tutorials 1-3: first in software with a measurable pass/fail, then one block at a time into the FPGA, each step checked
against the software version.

## Goal

Send bits as QPSK from TX1 to RX1 and get them back with a measured bit error rate, then move the modem from Python into the FPGA.

Numbers to start with: 3.84 MSPS, **4 samples per symbol** -> 960 ksym/s -> **1.92 Mbit/s** raw; root-raised-cosine (RRC) pulse, roll-off 0.35, span 11 symbols; occupied bandwidth about 1.3 MHz, inside the 4 MHz RF bandwidth of the bring-up.

## What has to be synchronised (and how GNU Radio does it)

A receiver gets a stream of complex samples with unknown *when* (time), unknown *phase* and (with two radios) unknown *frequency*. A typical GNU Radio QPSK receiver chain, with what each block recovers:

| block (GNU Radio) | recovers | how |
|---|---|---|
| AGC | amplitude | a gain that tracks the signal power: the later loops need a constant level |
| FLL band-edge | coarse carrier **frequency** offset | filters at both band edges of the RRC spectrum; a loop drives the difference of their powers to zero. Only needed when TX and RX clocks differ (two radios) |
| **Polyphase clock sync** | **symbol timing**: which sample is the best one, and the slow drift | a bank of e.g. 32 matched (RRC) filters, each with a different fractional-sample delay, plus a bank of their derivatives. The *derivative* of the matched-filter output is the timing error; a loop filter steers which sub-filter is used, and slips a whole sample when it wraps. Output: **one sample per symbol** |
| equaliser (CMA / LMS) | the channel (multipath, filter ripple) | adaptive FIR on the symbol-rate samples (optional here) |
| **Costas loop** (order 4) | carrier **phase** and the fine frequency | a numerically controlled oscillator (NCO) de-rotates the symbols; the phase error is the angle between each symbol and its nearest QPSK point, a 2nd-order loop filter drives it to zero. Order 4 = QPSK: it cannot tell the four rotations by 90° apart |
| differential decoding, or a known word | the **4-fold phase ambiguity** left by the Costas loop | encode the data as phase *changes*, or use the preamble to pick the rotation |
| correlate access code | **frame start** | correlation of the bit stream (or of the samples) with a known preamble |

The "symbol sync" block of newer GNU Radio versions does the timing step with a choice of timing error detectors (Gardner, Mueller-Müller, maximum likelihood) and an interpolating resampler
instead of the polyphase bank: same job.

### What this platform needs of that

* **One chip, one clock.** TX and RX of the AD9361 share the reference, so the sample clocks do not drift against each other and, with the same LO, there is **no carrier frequency offset**: no FLL, and the symbol timing is a *constant* fractional delay. The first link can therefore use a preamble to find frame start, timing and phase **once per packet**, with no loops at all.
* **The loops come in when the problem becomes real.** We can create a real frequency offset on purpose with two LO frequencies (`set_tx_lo_freq` a few kHz away from `set_rx_lo_freq`), and a timing drift by resampling the transmit waveform by a few ppm. Then the Costas loop and the timing loop have something to do, and we can show them working.
* **Latency is not a synchronisation problem** once there is a preamble: the receiver does not care how long the chain delays, it finds the packet by correlation. We still measure it (a delay in samples between a transmitted burst and its arrival), because it sets the turnaround time of any acknowledgement protocol.

## Chapters

| # | chapter | what you build | check |
|---|---|---|---|
| 4a | **Software QPSK link, digital loopback** | `qpsk_tx`: bits -> Gray-mapped QPSK -> RRC (NumPy), preamble + guard of zeros; sent with the DAC DMA in the AD9361's digital loopback; `qpsk_rx`: capture, **preamble correlation** (frame start, fractional timing, phase), matched filter, slicer; measures the chain's latency | 0 bit errors in 10^6 bits; constellation and eye diagram; latency in samples |
| 4b | **Over the air, with loops** | the same over antennas; **polyphase clock sync** and **Costas loop** in NumPy (reference implementations); inject an LO offset and a ppm drift to show the loops lock; BER versus TX attenuation (SNR) | BER curve against the theoretical QPSK curve; loops lock with 2 kHz offset |
| 4c | **Transmitter in the FPGA** | AXI-Stream chain: bit FIFO -> QPSK mapper -> RRC interpolating FIR (Xilinx FIR Compiler, x4) -> `dds_out`-style connection to `dac_data_i0/q0`; register block for gain and enable; bits arrive over a DMA | the FPGA waveform equals the NumPy one (sample-exact for the same bits, within rounding); the 4a receiver decodes it |
| 4d | **Receiver in the FPGA** | RX chain: matched FIR -> timing recovery (Gardner or the polyphase bank as a multi-coefficient-set FIR) -> Costas loop (the **DDS Compiler as NCO** from tutorial 2 + a complex multiplier + a small RTL phase detector and loop filter) -> slicer -> bit stream over a DMA; loop gains from registers | the demodulated bits equal the NumPy receiver's bits; BER curve unchanged |
| 4e | **Packets and throughput** (optional) | preamble detector and header/CRC in RTL, back-to-back packets, throughput and latency figures; two boards (needs the FLL) | CRC pass rate, sustained bit rate |

## Why this order

1. **Software first** because the loops are the hard part and need tuning (bandwidths, damping, initial lock): NumPy shows every internal signal. The FPGA versions are then ports of a working algorithm.
2. **Preamble before loops** so that the first chapter has a clear pass/fail (zero errors) and measures the latency.
3. **TX before RX in hardware** because it is feed-forward (no loops, bit-exact check against NumPy), the receiver reuses the DDS and FIR blocks learned on the way.

## Things to decide tonight

* Samples per symbol 4 (simple, 1.92 Mbit/s) or 8 (easier timing recovery, 0.96 Mbit/s)?
* Roll-off 0.35 or 0.25? (bandwidth versus sensitivity to timing error)
* Differential encoding (no phase ambiguity at all, ~2 dB worse) or a known preamble to resolve the 4-fold ambiguity?
* Fixed-point formats in the FPGA: 16-bit samples (as everywhere), loop filter in 24 bits.
* Packet format for 4e: preamble length, header, CRC.

## Risks and what we already know

* **Stale data and pipeline latency** (tutorial 3): a stream through a FIFO needs a flush at the start of a packet, and the first frames after a change are old. In the modem the preamble makes this harmless, but the TX FIFO must start empty and end with zeros (the DAC replays its last samples after a DMA stop).
* **The AD9361's analog state** after a start is random (image rejection 40-60 dB): `settle` stays in the bring-up; QPSK is tolerant of 40 dB image rejection, but not 25 dB.
* **Sample-rate limit of the DMAs**: 1 sample = 4 bytes at 3.84 MSPS = 15 MB/s, trivial; the modem in the FPGA only moves *bits*.
* **Clocking in the FPGA.** In 1R1T `l_clk` = 2 x the sample rate = 7.68 MHz: only 2 clock cycles per sample. The multipliers of a 44-tap RRC at 4 samples per symbol and of the Costas loop need no more than that (a DSP slice can do the multiply-adds in time), but a loop with a long feedback delay (loop filter, NCO, phase detector in series) should be pipelined with care, or the modem can run on a faster PL clock with a small FIFO at the boundary. Decide in 4d with the numbers of 4b.
