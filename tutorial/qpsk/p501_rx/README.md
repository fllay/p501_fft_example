# Chapter 4d: the QPSK receiver in the FPGA (adjustable loops)

Status: **done**: reference receivers (stage 1), RTL bit-exact in simulation (stage 2), integrated into the TX+RX overlay `p501_qpsk_trx` (stage 3), tested over the air against the P501's own FPGA transmitter and against GNU Radio on the B210 (stage 4). The 4e packet layer (preamble, CRC) is not part of this chapter.

## Architecture

One engine in the 100 MHz PS clock domain (the clock of the AXI-Lite registers: no register synchronisers), working once per symbol:

```
ADC samples (l_clk) -> 256-entry dual-clock RAM (write on l_clk, a Gray-coded write counter crosses to the engine clock)
engine, per symbol (about 65 of the 104 clock cycles available at 960 ksym/s):
  44-tap multiply-accumulate on the arm k of 16 (matched filter and derivative filter, I and Q: 4 DSP multipliers in parallel)
  -> symbol-rate AGC -> timing error -> timing loop (rate + position p, in 1/16 sample and 16 fractional bits)
  -> derotation by the Costas NCO (1024-entry sine/cosine table) -> Costas error -> phase/frequency loop
  -> decision -> differential decoder -> bits -> self-synchronising PRBS-15 checker (counters) and a capture RAM of soft symbols
```

Every gain is a register (32-bit): timing `TA`, `TB`, Costas `CA`, `CB`, AGC speed `MU` and reference `REF`, initial gain `G0`, initial frequency `W0`, rate limit `MAXR`;
`regs_from_bw()` in `qpsk_rx_fixed.py` computes them from loop bandwidths with the formulas of GNU Radio's blocks. The loops report what they measured:
the Costas frequency register is the carrier offset, the timing-rate register is the sample-clock offset.

## Stage 1: reference receivers (NumPy)

| file | what |
|---|---|
| `qpsk_rx_model.py` | float reference: polyphase matched/derivative banks, timing loop, Costas loop |
| `qpsk_rx_fixed.py` | integer model with the hardware's widths and shifts: the bit-exact reference for the RTL |

Both decode the recordings of chapters 4b and 4c from a cold start (no frequency hint, loops 2 pi/400), as well as or better than GNU Radio's chain:

| recording | float model | fixed model | GNU Radio (4b/4c) |
|---|---|---|---|
| B210 -> P501, 60 dB (10 dB SNR) | 9.2e-2 | 9.2e-2 | 1.4e-1 |
| B210 -> P501, 70 dB (18 dB) | 9.1e-5 | 7.9e-5 | 6e-5 |
| B210 -> P501, 75 dB (21 dB) | 0 | 0 | 0 |
| FPGA TX -> B210, atten 30 dB | 0 | 0 | 0 |
| FPGA TX -> B210, atten 40 dB | 4.4e-6 | 4.4e-6 | 8.7e-6 |
| FPGA TX -> B210, atten 45 dB | 5.1e-4 | 4.9e-4 | 4.1e-4 |

(about 0.46 to 0.48 million bits each; the Costas loop settles at +-9.5 kHz, the timing loop at the 10 ppm found in chapter 4b.)

Lessons of stage 1: the loop gains scale with the **square of the symbol amplitude**, so the AGC reference matters as much as the bandwidth: with the symbol amplitude at 1.0 the same
bandwidths gave a BER 30 times worse; at 2.0 (`REF` = 16384, as in GNU Radio's constellation) they match the float model.

## Stage 2: the RTL, bit-exact (`rtl/qpsk_rx.v`, `qpsk_rx_rom.v`, `qpsk_rx_trig.v`)

`sim/tb_qpsk_rx.v` feeds 60000 samples of a real capture (the 70 dB recording of chapter 4b) to the RTL in xsim, with `adc_valid` every second `l_clk` cycle and the 100 MHz engine clock, and logs every symbol.
Compared with the integer model `qpsk_rx_fixed.py` over all **14990 symbols**: **0 mismatches** in the decoded bits, the soft symbols (`zi`, `zq`), the Costas frequency, the timing rate, the AGC gain and both loop errors.
The engine needs about 65 of the 104 clock cycles of a symbol; no overruns.

Two simulation pitfalls found on the way (both are bugs the synthesis would have hidden or reported late): a Gray-to-binary decode written as `always @*` stays unknown in simulation until its input changes (use a function in a
continuous assignment); and `ic[7:0]` on a 7-bit register is an out-of-range select.

## Stage 3: integration (overlay `p501_qpsk_trx`)

`steps/step1_rx.tcl` instantiates `qpsk_rx` (module reference) on `axi_ad9361`'s RX1 samples (`l_clk`, `adc_valid_i0`, `adc_data_i0/q0`) and on the PS clock and AXI-Lite bus
(registers at `0x9C470000`, 16 KB; the capture RAM is at +0x1000); `steps/step2_constraints.tcl` and `src/qpsk_rx_cdc.xdc` declare the two clock crossings (Gray write counter, sample RAM) as false paths. Build:

```bash
vivado -mode batch -source create_project.tcl -tclargs FFT=0 QPSK=1 QPSKRX=1 RUN=bit JOBS=8      # -> build/overlay/p501_qpsk_trx.bit/.hwh (about 10 minutes)
python3 tools/fix_hwh.py build/overlay/p501_qpsk_trx.hwh                                         # PYNQ-loadable hwh
```

Timing at 100 MHz with the multiply-accumulate paths unpipelined: **WNS +0.417 ns, WHS +0.011 ns**, no failing setup/hold endpoint (the one pulse-width endpoint of -0.002 ns is the PS Ethernet GMII RX clock, not this design).
The whole TX+RX design uses 14.1 k LUTs (12 %), 20.6 k flip-flops and 6.5 BRAM tiles of the XCZU5EV.

## Stage 4: hardware tests

Python side: `notebook/p501_qpsk_rx.py` (`P501QpskRx`: `configure()`/`set_loops()` compute the gain registers from loop bandwidths, `start()`, `stats()`, `offsets()`, `capture()`).
Board script `p501_qpsk_link.py`, host runner `run_rx_test_4d.py` (the B210 transmits the PRBS-15 with `qpsk_b210_loop.py --pattern prbs15`, the P501 receives and checks it); all numbers below are
read from the FPGA's own counters. A "bit error" is `mismatches / 3` (the self-synchronising checker counts three mismatches per isolated error).

![constellations from the FPGA's capture RAM](../../img/qpsk_rx_fpga_constellation.png)

**P501 FPGA transmitter -> P501 FPGA receiver** (both in the same overlay, 5 s, loops 2 pi/400, no help):

| path | what | result |
|---|---|---|
| AD9361 digital loopback | carrier offset 0 Hz, clock offset 0 ppm | 8 bit errors in the first 30 microseconds (the loops pulling in), then **none in 7.7 million bits** |
| over the air, TX attenuation 30 dB (RX gain index 70) | | 19 bit errors during the pull-in, **none in 9.6 million bits** |
| over the air, 20 dB | | 52 bit errors in the first 1.2 ms, none in 9.6 million bits |
| over the air, 40 dB / 50 dB (first overlay) | too weak (AGC gain 25 / 50) | BER 4.6e-3 / 15 % (not locked) |

**B210 (GNU Radio, PRBS-15) -> P501 FPGA receiver**, TX gain 75 dB, antennas a few centimetres apart, P501 RX gain index 70, 6 s per run (11.5 million bits):

| loops | cold start (no help) |
|---|---|
| 2 pi/400 | locks in 3 of 3 runs: last error after 0.75 / 0.90 / 1.5 ms (55 / 46 / 196 bit errors), then none |
| 2 pi/800 | locks in 3 of 3 runs, last error after 50 ms / 4 ms / 1.0 s (3300 / 370 / 41500 bit errors), then none |
| 2 pi/1600 | **never locks** in 3 of 3 runs: the Costas loop cannot pull in the 9.7 kHz offset (it sits at 0 Hz, or at the offset with BER 2 to 3 %) |
| 2 pi/100 for 30 ms, then 2 pi/1600 (live register write) | locks in 3 of 3 runs (last error after 0.6 / 33 / 48 ms: 192 / 361 / 2026 bit errors), **no error in the following 11.5 million bits** each |

(All rows are from the final overlay, after the rounding fix of lesson 1 below; 2 pi/100 from a cold start was not repeated with it.)

So **acquire wide, track narrow** is what the adjustable registers are for: `rx.configure(timing_bw=2*pi/100, phase_bw=2*pi/100); rx.start(); time.sleep(0.03); rx.set_loops(2*pi/1600, 2*pi/1600)`.
Both loops are then 16 times narrower, which matters at lower signal levels (below). An initial frequency (`init_freq_hz`, register W0) can replace the wide acquisition when the offset is known (from the FFT chain of tutorial 1, say); it was tried only on the first overlay (2 pi/800 with a 9.7 kHz hint: one clean lock, one slow lock, one run that never locked), so we do not claim anything from it.

What the receiver measures (averaged over 2 s from the registers): **carrier offset +9.68 to +9.71 kHz, clock offset +9.9 to +10.8 ppm** (narrow loops; 7 to 9 ppm with 2 pi/400, whose timing jitter is larger): the 10.4 ppm of chapter 4.0 (two-tone measurement)
within its accuracy; in P501-to-P501 operation 0.0 to 0.7 ppm.

**Lower signal levels** (B210 TX gain; acquisition 2 pi/100 for 30 ms, then the tracking bandwidth shown; two runs each, BER over everything including the pull-in):

| B210 TX gain | tracking 2 pi/400 | tracking 2 pi/1600 | GNU Radio (4b, stock loops) |
|---|---|---|---|
| 75 dB | no error after the pull-in | no error after the pull-in | no error after the pull-in |
| 70 dB | 4.5e-4, 2.4e-6 | 1.9e-2, 1.1e-5 | about 6e-5 |
| 65 dB | 6.2e-3, 5.0e-3 | 3.4e-3, 5.8e-4 | not tried |
| 60 dB | not locked (BER 17 to 21 %) | not locked | not decodable (14 %) |

The spread between runs at 70 and 65 dB is large (cycle slips and false locks of the Costas loop at low SNR, each costing many bits; the receiver has no cycle-slip detector or preamble to resynchronise): this
is the point where chapter 4e (preamble, CRC, packets) takes over, not a thing the loop gains can fully fix. The constellation of one capture at 75 dB has 14.5 degrees of angular spread (3.5 degrees for the P501's own transmitter at 20 dB attenuation); the NumPy model, which equals the RTL, gives 12 degrees on the 70 dB recording of chapter 4b, so the FPGA is not worse than its model. GNU Radio's 8 to 10 degrees of chapter 4b came from different captures and its own measure; we did not compare like with like.

## Lessons from the hardware

1. **A floor in a loop integrator is a bias.** `rate += (TB*e) >> 21` in two's complement rounds towards minus infinity: for narrow loops (small `TB*e`) every update is 0 or -1, a drift of -0.5 LSB per symbol,
   which the loop cannot balance and which ran the timing integrator into its limit (+-12500 ppm) within 0.1 s for 2 pi/1600, and even with 2 pi/400 shifted the reported clock offset to 16 ppm instead of 10.4.
   The bit-exact NumPy model showed the same on the recorded data (rate 12499 ppm with the floor, 10.4 ppm with rounding), so the fix is one rounding constant in the RTL and the model (`(TB*e + 2^20) >> 21`).
   Verified again bit-exactly in xsim (`sim/compare_rx.py`: bits, soft symbols, frequency, rate, AGC gain and both loop errors, 0 mismatches over 14990 symbols, with the default and with a narrow `TB`).
   This was invisible with the loop bandwidths of the first simulations and found only when the register gains were swept on the hardware.
2. **Pull-in is a separate problem from tracking** (table above): a Costas loop cannot acquire a 9.7 kHz offset with a bandwidth of 0.4 % of the symbol rate; adjustable gains allow the two phases to use different loops.
3. Start the transmitter first and the receiver 2 s later (as in 4a): the loops must not run on the transmitter's start-up transient (`--tx-delay`).
