# Tutorial 4: a QPSK modem in the FPGA, tested against GNU Radio

*This file is generated: `tutorial/qpsk/doc/TUTORIAL_QPSK.src.md` is the text, `build_doc.py` pastes the code excerpts from the real source files into it
(`python3 tutorial/qpsk/doc/build_doc.py`), so the code shown here is always the code of the repository. Figures are drawn by `make_diagrams.py`.*

In tutorials 1 to 3 the FPGA did **measurements** (a spectrum) and **generated tones**. Here it does what a real radio modem does: it **transmits data**
as differential QPSK and it **receives** it, including everything that a receiver has to recover on its own (signal level, symbol timing, carrier
frequency and phase). Python only starts and stops it, sets the loop gains, and reads the results. No sample passes through Python or a DMA.

![The two ends of the link](img/qpsk_block_system.png)

| part | content |
|---|---|
| **A** | the concepts: what is sent, what the receiver has to recover, and why the FPGA design looks the way it does; **A.5: functional block diagrams** (what every block does and why it is needed); **A.6: the GNU Radio flowgraph blocks side by side with the Verilog** |
| **B** | the transmitter: block diagram, and every block with its Verilog |
| **C** | the receiver: block diagram, and every block with its Verilog |
| **D** | integration into the block design, the register interface, and the verification method (model, simulation, hardware) |
| **E** | the test code, in detail: the Python drivers on the board, the host scripts, the GNU Radio flowgraphs, the analysis |
| **F** | results, lessons, and how to run everything |

**Parameters of the link** (everything below follows from these):

| quantity | value |
|---|---|
| carrier | 915.0 MHz |
| sample rate | 3.84 MSPS (AD9361 in 1R1T mode; the FPGA clock `l_clk` is 2 x this = 7.68 MHz) |
| modulation | differential QPSK, 2 bits per symbol, Gray-like pre-differential code |
| symbol rate | 960 ksym/s = **1.92 Mbit/s**, 4 samples per symbol |
| pulse shape | root-raised-cosine, roll-off 0.35, span 11 symbols |
| test pattern | PRBS-15 ( x^15 + x^14 + 1 ), period 32767 bits |
| other end | USRP B210 + GNU Radio 3.10 (radioconda), the *trusted reference* |

---

# Part A. The concepts

## A.1 Method: reference first, then one block at a time

The tutorial follows the same method as tutorials 1 to 3, and the order matters more than any single block:

1. **A trusted reference first.** GNU Radio's standard QPSK transmitter and receiver (`digital.generic_mod`, AGC, FLL band-edge, polyphase clock sync, Costas loop) run on the B210. They tell us whether the radios, the antennas and the levels work *before* we write any Verilog (chapter 4a).
2. **A software model of every FPGA block.** NumPy models in *float* (the algorithm), then in *integers with the hardware's widths* (**bit-exact**: every shift, every clip). The integer model is what the Verilog is checked against.
3. **Simulation with the real data.** The RTL runs in `xsim` on 60,000 samples of a real recording; every symbol (soft values, loop states, bits) is compared with the integer model: **0 mismatches**.
4. **Hardware, against the reference.** The FPGA transmitter is decoded by GNU Radio; GNU Radio's transmitter is decoded by the FPGA receiver; the FPGA transmitter is decoded by the FPGA receiver (digital loopback and over the air). Bit errors are counted *inside the FPGA*.

Why the integer model is worth its effort: it is also how a **bug that no simulation shows** was found (see F.3): the model, run on a recording, disagreed with an independent measurement.

## A.2 What is transmitted: bits -> symbols -> samples

```
bits (PRBS-15) --2 bits--> chunk c --pre-diff map--> p --differential encoder--> d --> point (I, Q) = (+-1, +-1) --> RRC pulse shaping --> samples (4 per symbol)
```

**Differential QPSK.** Four phases carry two bits. A coherent receiver recovers the carrier phase with a Costas loop, but the loop has a **4-fold ambiguity**
(it can lock with the constellation rotated by 0, 90, 180 or 270 degrees: the error detector of QPSK looks identical). If the data are encoded as the *change*
of phase between symbols, the receiver does not need to know which of the four it locked to: **the bits come out right whatever the rotation**. The price is that one
symbol error makes two adjacent decisions wrong (about 2 dB). The encoder is a modulo-4 accumulator:

```
d[n] = (d[n-1] + p[n]) mod 4          p = pre-differential map of the two data bits: [0,1,3,2]  (a Gray-like code: 00,01,11,10)
point  d = 0,1,2,3  ->  (+,+)  (-,+)  (-,-)  (+,-)       (GNU Radio constellation_dqpsk)
```

The receiver does the inverse: `dd = (point[n] - point[n-1]) mod 4`, then the map `[0,1,3,2]` again (it is its own inverse).

**Pulse shaping.** A stream of +-1 impulses has an infinite bandwidth; each symbol is replaced by a *root-raised-cosine* (RRC) pulse. The receiver filters with the same RRC
(the **matched filter**): the cascade is a raised cosine, which has *no inter-symbol interference at the symbol instants* and maximum SNR. Roll-off 0.35 means the
occupied bandwidth is 960 kHz x 1.35 = 1.3 MHz. With 4 samples per symbol the filter has 45 taps (11 symbols x 4 + 1).

**A trick for the FPGA transmitter.** The symbols are only **+-1**, so the 45-tap FIR needs **no multiplier**: the output is the sum of 12 coefficients with signs.
Per output sample only 12 of the 45 taps matter (the other 33 meet zero-stuffed positions): the filter is a **polyphase** FIR with 4 phases of 12 taps (`ph` = the position of the sample inside the symbol).
Only the final amplitude scaling uses two multipliers.

## A.3 What the receiver has to recover

Two radios have independent clocks and independent phases: the receiver gets samples with unknown **level**, unknown **instant** (which of the 4 samples per symbol, and a fractional part),
unknown **phase** and, because the two crystals differ by a few ppm, an unknown **frequency** and a slightly different **sample rate**. We measured both (chapters 4.0 and 4b):
**+9.7 kHz carrier offset** (10.4 ppm of 915 MHz) and **10.4 ppm sample-clock offset** (about 10 symbols of slip per second at 960 ksym/s). Nothing can be fixed with a fixed filter or a lookup: the receiver
needs **feedback loops**.

| problem | recovered by | how |
|---|---|---|
| signal level | **AGC** | a gain `g` follows the amplitude of the decisions towards a reference: the loops downstream need a known amplitude |
| symbol instant, and its drift | **timing loop** on a **polyphase matched filter** | the matched filter is computed at 16 fractional delays ("arms") of 1/16 sample; a *derivative* filter gives the slope; their product tells *early or late*; a 2nd-order loop moves the sampling position |
| carrier frequency and phase | **Costas loop** (order 4) | the symbols are rotated back by an NCO; a decision-directed phase detector measures the remaining angle; a 2nd-order loop corrects phase and frequency |
| 4-fold rotation ambiguity | **differential decoding** | see A.2 |

**Timing recovery with a polyphase matched filter** (the idea of GNU Radio's `pfb_clock_sync_ccf`, rebuilt for the FPGA). Let `x[n]` be the samples. We want
`y(t) = (x * h)(t)` at the instants `t = kT + tau`, where `tau` is unknown. A bank of NF = 16 filters `h_k[i] = h(i + k/16)` gives `y` at the sample *plus* k/16 of a sample.
The *derivative* bank `h'_k` gives `y'(t)`. At the right instant `y` has its maximum, so `y' = 0`; the **timing error** is `e = Re{ y * conj(y') }`: negative or positive depending on early or late.
The loop filter turns `e` into a position: `rate += beta*e; position += nominal + rate + alpha*e`. The integral part `rate` converges to the **sample-clock offset** (a register you can read), and the position
index splits into a sample index and an arm: `t = position >> 20`, `arm = (position >> 16) & 15`.

**Costas loop for QPSK.** After the matched filter and sampling, `z = y * exp(-j*theta)`. For a QPSK point at 45 degrees (+-1+-1j) the angle error is proportional to
`e = sgn(Re z) * Im z - sgn(Im z) * Re z` (it is zero for all four points when `theta` is right, and the sign is the same in all quadrants: that is why the loop cannot tell the quadrants apart).
The loop filter is again second order: `omega += beta*e` (the frequency, a register you can read: **the carrier offset**), `theta += omega + alpha*e`.

**Loop gains from a bandwidth.** Both loops are second-order with damping `zeta = 0.707`. For a bandwidth `bw` (radians per symbol; `2*pi/400` = 2.4 kHz at 960 ksym/s) the proportional and integral gains are

```
alpha = 4 zeta bw / (1 + 2 zeta bw + bw^2)        beta = 4 bw^2 / (1 + 2 zeta bw + bw^2)        (the formulas of GNU Radio's blocks)
```

In the FPGA they are **registers** (TA, TB for timing, CA, CB for the Costas loop), written from Python, and the receiver reads them on every symbol: **you can change them while it runs**.
This is what makes the design useful for experiments: a wide loop acquires quickly, a narrow loop has less noise (E.3).
The loop gains are proportional to the *square of the symbol amplitude* (the detector output grows with the product of two amplitudes), so the AGC reference is part of the loop design: `REF = 16384` means a symbol magnitude 2.0 (unit 8192), as in GNU Radio.

## A.4 Architecture decisions

| decision | why |
|---|---|
| **Transmitter at the sample rate, receiver engine at 100 MHz.** The transmitter produces one sample per `ce` (= `dac_valid_i0`, every second `l_clk`), so it must keep up with the sample rate. The receiver works **once per symbol** (every 104 cycles at 100 MHz), so one set of multipliers can be reused. | A receiver with a 44-tap, 4-bank filter and two loops, built as a pipeline at the sample rate, would use many times more DSP slices; time multiplexing needs 4 multipliers. The engine needs about 65 of the 104 cycles available: **no overruns**. |
| **Dual-clock sample RAM + Gray-coded write counter** between `l_clk` (writes) and the 100 MHz engine (reads). | The two clocks are unrelated; a Gray counter changes one bit at a time, so two flip-flops are enough to cross it safely. The RAM is only read for samples the (synchronised) counter says are complete. |
| **AXI-Lite registers on the 100 MHz PS clock** for the receiver; the transmitter's registers hand their values to `l_clk` through a commit/acknowledge toggle. | the receiver's registers are only read by the engine on the same clock (no crossing); the transmitter's parameters must change *at one sample* (a half-updated amplitude is a glitch). |
| **A self-synchronising PRBS-15 checker in the FPGA** with counters, instead of a DMA that moves bits to Python. | bit-error counting at 1.92 Mbit/s runs for hours without any CPU load; no buffer, no DMA, no software that could be the cause of an error. |
| **A capture RAM of 1024 soft symbols.** | the constellation can be looked at without a DMA: one read of 1024 words. |
| **The loops report what they measured** (`OMEGA`, `RATE` registers). | the receiver is also a measuring instrument for the carrier offset and sample-clock offset. |

## A.5 Functional block diagrams: what every block does, and why it is needed

Parts B and C show the *implementation*: the Verilog, state by state. This section shows the *function*: the same blocks drawn as a communications engineer thinks of them, each with the reason it exists. Every block is there because of one thing that goes wrong on a real link.

### A.5.1 The link, and what goes wrong in it

![The link and the problems in it](img/qpsk_func_link.png)

| what goes wrong | size in our link | the block that fixes it |
|---|---|---|
| the ADC has a finite step (12 bit) | the received signal is a few tens of counts rms: the RX gain must put it well above one step | RF/ADC gain setting (RX gain index) |
| the level is unknown | changes by tens of dB with distance and gains | **AGC** |
| noise, and an unknown sampling instant that also drifts | the transmitter's sample clock differs from ours by **10.4 ppm**: the best instant moves by one sample in about 24,000 symbols | **matched filter** (best SNR) and **timing loop** |
| the carrier is not at the frequency we expect, and its phase is unknown | the two crystals differ by **10.4 ppm of 915 MHz = +9.7 kHz** = 3.6 degrees of rotation per symbol | **Costas loop** |
| after the loop has locked, the constellation may sit rotated by 0, 90, 180 or 270 degrees | the loop cannot tell | **differential encoding** at the transmitter, **differential decoding** at the receiver |

The rest of the design follows from this table. A transmitter has little to do (it knows everything); the receiver is a chain of loops, each removing one unknown, in an order that matters (A.5.3).

### A.5.2 The transmitter, block by block

![Transmitter, functional blocks](img/qpsk_func_tx.png)

The rates along the chain: **1.92 Mbit/s** of data -> **960 ksym/s** (two bits per symbol) -> **3.84 MSPS** (four samples per symbol after the pulse shaping) -> a 3.84 MSPS complex stream to the AD9361, which converts it to a signal around 915.0 MHz about **1.3 MHz wide** (960 kHz x 1.35).
Blocks 1 to 4 work at the symbol rate and need only a handful of gates: they are *bookkeeping*. Block 5 is the only one that works at the sample rate, and because the symbols are +-1 it needs additions, not multiplications (B.5).

### A.5.3 The receiver, block by block

![Receiver, functional blocks](img/qpsk_func_rx.png)

**Why this order.**
* **AGC first**, because the gains of both loops depend on the signal amplitude (the detectors multiply amplitudes: the gain goes with the square).
* **The matched filter before everything else at the symbol rate**: it gives the best SNR, and the timing and phase detectors work on its output.
* **Timing before carrier**: the timing detector `e = Re{ y x conj(y') }` is a product of the filter output and its own derivative, so a rotation of the constellation cancels out of it (both rotate together; even a steady rotation only adds a term `j x omega x |y|^2` whose real part is zero). It works while the carrier loop has not locked yet.
  The Costas loop, on the other hand, needs one sample per symbol at the *right instant*, which only the timing loop delivers.
* **Carrier recovery before the decision**, and the **differential decoder after it**: the decision needs an un-rotated constellation; the decoder turns the 4-fold ambiguity into nothing.
* The **checker** sits at the end because it only looks at bits.

### A.5.4 Symbol timing in pictures

![Timing recovery: eye diagram and S-curve](img/qpsk_func_timing.png)

*Left, the eye diagram.* If the received pulses are laid on top of each other, a gap opens where every trace passes through +1 or -1: that is the instant to sample, and the matched filter was designed to leave no inter-symbol interference there. Early or late, the traces scatter: noise and neighbouring symbols leak into the decision.
The transmitter and the receiver have independent crystals, so *that instant moves*: by 10.4 ppm, one symbol of drift every 100,000 symbols, which is why the sampling instant cannot be fixed once and for all.

*Right, how the loop knows.* A **derivative filter** (a second FIR next to the matched filter) gives the slope y' of the output. Before the peak y and y' have the same sign, after the peak opposite signs, at the peak y' = 0.
The product `e = y x y'` is therefore positive when we sample **early** and negative when we sample **late**, whatever the sign of the symbol (a negative symbol has a negative peak and a negative rising slope: the same product). Averaged over the data, `e` is the S-curve of the plot: **zero exactly at the right instant**, with the sign that pushes towards it on both sides: negative feedback.
The loop filter turns `e` into the position: the *integral* path learns the clock offset (the `RATE` register: +10 ppm here), the *proportional* path follows the jitter. The position has a fractional part, which is why the filter exists in 16 versions ("arms") of 1/16 sample.

### A.5.5 The Costas loop in pictures

![The Costas loop](img/qpsk_func_costas.png)

*Left, the loop.* The matched-filter output `m` is rotated back by the NCO's angle `theta` (**derotate**: `z = m x e^(-j theta)`); the **slicer** takes the nearest of the four points; the **phase detector** measures the angle left between `z` and that point, `e = sgn(zi) zq - sgn(zq) zi`
(about `|z| x sqrt(2) x sin(error)`, positive for a positive error); the **loop filter** adds a proportional term (`alpha x e`, follows the phase) and an integral term (`beta x e` accumulated into `omega`, learns the frequency); the **NCO** produces the next `theta`. A rotation of 3.6 degrees per symbol (9.7 kHz) is a constant frequency error:
the integrator settles on it, and `omega` *is* the carrier offset that the receiver reports.

*Right, the detector.* The curve shows `e` against the rotation of the constellation: it is zero at 0, 90, 180 and 270 degrees, and each is a stable point (the slope pushes back). **The loop cannot tell them apart**: any of the four is a perfect lock. That is the 4-fold ambiguity, and the reason for the differential code. An example (chunks c = 1, 3, 0, 2):

| step | 1 | 2 | 3 | 4 | how it was obtained |
|---|---|---|---|---|---|
| data chunk c | 1 | 3 | 0 | 2 | the data |
| pre-differential map p | 1 | 2 | 0 | 3 | `[0,1,3,2]` |
| transmitted point d | 1 | 3 | 3 | 2 | `d = d + p (mod 4)` |
| received point, constellation locked **+90 degrees off** | 2 | 0 | 0 | 3 | every point moves by +1 |
| receiver: `dd = d' - d'(previous)` | - | 2 | 0 | 3 | the +1 cancels in the difference |
| after the map `[0,1,3,2]` again | - | 3 | 0 | 2 | **the data again** (chunks 2 to 4) |

The only price: one symbol error disturbs two differences, so errors come in pairs (about 2 dB at the same BER).

**Pull-in.** The loop can only pull in a frequency error of about `960 kHz / N` for a loop bandwidth of `2 pi / N` (9.6 kHz for N = 100): the B210's +9.7 kHz is at the edge, which is why the notebook's `acquire()` tries frequency hints (E.3) and why GNU Radio's receiver has a separate FLL in front of its Costas loop.

### A.5.6 From the functional blocks to the Verilog

| functional block | why (short) | Verilog | what the Verilog looks like |
|---|---|---|---|
| TX 1 test bits | countable errors | B.2 | 15-bit LFSR, two steps per symbol |
| TX 2 to 4 pairs, map, differential encoder, mapper | 2 bits/symbol, Gray-like, rotation-proof | B.2 | a 2-bit adder and two sign bits |
| TX 5 pulse shaping | 1.3 MHz band, no ISI | B.4, B.5 | ROM of 12 taps per phase + 12 adders/subtractors |
| TX 6 scale and DAC | level | B.6 | one multiplier per axis, pipeline register |
| RX 1 samples and RAM | two clocks | C.3 | dual-clock RAM + Gray-coded counter |
| RX 2 AGC | known amplitude | C.5 (S0 to S3) | multiply by `g`, a level estimate, `g += MU x error` |
| RX 3 matched filter + timing loop | best SNR, right instant | C.4, C.6 (MAC, S2 to S4) | 4 DSP multiplies reused 44 times, rate and position update |
| RX 4 Costas loop | carrier offset and phase | C.7, C.8 (S5 to S8) | 1024-entry sine/cosine table, 4 multiplies, two accumulators |
| RX 5 decision + differential decoder | bits | C.9 (S6) | signs, a 2-bit subtraction, the map |
| RX 6 checker, counters, capture RAM | measure without software | C.10, C.11 | 15-bit predictor, counters, 1024-word RAM |

The Verilog diagrams in B and C show the same blocks as hardware: registers, ROMs, DSP slices, the state machine.

## A.6 The GNU Radio flowgraphs and the Verilog, side by side

The B210 side of the tests is two GNU Radio flowgraphs (`qpsk_b210_tx.grc`, `qpsk_b210_rx.grc`, E.13). They contain the same functions as the FPGA, built from GNU Radio's stock blocks. If you know one side, the other follows: each row below pairs a block **as it is named in Companion** with the Verilog that does the same job.
(Blue = a stock GNU Radio block, yellow = an embedded Python block, orange = the B210 radio, grey = a viewer. On the right: the colours of the Verilog diagrams in B and C.)

![Transmitter: GNU Radio blocks and Verilog](img/qpsk_func_vs_grc_tx.png)

The transmitter's `digital_constellation_modulator` is one block in Companion, but it is a *hierarchical* block (`generic_mod`) made of the five blocks inside the frame: bits to chunks, the pre-differential map, the differential encoder, the symbol mapper and the RRC pulse shaper.
In `qpsk_tx.v` the same five steps are a few lines each (B.2), and the pulse shaper is the ROM plus twelve adders (B.4, B.5).

![Receiver, front half: GNU Radio blocks and Verilog](img/qpsk_func_vs_grc_rx1.png)

![Receiver, back half: GNU Radio blocks and Verilog](img/qpsk_func_vs_grc_rx2.png)

**The knobs, side by side.** The same experiment can be done on either end; this is how the controls correspond:

| GNU Radio flowgraph | what it sets | the P501 notebook | what it sets |
|---|---|---|---|
| `tx_on` (Transmit ON/OFF) | `multiply_const` = `tx_amp x tx_on` | *P501 transmits* | `enable` of `qpsk_regs` |
| `tx_amp` | `multiply_const` | *TX amplitude* | `amp` of `qpsk_regs` (Q15) |
| `tx_gain` (UHD gain, 0 to 80 dB) | the B210's TX gain | *TX atten* (89.75 to 20 dB) | the AD9361's TX attenuation (`p501_radio`) |
| `rx_gain` (UHD gain) | the B210's RX gain | *RX gain* (index 0 to 76) | the AD9361's RX gain index |
| `bw_div` = N: `w = 2 pi / N` into the FLL, `pfb_clock_sync` (`loop_bw`) and `costas_loop_cc` | the three loop bandwidths | *Live loop N* | the four gain registers TA, TB, CA, CB (the same formulas, `regs_from_bw`) |
| BER box (`epy_block` + `qtgui_number_sink`) | bit errors / bits | the picture's *BER estimate*, `MISMATCH / 3 / BITS` | the FPGA's checker counters |
| `qtgui_const_sink_x` | 1024 symbols after the Costas loop | the live constellation | the capture RAM (`rx.capture()`) |

**What is different, and why.**

| | GNU Radio | FPGA | why |
|---|---|---|---|
| structure | one block per function, each running continuously on the PC | one engine that runs a short program once per symbol (S0 to S9), sharing 4 multipliers | the symbol rate is 100 times slower than the clock |
| arithmetic | 32-bit floating point | integers with chosen widths, shifts and clips (C.1), rounded integrators (F.3) | DSP slices, and bit-exact checking against the model |
| polyphase arms | 32 (`filter_size`), the derivative bank included | 16 arms of 44 taps, only the arm selected by the timing loop is computed per symbol | 1/16 of a sample is enough resolution; 4 multipliers instead of 32 filters |
| coarse frequency | `digital_fll_band_edge_cc` in front of the clock sync | none: the Costas loop pulls in, helped by `W0` and `acquire()` | an FLL costs a band-edge filter pair; `acquire()` costs a few lines of Python |
| protection against bursts | the limiter (`rail_ff`) | saturating arithmetic (`clip16`, `clip24`) | fixed-point saturates by itself |
| loop gains | `loop_bw`, `w` (floating point) | registers TA, TB, CA, CB, written from Python | live adjustable, no re-synthesis |
| bit error counting | Python block (`epy_block`) on the PC | 15-bit predictor and counters in the FPGA | no bit leaves the FPGA, at 1.92 Mbit/s |
| signal level after the AGC | reference 1.0: the symbols come out with |z| of about 1.03 | reference `REF` = 16384, a level estimate of 2.0 (8192 = 1.0): the decision points sit near 1.24 on each axis, |z| about 1.75 | the loop-gain registers are scaled for this level, which is why `REF` matters (A.3, C.1) |

One flowgraph detail worth knowing: GNU Radio's `pfb_clock_sync_ccf` is the same *kind* of block as the FPGA's timing section, and the two behave alike on the same signals; the difference that bit us was not in the algorithm but in the surroundings: the GNU Radio block stalls the whole flowgraph if a burst reaches it, which the limiter prevents (E.13), where the fixed-point FPGA just saturates.

---

# Part B. The transmitter (`rtl/qpsk_tx.v`)

![Transmitter block diagram](img/qpsk_block_tx.png)

*This is the implementation view; what each block does and why it is needed is in A.5.2.*

The transmitter replaces the DAC DMA path for TX1, exactly as the DDS of tutorial 2 does: its outputs go to `dac_data_i0` / `dac_data_q0` of `axi_ad9361`, and its sample clock enable is `dac_valid_i0`.
Everything below happens only on a `ce`; between the `ce`s the module holds its state.

## B.1 Interface and the two pipeline stages

@@ rtl/qpsk_tx.v 11 23 module interface

* `ce` is `dac_valid_i0`: one pulse per DAC sample.
* `enable` and `amp` come from the register block `qpsk_regs` (the same `dds_regs.v` as in tutorial 2, see B.7).
* `amp` is Q15 (0 to 32767); `dac_i` / `dac_q` are 16-bit signed; the AD9361's DAC uses the top 12 bits.
* The module has **two pipeline stages** (`ysum_*`, then `dac_*`): the sum of the taps is registered, then scaled. The output is one sample late; the NumPy model includes this (the first sample is 0).

## B.2 The pseudo-random source: PRBS-15

A 15-bit linear-feedback shift register, polynomial x^15 + x^14 + 1, seed `0x7FFF` (all ones). The output bit is the most significant bit `lfsr[14]`; the next state shifts left and feeds
back `lfsr[14] ^ lfsr[13]`. The sequence repeats every 32767 bits and contains every non-zero 15-bit pattern once, which makes it a good test of the whole chain (a stuck bit, a missing
pulse or an inversion shows up as errors).

A symbol needs **two bits**, so the register is advanced **two** steps per symbol. The code computes the next two states combinatorially (`l1`, `l2`) so that the two bits `lfsr[14]`, `l1[14]` are
available at the same time:

@@ rtl/qpsk_tx.v 55 62 the next symbol: two LFSR steps, the 2-bit chunk, the map [0,1,3,2], the differential encoder, the quadrant

* `c = {lfsr[14], l1[14]}`: the first bit is the **MSB** (what GNU Radio's `unpack`/`pack` convention expects).
* `p` = the pre-differential map `[0,1,3,2]`: chunks 2 and 3 swap.
* `dn = d + p` : a 2-bit adder; **the wrap-around of 2 bits is the modulo 4**.
* `ni`, `nq` are the *signs* of the next symbol, from `dn`: point 0 = (+,+), 1 = (-,+), 2 = (-,-), 3 = (+,-); so `ni = dn[1] ^ dn[0]` (negative I for points 1 and 2) and `nq = dn[1]` (negative Q for points 2 and 3).

Only the sign bits are kept: the symbols are +-1.

## B.3 Start state: the first symbol is already "in the pipe"

With `enable = 0` the module sits in a defined state so that `enable = 1` starts the pattern *from its first bit* (the receiver, and `qpsk_model.py`, rely on this):

@@ rtl/qpsk_tx.v 24 34 constants: the state after the first symbol has been prepared (computed by the synthesis tool)

The first symbol is made from the seed's first two bits; at reset the LFSR already points to the *third* bit (`S2`), `d` holds the differential state after symbol 0 (`D0`), and the history holds
that first symbol (`NI0`, `NQ0`). The register `hist_*` initially has 11 zeros = +1 (positive) symbols before it, as if the transmitter had sent +1 symbols forever.

## B.4 History of symbols and the polyphase coefficient ROM

@@ rtl/qpsk_tx.v 36 42 state registers and the ROM instance

`hist_i[j]` is the sign of the symbol sent `j` symbols ago (bit 0 = newest, 1 = negative). The 45-tap RRC filter gets one **phase** `ph` (0..3) per output sample and uses 12 taps:
`h[4j + ph]`, j = 0..11. The ROM `qpsk_rrc_coef` returns those 12 coefficients, as one 192-bit vector, for the current `ph`. It is **generated** by `qpsk_model.py` from the same function that the model uses
(so the model and the RTL cannot disagree):

@@ tutorial/qpsk/p501_tx/qpsk_model.py 21 32 the RRC taps (closed form) and their integer version, peak = 12288
@@ rtl/qpsk_rrc_coef.v 1 12 the generated ROM (first phases)

The scale 12288 for the peak tap is chosen so that the largest sum of absolute values of 12 taps (about 17,800) still fits 17 signed bits (`ysum`), and with `amp` < 2^15 the scaled
product's bits [30:15] cannot overflow.

## B.5 The FIR: twelve additions with signs, no multiplier

@@ rtl/qpsk_tx.v 44 53 the sum of the taps, sign chosen by the symbol

An `always @*` loop with a constant bound unrolls into 12 adders/subtractors in parallel: for tap `j` the sign comes from `hist_i[j]` (and `hist_q[j]` for the quadrature branch).
The I and Q branches are independent: the same coefficients, different symbol signs.

## B.6 Clocked part: the pipeline, the amplitude and the symbol clock

@@ rtl/qpsk_tx.v 64 81 amplitude scaling, pipeline registers and the symbol clock (ph counts the samples within a symbol)

* On every `ce`: `ysum_*` registers the sum (stage 1); `dac_*` registers `ysum x amp` (stage 2). `prod[30:15]` is the product shifted right by 15 (Q15).
* `ph` counts 0,1,2,3. At `ph == 3` the *next* symbol is taken over: the LFSR advances, `d` advances, and the sign bits are shifted into the history. So during the four samples of symbol *m* the history holds
  symbol *m* as the newest.
* `if (!resetn || !enable)`: reset state and **zero output**. This is what makes `enable` a clean start/stop: when it is low the DAC gets zeros.

The model in `qpsk_model.py` is bit-exact with this block, including the latency:

@@ tutorial/qpsk/p501_tx/qpsk_model.py 43 72 the NumPy model of the transmitter (symbol indices and the sample-by-sample output, floor shift as in the RTL)

## B.7 Register block and start/stop: why `commit`

The transmitter uses the **same register block as the DDS** (`dds_regs.v`, instance name `qpsk_regs`, address `0x9C460000`): `CONTROL` bit 0 = enable, `AMP` (Q15), `COMMIT`. The frequency word is unused.
The values are written on the 100 MHz AXI clock but used on `l_clk`; they must change **together**, and never half-written. The hand-over:

@@ rtl/dds_regs.v 97 113 hand-over: COMMIT toggles a flag; the l_clk side sees the toggle through two flops and only then takes the (long stable) parameters

Software writes `AMP`, `CONTROL`, then `COMMIT`; the register block toggles `commit_tog`; `l_clk` sees it two cycles later, loads `enable` and `amp` in one clock, and toggles `ack_tog`;
software waits for `STATUS` bit 0 (`applied`). If the AD9361 clock is not running the wait times out (see `P501Dds.set`, E.2).

---

# Part C. The receiver (`rtl/qpsk_rx.v`)

![Receiver block diagram](img/qpsk_block_rx.png)

*This is the implementation view; what each block does and why it is needed is in A.5.3 to A.5.5.*

The receiver is a **small processor with a fixed program**: one *engine* that, for every symbol, runs a sequence of states (`ST_WAIT`, `ST_MAC`, `S0`..`S9`). Each state is one clock cycle at 100 MHz; the DSP products are
formed combinationally in a state and registered at its end. The numbers in every line come from the integer model `qpsk_rx_fixed.py`, which is why that file is the best way to read this one.

## C.1 Number formats (read this once)

| signal | format | meaning |
|---|---|---|
| `x` (ADC sample) | signed 12 bit in 16 (+-2047 counts) | what the AD9361 delivers |
| `cm`, `cd` (coefficients) | int16, x 2^15 | matched filter and derivative filter, 16 arms x 44 taps (`qpsk_rx_rom`) |
| `m`, `d` (MAC result) | 24-bit, `acc >> 11` | Q4: **16 = one ADC count** |
| `g` (AGC gain) | 17-bit unsigned, Q10 | 1024 = gain 1.0 |
| `m'`, `d'` (after AGC) | int16, `(m*g) >> 10` | symbols: 8192 = amplitude 1.0 |
| `p` (timing position) | 52 bit: `[51:20]` sample index, `[19:16]` arm (of 16), `[15:0]` fraction | Q16 in arms; one symbol = 64 << 16 |
| `rate` | signed 32, Q16 arms per symbol | the sample-clock offset: `ppm = -rate / 2^22 x 10^6` |
| `theta`, `omega` | 32-bit, turns x 2^32 | NCO phase and frequency: `Hz = omega / 2^32 x 960000` |
| `e_t`, `e_c` | signed 14 bit, clipped to +-8191 | detector outputs |
| TA, TB | gain x 2^24 (then `>> 21`) | timing loop |
| CA, CB | rad x 2^27 / 2 pi (then `>> 8`) | Costas loop |

## C.2 Registers (AXI-Lite)

@@ rtl/qpsk_rx.v 53 81 the control registers (reset values = loops 2 pi/400, REF 16384, G0 1.0, W0 0, rate limit 5 %)

A write is accepted when address and data are both valid (`do_write`) and the previous response has been taken; the registers are plain flops on the AXI clock. The engine reads them directly: **a write acts on the next symbol**. Reads:
see C.11.

## C.3 The sample RAM and the clock crossing

@@ rtl/qpsk_rx.v 83 104 samples written on adc_clk into a 256-entry RAM; the write counter crosses as Gray code through two flops

* The RAM holds the last 256 samples (the filter window is 44).
* `wr_gray` changes **one bit per count**, so the two-flop synchroniser (`g_s1`, `g_s2`) delivers either the old or the new value, never a wrong one. `gray2bin` converts back.
* The false-path constraints in `src/qpsk_rx_cdc.xdc` tell Vivado that these two crossings are intentional (D.3).

The engine knows how many samples are complete (`wr_sync`) and which window it wants (`base + t`). `avail = wr_sync - base - t > 0` starts a symbol when the newest sample of the window has been written:

@@ rtl/qpsk_rx.v 106 119 engine state: p (the position), rate, omega, theta, the AGC gain g

## C.4 Matched filter and derivative filter: the MAC

@@ rtl/qpsk_rx.v 121 137 the multiply-accumulate pipeline: sample RAM read, ROM, four products, four accumulators

For tap `ic` = 0..43 the engine reads the sample `x[t - ic]` (`ram_raddr = base + t - ic`) and the coefficients of the current arm (`{arm, ic[5:0]}`) from the ROM. **Four DSP multipliers work in parallel**:
`xi*cm`, `xq*cm` (matched filter I and Q) and `xi*cd`, `xq*cd` (derivative filter). The pipeline (RAM read, product, accumulate) adds 3 cycles, so `ST_MAC` lasts 47 cycles (`ic` 0..46).
The ROM is generated from the same NumPy arrays as the model:

@@ tutorial/qpsk/p501_rx/qpsk_rx_model.py 28 34 the filter banks: arm k holds the prototype's samples k, k+16, k+32 ...; the derivative bank is the central difference of the prototype
@@ rtl/qpsk_rx_rom.v 1 7 the generated ROM (first lines)

## C.5 AGC: S0 and S1

@@ rtl/qpsk_rx.v 228 235 S0: accumulators >> 11 (clipped to 24 bit); S1: x gain >> 10 (clipped to 16 bit)

The four MAC results are scaled by the same gain `g` (Q10), so the matched and the derivative outputs keep their ratio. A level estimate and the gain update follow in `S2` and `S3`:

@@ rtl/qpsk_rx.v 184 204 the combinational products used by the states (level error, gain update, both loops)

* **level** `a = max(|mi2|,|mq2|) + min(|mi2|,|mq2|)/2` (an approximation of the magnitude without a square root; error < 12 %), `err = REF - a`, `g += (MU * err) >> 16`, clipped to 16..131071.
* With `REF = 16384` the loop drives the **symbol magnitude to 2.0** (8192 = 1.0, so about 11585 per axis): the value that the loop gains were designed for.
* `MU` is the speed (default 40); `G0` the initial gain (1.0).

## C.6 Timing loop: S2, S3, S4

@@ rtl/qpsk_rx.v 236 249 S2: the level and the timing error; S3: AGC gain and rate integrator; S4: the new sampling position

* `e_t = (mi2*di2 + mq2*dq2) >> 13`: **the product of the matched and the derivative filter output** (summed over I and Q): positive or negative depending on early or late (the sign of `e_t` is the *direction*).
* `rate_new = rate + ((TB * e_t + 2^20) >> 21)`: the **integral** part. It is **rounded**, not truncated: see F.3. The result is limited to +-`MAXR` (default 5 % of a sample per symbol).
* `p = p + 64<<16 + rate + ((TA * e_t) >> 21)`: the **proportional** part and the nominal advance of **4 samples = 64 arms** (`4194304 = 64 << 16`).
  The arithmetic is in a wide register because `p` counts all samples since the start.
* The next window is `t = p[51:20]`, `arm = p[19:16]`. The loop makes `arm` change slowly with the clock offset; a whole sample slips when the arm index wraps.

The same equations in the integer model (the *specification* of this block):

@@ tutorial/qpsk/p501_rx/qpsk_rx_fixed.py 53 67 the engine in NumPy: window, MAC, AGC, timing loop (compare with C.4 to C.6)

## C.7 Derotation: S5 and the 1024-entry sine/cosine table

@@ rtl/qpsk_rx.v 250 253 S5: z = m' * exp(-j theta): four multiplies, shifted right by 15

@@ rtl/qpsk_rx.v 155 156 the table instance: address = the top 10 bits of theta
@@ rtl/qpsk_rx_trig.v 1 8 the generated table: cos and sin of 2 pi a / 1024, Q15

`theta` is a 32-bit phase in turns x 2^32; its top 10 bits address the table (resolution 0.35 degrees). `zi = mi2*cos + mq2*sin`, `zq = mq2*cos - mi2*sin`: a complex multiplication by `exp(-j theta)`.
The table is generated with the ROM (`gen_rx_rom.py`).

## C.8 Costas loop: S6, S7, S8

@@ rtl/qpsk_rx.v 254 275 S6: Costas error, decision, differential decode, PRBS checker, counters, capture; S7: frequency; S8: phase

* `e_c = sgn(zi)*zq - sgn(zq)*zi` (`ec_raw` in the listing of C.5) clipped to +-8191: the angle between the symbol and its quadrant's 45-degree point, times the amplitude.
* `omega += (CB * e_c) >> 8` (S7): the frequency integrator. `OMEGA` is the offset in turns/symbol x 2^32: this is what is read as the **carrier offset**.
* `theta += omega + ((CA * e_c) >> 8)` (S8): the phase advances by the frequency plus the proportional correction.
* The register scale `CA = alpha_rad x 2^27 / 2 pi`: `theta` is in turns x 2^32 and the error has a unit of 2^13, so `>> 8` leaves exactly `alpha / 2 pi x 2^32` per unit error / 2^13.

## C.9 Decision, differential decoding and bits

@@ rtl/qpsk_rx.v 170 176 the slicer: signs of zi and zq -> point 0..3; difference to the previous point; the map [0,1,3,2]

`pt` is the quadrant of `z`; `dd = pt - prev` (2-bit subtraction = modulo 4); the 2-bit map gives the two data bits `b0` (MSB) and `b1`. Everything is combinational from `zi`, `zq`; `S6` registers the result (`bits2`, `prev`).
The NumPy side of the same step:

@@ tutorial/qpsk/p501_rx/qpsk_rx_fixed.py 68 80 the integer model of S5..S8 and the decision

## C.10 The PRBS-15 checker: counting bit errors without a reference

The checker does not need to know *where* in the PRBS period the data are. A maximal-length sequence satisfies `a[n] = a[n-15] ^ a[n-14]`; the checker keeps the **last 15 received bits** in `prbs_sr`, predicts the next bit
from two of them, and counts a mismatch when the next bit differs from the prediction. After 15 bits it is synchronised, whatever the starting point; if a bit is received wrong, it is wrong **in the prediction register too**,
which causes the next two predictions (when the wrong bit passes the two tap positions) to fail as well: **an isolated bit error produces 3 mismatches**. That is why `BER ~ MISMATCH / 3 / BITS` in the Python driver.

@@ rtl/qpsk_rx.v 177 182 the prediction for the first and the second bit of a symbol, mismatch and checked-bit counts

(`pr0`, `pr1` are the "register is full" flags: no counting during the first 15 bits after `run` rises.) An unlocked receiver delivers random bits, which mismatch the prediction on every second bit: the counters then give a BER estimate of about 0.17 (= 0.5 / 3), which is what the unlocked runs show; a locked receiver gives exactly 0.
estimate saturates at about 0.5; a locked receiver gives exactly 0.

## C.11 Counters, capture RAM and read-back

The decision stage also drives the statistics and the capture RAM in `S6` (code in C.8):

* `n_bits`, `n_mism`, `n_sym`: 32-bit counters, reset when `run` (`CTRL[0]`) goes low. A write of `CTRL = 3` after `CTRL = 1` (bit 1 rising) **arms the capture**: the next 1024 values of `{zq, zi}` are stored in `cap_mem`, `STATUS[1]` = done.
* `n_over` counts passes that started late (more than 200 samples behind): must stay 0.

@@ rtl/qpsk_rx.v 285 312 the read side: STATUS, counters, OMEGA, RATE, GAIN, the capture RAM at +0x1000

## C.12 Timing and why the loops do not depend on the FPGA clock

The engine performs **one** loop update per symbol (960 kHz); the loop dynamics are those of the NumPy model and do not depend on the 100 MHz clock. Each state is one multiplication (or a few in parallel) followed by a shift and a clip,
with nothing pipelined across states, and the design closes timing at 100 MHz (**WNS +0.417 ns, WHS +0.011 ns**). In simulation the engine needs about 65 of the 104 cycles of a symbol; `OVERRUNS` stays 0.

---

# Part D. Integration, register interface and verification

## D.1 Adding the blocks to the block design (Tcl)

Each part is a *module reference* (Verilog added to the project as a block). The Tcl scripts are the "steps" of the earlier tutorials, one idea per file:

@@ tutorial/qpsk/p501_tx/steps/step2_tx.tcl
@@ tutorial/qpsk/p501_tx/steps/step3_dac.tcl
@@ tutorial/qpsk/p501_rx/steps/step1_rx.tcl

Transmitter: `step1_regs.tcl` (register block at `0x9C460000`), `step2_tx.tcl` (instance; `ce` = `dac_valid_i0`, reset from `axi_ad9361/rst` inverted), `step3_dac.tcl` (**delete the old nets on `dac_data_i0/q0`** and connect the transmitter,
exactly as the DDS does), `step4_constraints.tcl`.
Receiver: `step1_rx.tcl` (instance on `l_clk`, `adc_valid_i0`, `adc_data_i0/q0` and the 100 MHz clock; address `0x9C470000`, 16 KB because the capture RAM is at +0x1000), `step2_constraints.tcl`.

`create_project.tcl` builds any combination with options:

```bash
vivado -mode batch -source create_project.tcl -tclargs FFT=0 QPSK=1 QPSKRX=1 RUN=bit JOBS=8     # transmitter + receiver: p501_qpsk_trx.bit/.hwh, about 10 minutes
python3 tools/fix_hwh.py build/overlay/p501_qpsk_trx.hwh                                        # PYNQ-loadable hardware handoff
```

(`QPSK=1` replaces the DAC DMA path, so it cannot be combined with `DDS=1`; `QPSKRX=1` is independent of the others.)

## D.2 Resources and timing

The complete design (including the AD9361 interface and the processor system) uses 14.1 k LUTs (12 %), 20.6 k flip-flops, 6.5 BRAM tiles and **53 DSP slices** (4 % of the XCZU5EV).
Setup slack +0.417 ns, hold +0.011 ns at 100 MHz.

## D.3 Clock-domain crossing constraints

@@ src/qpsk_rx_cdc.xdc

The write counter's first flop (`g_s1`) can be set at any moment: not a timing path. The RAM's output is only read for samples that the counter says are complete: the path from the RAM to the read register is not checked either.
The transmitter's hand-over is constrained by `src/dds_cdc.xdc` (which matches the instance names `dds_regs` and `qpsk_regs`).

## D.4 Verification: model, simulation, hardware

| level | what is compared | where | result |
|---|---|---|---|
| float model vs GNU Radio | bit errors on recordings of the B210's signal | `qpsk_rx_model.py` | as good as GNU Radio's receiver |
| integer model vs float model | bit errors on the same recordings | `qpsk_rx_fixed.py` | the same |
| RTL vs integer model | **every symbol**: bits, `zi`, `zq`, `omega`, `rate`, `g`, `e_t`, `e_c` | `sim/tb_qpsk_rx.v` + `sim/compare_rx.py` | **0 mismatches** in 14,990 symbols |
| transmitter RTL vs NumPy model | every DAC sample | `sim/tb_qpsk_tx.v` | bit-exact |
| hardware vs GNU Radio | bit errors counted by the receiver on the other end | E.6 | see F |

The testbench feeds a real recording to the RTL (60,000 samples) with `adc_valid` every second `adc_clk` cycle (as in the AD9361's 1R1T mode), writes a line for every symbol, and the Python script compares the columns:

@@ tutorial/qpsk/p501_rx/sim/tb_qpsk_rx.v 3 6 the clocks: 100 MHz engine, 7.69 MHz adc_clk (= l_clk at 3.84 MSPS)
@@ tutorial/qpsk/p501_rx/sim/tb_qpsk_rx.v 26 43 the stimulus: reset, read the ID, optional TB override, run, one sample per two adc_clk cycles, read the counters
@@ tutorial/qpsk/p501_rx/sim/compare_rx.py 1 17 the comparison with the integer model

---

# Part E. The test code, in detail

## E.0 How the pieces fit

```
 host PC (this machine)                                              P501 board (PYNQ, Linux, Python as root)
 ------------------------------------------------                    ----------------------------------------------
 run_rx_test_4d.py  --ssh-->  p501_qpsk_link.py rx ...  -------->    loads overlay, brings up the AD9361, waits for /tmp/go
        |                                                            then: rx.start(), polls the counters, prints the statistics
        |  (GNU Radio flowgraph: Tx class of qpsk_b210_loop.py)
        v                                                            <--- the radio link, 915 MHz, a few cm of air --->
   USRP B210 transmits PRBS-15 DQPSK at 3.84 MSPS
```

Three kinds of code, from the inside out:

| layer | files | runs on | job |
|---|---|---|---|
| **drivers** (the Python API of the FPGA blocks) | `p501_radio.py`, `p501_dds.py`, `p501_qpsk.py`, `p501_qpsk_rx.py` | the board (and in Jupyter) | bring the AD9361 up; write and read the registers |
| **board scripts** | `p501_qpsk_tx.py`, `p501_qpsk_link.py`, `p501_capture.py` | the board, as root | one experiment each, with a start handshake and a safe end state |
| **host scripts** | `run_tx_test_4c.py`, `run_rx_test_4d.py`, `run_capture_4b.py`; GNU Radio: `qpsk_b210_loop.py`, `qpsk_analyze.py`, `qpsk_decode_file.py` | the PC | start both ends in the right order, collect, analyse |
| **models** | `qpsk_model.py`, `qpsk_rx_model.py`, `qpsk_rx_fixed.py`, `gen_rx_rom.py` | the PC | specifications of the FPGA blocks; ROM generators |

Two rules that every script follows (because the AD9361 is a real radio):

1. **Start quiet, end quiet.** The TX attenuation is set to the maximum (89.75 dB) *before* the calibrations, raised only when the experiment starts, and set back in a `finally:` block whatever happens.
2. **The transmitter starts first, the receiver 2 s later.** The loops must not see the start-up transient of the other radio. Hand-over between processes is a **file**: the board script waits for `/tmp/go`, the host script creates it with `ssh ... touch /tmp/go`.

## E.1 `p501_radio.py`: bring the AD9361 up

The AD9361 is configured over SPI by software; the FPGA cannot produce a data clock until this has run. `bring_up()` is the only mandatory Python in the data path:

@@ notebook/p501_radio.py 24 59 bring_up(): clocks, LO, calibrations, gain, FDD

Points to note:

* `tx_atten_db=89.75` first: the TX is calibrated with the attenuation at its maximum. Only after `analog_init` the requested level is set.
* `rx_gain_index`: manual gain index of the AD9361; **45** is enough for loopback tests; **70** is needed to receive the B210's weak signal through the air (index 45 leaves the receiver at the quantisation floor).
* `axi_ad9361_core_enable` is called twice: before and after the filter loading.
* `ad.info["ok"]`: the product ID read back, both PLLs locked and the ENSM state FDD.

@@ notebook/p501_radio.py 78 86 loopback() and quiet()

`loopback(ad, True)` sets bit 0 of register `0x3F5`: the AD9361 routes the TX digital data back to its RX port inside the chip (no antenna). `quiet()` is `set_tx_atten_db` with a name that says what you mean.

## E.2 `p501_dds.py` and `p501_qpsk.py`: the transmitter's driver

@@ notebook/p501_dds.py 58 80 set(): write the parameters, COMMIT, wait for the l_clk side to take them over
@@ notebook/p501_qpsk.py 1 16 the QPSK transmitter is a thin subclass: start / stop

The pattern of every driver in this series: **write the parameters, then COMMIT, then poll STATUS** with a timeout whose error message names the most likely cause (the AD9361 clock is not running).
`P501QpskTx.start(amp=0.5)` = `set(amp, enable=True)`: the PRBS starts from its first bit. `stop()` = `off()`: the DAC gets zeros.

## E.3 `p501_qpsk_rx.py`: the receiver's driver

**Register map and conversion helpers:**

@@ notebook/p501_qpsk_rx.py 18 36 the register offsets, loop_gains() and regs_from_bw(): from a bandwidth in rad/symbol to the register values

`loop_gains` are the formulas of A.3. `regs_from_bw` applies the fixed-point scale of each register (the same numbers as in the integer model; the two functions must stay identical):

| register | value written | why that scale |
|---|---|---|
| `TA`, `TB` | `round(alpha_or_beta x 2^24)` | `e_t` = 8192 means 1.0; `(TB * e_t) >> 21` = beta x (e_t / 8192) x 2^16: the update in Q16 arms |
| `CA`, `CB` | `round(alpha_or_beta x 2^27 / 2 pi)` | `theta` in turns x 2^32: 2^32 / 2 pi x 2^-13 (error unit) x 2^8 (shift) = 2^27 / 2 pi |
| `W0` | `round(f_hz / 960000 x 2^32)` | initial Costas frequency, turns per symbol x 2^32, masked to 32 bits (two's complement) |
| `MAXR` | `round(max_rate x 16 x 2^16)` | the rate limit in Q16 arms per symbol (0.05 sample = 0.8 arm) |
| `REF`, `MU`, `G0` | integers | AGC level (16384 = 2.0), speed, initial gain Q10 |

**The class:**

@@ notebook/p501_qpsk_rx.py 56 75 configure() writes everything; set_loops() writes only the four loop gains (while running); start() = CTRL bit 0

* `configure()` before `start()`: the start values (`G0`, `W0`) are loaded when `run` rises.
* `set_loops()` can be called **while the receiver runs**: the RTL reads `TA..CB` on every symbol. This is the "acquire wide, track narrow" mechanism (E.5).

**Starting reliably: `acquire()`.** The Costas loop has no frequency detector in front of it (GNU Radio's receiver has the FLL), and the pull-in range of a loop of bandwidth `2 pi / N` is about
960 kHz / N: **9.6 kHz for N = 100, exactly where the B210's 9.7 kHz offset is**. Started cold, the receiver sometimes pulls in and sometimes ends at 0 Hz with a smeared constellation and 2 % errors.
`acquire()` therefore tries initial-frequency hints in turn (0, +6, -6, +12, -12 kHz, the `W0` register), and accepts a try only when the receiver is **locked** (no new mismatch in 50 ms *and* a sane constellation from the capture RAM) and its
frequency estimate has **stopped moving**; then it narrows both loops live and checks the lock once more:

@@ notebook/p501_qpsk_rx.py 36 51 the lock criterion: the PRBS counters alone are not enough (a receiver that outputs only zeros has no mismatches), so the constellation must be sane too
@@ notebook/p501_qpsk_rx.py 76 111 locked() and acquire()

On the hardware (B210 at 80 dB TX gain): **20 of 20 acquisitions locked at +9.7 kHz** (first try in 14 of 19 logged cases, otherwise the +6 kHz or -6 kHz hint), taking 0.45 to 1.3 s; three of them had 2 to 57 isolated bit errors in the next 1.5 s, the rest none.

**Reading the results:**

@@ notebook/p501_qpsk_rx.py 115 130 stats() and offsets(): conversion of the raw register values to engineering units

* `OMEGA` is a signed 32-bit number: `omega / 2^32 x 960000` = the **carrier offset in Hz** (the frequency the Costas loop had to add).
* `RATE` (signed, Q16 arms per symbol): `-rate / 2^16 / 16 / 4 x 10^6` = the **sample-clock offset in ppm** (16 arms per sample, 4 samples per symbol; the sign is chosen so that a faster transmitter reads positive).
* `ber_estimate = mismatches / 3 / bits` (A mismatch count of 3 per isolated error, C.10).
* `offsets()` averages many readings, because the instantaneous values jitter by tens of ppm from symbol to symbol (the timing loop's own noise); the mean is the offset.

**The constellation:**

@@ notebook/p501_qpsk_rx.py 131 141 capture(): arm, wait, read 1024 words, split {zq, zi}

Arming needs `CTRL` bit 1 to **rise**, hence the two writes (1, then 3); then `STATUS[1]`; then 1024 reads at `0x1000 + 4 i`. The 32-bit word holds `zq` in the top half and `zi` in the bottom half, both signed 16-bit
(`view(np.int16)` reinterprets the bits as signed).

## E.4 `p501_qpsk_tx.py` (chapter 4c): the board side of the transmitter test

@@ tutorial/qpsk/p501_tx/p501_qpsk_tx.py 9 34 load the overlay, bring up quiet, wait for /tmp/go, transmit, end quiet

Structure shared by all board scripts:

1. Load the overlay and construct the drivers (the constructor reads the **ID register**: a wrong overlay is caught at once).
2. `bring_up(... tx_atten_db=89.75)`, then `tx.off()` and print `READY`; the host script waits for that word.
3. Wait for `/tmp/go` (with a time-out, so that a forgotten board script ends by itself).
4. `try:` set the attenuation, `tx.set(...)`, print `TX_ON`, hold; `finally:` `tx.off(); quiet(...)`: **the end state is the same whatever happens**.

## E.5 `p501_qpsk_link.py` (chapter 4d): the FPGA receiver test

This script has three modes: `loopback` (digital loopback inside the AD9361), `air` (the FPGA transmitter into its own receiver through the antennas) and `rx` (only the receiver; the B210 transmits).

**Setup and the three modes:**

@@ tutorial/qpsk/p501_rx/p501_qpsk_link.py 19 46 arguments, overlay, bring-up, mode-dependent start

* Arguments: `mode atten seconds rx_gain divisor init_freq track_divisor acq_ms` (all but the first optional).
* `rx.configure(timing_bw=2*pi/DIV, ...)`: **the loop bandwidth is specified as a divisor**: 2 pi / 400 is the default, 2 pi / 100 a wide loop, 2 pi / 1600 a very narrow one.
* In `rx` mode the script prints `WAITING`, then blocks on `/tmp/go`: the host starts the B210 first.
* In the other modes the receiver starts first (`rx.start()`) and then the transmitter.

**The measurement loop: how the pull-in time is found.**

@@ tutorial/qpsk/p501_rx/p501_qpsk_link.py 47 65 polling, loop switching, results

* `last_m` = the last `MISMATCH` value seen; `last_t` = when it last **changed**. During the first 0.3 s the loop reads the counter without a pause (each AXI read is about 20 microseconds), so `last_t` resolves a pull-in of well under a millisecond; later it sleeps 5 ms.
* **If `last_t` is in the first half of the run**, the receiver had **pulled in**: everything after `last_t` is error-free. The script prints how many bit errors the pull-in cost (`mismatches / 3`) and a **BER upper bound** for the rest: `1 / (number of bits after the pull-in)`.
* Otherwise errors continue to the end: the receiver is marginal or not locked, and the script prints the BER over the whole run.
* **Acquire wide, track narrow:** at `ACQ_MS` after the start `rx.set_loops(2 pi / TRACK, ...)` narrows both loops, live.
* `rx.offsets(n=400)` (about 2 s) gives the averaged carrier and clock offset; `rx.capture()` the constellation (saved as `.npy`).

```python
finally:
    tx.off(); rx.stop(); p501_radio.loopback(ad, False); p501_radio.quiet(ad, 89.75)
```

Transmitter off, receiver stopped, loopback off, TX attenuation at its maximum: the board is quiet at the end whatever happened.

## E.6 `run_rx_test_4d.py`: the host script (B210 -> P501)

@@ tutorial/qpsk/p501_rx/run_rx_test_4d.py 23 36 start the board script over ssh, wait for WAITING, start the B210, release the board, collect

The order of events (this is the experiment's protocol):

1. `ssh ... rm -f /tmp/go`: remove a stale go-file from an earlier run.
2. `ssh ... python3 /tmp/p501_qpsk_link.py rx ...` is started with `Popen`, its output goes to `p501.log`.
3. Poll `p501.log` for **`WAITING`**: the bring-up (clocks, PLLs, calibrations) takes tens of seconds; the time-out (240 s) and `board.poll()` catch a board script that crashed.
4. `Tx(a); tx.start()`: the B210's flowgraph (E.7) starts transmitting; after `--tx-delay` (2 s) its start-up transient is over.
5. `ssh ... touch /tmp/go`: the receiver starts. `board.wait(...)` blocks until the board script ends.
6. `tx.stop()`, then the lines of the board's log that carry results (`PULLIN`, `averaged`, ...) are printed.

The host script needs the radioconda environment: `source tools/gnuradio_env.sh` (it puts GNU Radio and UHD in the path and points UHD at the B210 images).

## E.7 GNU Radio: the transmitter and the reference receiver (`qpsk_b210_loop.py`)

**The transmitter** is `digital.generic_mod` with the same pre-differential code, differential encoding, RRC and 4 samples per symbol that the FPGA implements. The data are a
repeating bit pattern; for the FPGA receiver the pattern is the PRBS-15 repeated 8 times (8 x 32767 bits = 32767 whole bytes: a **seamless** repeat, because `generic_mod` takes *packed* bytes):

@@ tutorial/qpsk/gnuradio/qpsk_b210_loop.py 23 27 the bit source: random, or PRBS-15 x 8 (the pattern the FPGA checker expects)
@@ tutorial/qpsk/gnuradio/qpsk_b210_loop.py 30 51 the transmit flowgraph: bytes -> generic_mod -> amplitude -> USRP sink

* `constellation_dqpsk()` is *not* the same as the plain QPSK constellation: it is rotation-proof (the loops may lock to any of the 4 rotations), as the FPGA design assumes.
* `tx_amp` (0.25) keeps the B210's DAC out of clipping; the B210's **TX gain** (the knob used in the tests: 60 to 80 dB) sets the power. Very low power only; check the rules where you are.
* The UHD arguments (`num_send_frames=128, send_frame_size=16360`...) enlarge the USB buffers: without them, host-side underruns look like symbol-timing errors.

**The receiver** (the reference) is written out block by block instead of using `generic_demod`, so that its internal signals can be recorded:

@@ tutorial/qpsk/gnuradio/qpsk_b210_loop.py 57 75 AGC -> FLL band-edge -> polyphase clock sync -> Costas -> decoder -> differential decoder -> map -> unpack

| GNU Radio block | corresponding FPGA part |
|---|---|
| `agc2_cc` | AGC (S1, S3) |
| `fll_band_edge_cc` | *(none: the FPGA's Costas loop pulls in the offset; this is why a wide acquisition bandwidth is needed)* |
| `pfb_clock_sync_ccf` (32 arms, `max_rate_dev` limit) | matched/derivative MAC (16 arms), timing loop (S2-S4), `MAXR` |
| `costas_loop_cc(bw, 4)` | derotation, Costas loop (S5-S8) |
| `constellation_decoder_cb`, `diff_decoder_bb`, `map_bb(invert_code)` | slicer, differential decoder, map (S6) |
| `unpack_k_bits_bb(2)` | `{b0, b1}` MSB first |

(The FLL is the main structural difference: the FPGA receiver relies on the Costas loop's pull-in, supported by a wider loop at the start or by the `W0` initial frequency.)

## E.8 `qpsk_analyze.py`: bit errors against a known pattern (GNU Radio side)

When GNU Radio is the *receiver* (chapters 4a to 4c) the errors are counted offline against the known repeating pattern. The unknown starting point in the pattern is found by **circular cross-correlation** with an FFT:

@@ tutorial/qpsk/gnuradio/qpsk_analyze.py 22 33 alignment by cross-correlation, then the error count

* The received bits of an interval after lock are folded into one period and averaged (`reshape(-1, P).mean`) to suppress the errors; the correlation peak gives the **shift** (and an inversion, in case the loop locked with the bits inverted).
* With the alignment known, every received bit is compared with its expected value: `nerr` bit errors.
* The script then reports **time to lock** (the first block with fewer than 0.1 % errors) and **BER after lock**, and prints the match and alignment of consecutive blocks: a *changing shift with a match of 1.0* means cycle slips, *a match of 0.5 to 0.75 everywhere* means never locked.

The FPGA receiver does this alignment in hardware (the self-synchronising checker, C.10), so no correlation is needed on the board.

## E.9 `measure_offsets.py` (chapter 4b): the two offsets from two tones

To measure the carrier offset **and** the sample-clock offset between the radios, the B210 sends two tones at +-1.5 MHz and the P501 records them (`p501_capture.py`, `run_capture_4b.py --signal twotone`):

@@ tutorial/qpsk/p501_capture/measure_offsets.py 1 17 the two-tone measurement

A tone of nominal frequency `f` arrives at `f (1 + d) + dLO`: the **sum** of the two measured frequencies gives the LO offset `dLO`, the **difference** gives the sample-clock offset `d`. Both were found to be **+10.4 ppm**
(9.5 kHz at 915 MHz): the number the FPGA receiver's `OMEGA` and `RATE` registers must reproduce (they do, after the fix of F.3: `RATE` reads 10.0 to 10.8 ppm with narrow loops).

## E.10 `p501_capture.py` and the offline decode (chapter 4b)

`p501_capture.py` records raw I/Q (receive only, TX fully attenuated) with the ADC DMA of tutorial 1's overlay:

@@ tutorial/qpsk/p501_capture/p501_capture.py 17 34 one DMA transfer of up to 16 MiB (1.09 s) into a contiguous buffer, saved as int16 I/Q

`run_capture_4b.py` copies the file to the PC and converts it to `complex64` (divide by 2048 = full scale of the 12-bit samples); `qpsk_decode_file.py` pushes it through the receiver chain of E.7 (as a
`file_source`), and `qpsk_analyze.py` evaluates the result. The same recordings are used to test the NumPy models: **the offline decode is the bridge between GNU Radio and the FPGA design**.

## E.11 The models and the ROM generators

| file | role |
|---|---|
| `qpsk_model.py` | transmitter: PRBS-15, symbols, the RRC taps, the **bit-exact** sample-by-sample model, writes `rtl/qpsk_rrc_coef.v` |
| `qpsk_rx_model.py` | receiver, float: the algorithm (filter banks, loops, decision) |
| `qpsk_rx_fixed.py` | receiver, integers: **the specification of `qpsk_rx.v`**; `regs_from_bw`, `receive_fixed` |
| `gen_rx_rom.py` | writes `rtl/qpsk_rx_rom.v` (matched/derivative banks) and `rtl/qpsk_rx_trig.v` (sine/cosine) from `qpsk_rx_fixed.py` |
| `sim/compare_rx.py` | compares the RTL's per-symbol log with the integer model |

Typical use: change something in `qpsk_rx_fixed.py` (a shift, a clip), see the effect on the bit errors of a recording **in seconds**, then change the Verilog and prove with `compare_rx.py` that the two still agree.

## E.12 Running everything

```bash
source tools/gnuradio_env.sh                                      # GNU Radio + UHD from radioconda

# 4c: the P501's FPGA transmitter, decoded by GNU Radio on the B210
scp tutorial/qpsk/p501_tx/p501_qpsk_tx.py xilinx@192.168.2.1:/tmp/
python3 tutorial/qpsk/p501_tx/run_tx_test_4c.py --out /tmp/p501_tx_run --p501-atten 30 --seconds 6
python3 tutorial/qpsk/gnuradio/qpsk_analyze.py /tmp/p501_tx_run prbs15

# 4d: the B210's PRBS-15 into the P501's FPGA receiver; copy the overlay and drivers first
D=/home/xilinx/jupyter_notebooks/p501_qpsk_trx
ssh xilinx@192.168.2.1 mkdir -p $D
python3 tools/fix_hwh.py build/overlay/p501_qpsk_trx.hwh /tmp/p501_qpsk_trx.hwh             # the PYNQ-loadable hardware handoff
scp build/overlay/p501_qpsk_trx.bit /tmp/p501_qpsk_trx.hwh notebook/p501_qpsk.py notebook/p501_qpsk_rx.py xilinx@192.168.2.1:$D/
scp tutorial/qpsk/p501_rx/p501_qpsk_link.py xilinx@192.168.2.1:/tmp/
python3 tutorial/qpsk/p501_rx/run_rx_test_4d.py --out /tmp/rx_run --tx-gain 75 --seconds 6 --div 100 --track-div 1600

# the FPGA transmitter into the FPGA receiver, no B210 involved (on the board): loopback, then over the air
sudo python3 /tmp/p501_qpsk_link.py loopback 89.75 5 45 400
sudo python3 /tmp/p501_qpsk_link.py air 30 5 70 400
```

## E.13 The interactive demo: two GNU Radio flowgraphs and a notebook

For hands-on experiments (instead of the scripted tests above) there is a GUI on each side. **One direction at a time** (both radios use 915.0 MHz):

| direction | B210 side (GNU Radio) | P501 side |
|---|---|---|
| **A: B210 -> P501** | `qpsk_b210_tx.grc`: PRBS-15 DQPSK source, controls *Transmit* (OFF at start), *TX gain* (0 to 80 dB, default 80), *amplitude*; spectrum of what is sent | `P501_QPSK_Link_Live.ipynb`: *Start receiver* (`acquire()`), live constellation from the capture RAM, locked / not locked, bit errors and offsets from the FPGA counters, sliders for the loop bandwidths |
| **B: P501 -> B210** | `qpsk_b210_rx.grc`: the receiver chain of E.7 with a **PRBS-15 BER box**, constellation after the Costas loop, spectrum, sliders for *RX gain* and the loop bandwidth | the same notebook: checkbox *P501 transmits*, *TX attenuation* (20 to 89.75 dB), *amplitude* |

The flowgraphs are generated with GNU Radio Companion's own Python API by `make_flowgraph.py` (so every block has all its default parameters and the file is validated), and open in `gnuradio-companion` like any other `.grc`; `run_flowgraph_headless.py tx|rx` runs them without a screen. The notebook is generated by `p501_rx/make_notebook.py`
and tested by executing it on the board with `jupyter nbconvert --execute` (15 checks: the overlay, the loopback self-test, the live pictures, every control, and an experiment table against the real B210).

Three things went wrong on the way, and the flowgraphs contain the fixes:

1. **A receiver that runs on noise before the signal appears can stall the whole flowgraph.** The AGC (gain up to 200) turns the noise floor into a burst of tens of units when the signal starts, the polyphase clock sync runs away (it emits ten times too many symbols, with a constant output) and its work function stops the flowgraph. A hard limiter of +-1.5 on each component between the AGC and the FLL prevents it (late start, and signal dropout and return, both re-lock). The first version of the flowgraph looked fine in the first test because the transmitter was already on when the receiver started.
2. **A stuck bit stream passes the PRBS rule.** `a[n] = a[n-15] ^ a[n-14]` also holds for all zeros, so a runaway receiver showed a BER of 1e-41 in the first test. The BER block therefore reports 0.5 when the fraction of ones leaves 0.35 to 0.65, and the notebook's *locked* needs a sane constellation as well as zero new mismatches.
3. **One flowgraph with both the transmit and the receive chain** loads the host enough to underflow the transmit stream, and what the P501 then sees is degraded. Hence two flowgraphs.

And one hardware observation: **the B210 at 75 dB TX gain gave poor and irregular results through the air (several runs ended at 0 Hz carrier and 2 % errors), while 70 dB and 80 dB were fine**; the default is 80 dB (the highest value allowed so far).

## E.14 Test procedure: the flowgraphs and the notebook, step by step

What you need: the P501 with the overlay `p501_qpsk_trx` (copied to `/home/xilinx/jupyter_notebooks/p501_qpsk_trx/` together with `p501_qpsk.py` and `p501_qpsk_rx.py`) and the notebooks of `p501_fft_dds` (for `p501_radio.py`); the B210 on a USB 3 port; the PC with the radioconda environment;
antennas on TX1 and RX1 of the P501 and on the TX/RX and RX2 ports of the B210, **a few centimetres apart**. Very low power; check the rules where you are before radiating. **Only one direction at a time**: both radios use 915.0 MHz, and only one program can hold the B210.

<!-- FIGURE: the set-up: the two antenna pairs a few centimetres apart (photo) - tutorial/img/qpsk_setup_photo.png -->

**0. Prepare**

1. On the PC: `source tools/gnuradio_env.sh` (it puts `~/radioconda/bin` on the PATH and points UHD at the B210 images); `uhd_find_devices` must list the B210. Without sourcing the script, `gnuradio-companion` is not found.
2. In Jupyter on the board open `P501_QPSK_Link_Live.ipynb` and run the cells down to **Self-test** (the digital loopback). Every line must say PASS: the overlay, the AD9361 bring-up, the FPGA transmitter into the FPGA receiver inside the chip, the live pictures. Then run the **Controls** cell.

<!-- FIGURE: the notebook after the self-test (the PASS lines) and the Controls cell with the live picture in the loopback - tutorial/img/qpsk_nb_selftest.png -->

**Direction A: the B210 transmits, the P501's FPGA receiver decodes**

1. `gnuradio-companion tutorial/qpsk/gnuradio/qpsk_b210_tx.grc`, press the run button (the first time it asks to save the flowgraph). The controls: *Transmit* (starts **OFF**), *TX gain* (default 80 dB, maximum 80), *TX digital amplitude* (0.25); the plot shows the spectrum of what is sent.
2. Set *Transmit* to **ON** (TX gain 80). In the notebook leave *P501 transmits* and *Digital loopback* **unticked**, *RX gain* at 70, *Acquisition N* at 100, *Tracking M* at 400, *Search for the carrier* ticked.
3. Press **Start receiver**, then **Start display**. The status line says *locked after N try(ies), hint ... Hz*, taking about half a second to a second; the picture says **LOCKED** in green.

<!-- FIGURE: qpsk_b210_tx.grc running (Companion window with the controls and the spectrum) - tutorial/img/qpsk_grc_tx.png -->

What a good result looks like (numbers from our runs, B210 at 80 dB):

| item | good | what it tells you |
|---|---|---|
| constellation | four tight clusters, angular spread 7 to 11 degrees | the loops are locked and the SNR is good |
| carrier offset | +9.5 to +9.8 kHz, steady | the offset between the two radios (10.4 ppm of 915 MHz) |
| clock offset | about +10 ppm (instantaneous values jitter by tens of ppm) | the sample-clock offset, from the timing loop |
| mismatches per second | flat at 0 | no bit errors now (the counters keep the errors of the pull-in; **Start receiver** resets them) |
| AGC gain | about 5 to 10 | the signal level; **about 100 means nothing arrives** (the AGC has turned the noise floor up as far as it goes) |

<!-- FIGURE: the notebook locked on the B210: LOCKED, carrier +9.6 kHz, spread 7 degrees - tutorial/img/qpsk_nb_locked.png -->

4. Experiments while it is locked: slide **Live loop N** (50 to 1600). Wide loops (small N) are noisy, narrow loops (1600) average the phase noise: in our run the arcs of the clusters at N = 400 (spread 15 degrees, with a weaker signal) turned into round clusters at N = 1600 (7 degrees, with a stronger signal). Lower the B210 *TX gain* in steps (80, 75, 70, 65): the AGC gain rises, the spread grows, and below about 65 dB the receiver stops locking.
   Press **Start receiver** again after each big change of level: it re-runs the carrier search. The table in the **Experiment** cell shows why the search exists: cold starts with narrow loops end at 0 Hz carrier with about 2 % errors, `acquire()` locks every time.
5. **Stop** the flowgraph (window closed or the stop button); the transmitter is switched off with it.

**Direction B: the P501's FPGA transmitter, GNU Radio decodes**

1. Close `qpsk_b210_tx.grc` (only one program can hold the B210) and run `qpsk_b210_rx.grc`. Set *B210 RX gain* to about 45 and leave the loop bandwidth at 400.
2. In the notebook set **TX atten** to 40 dB, tick **P501 transmits (direction B)**, make sure *Digital loopback* is unticked, and lower the attenuation in steps (40, 35, 30 dB; 20 dB is the strongest the slider allows).
3. In the flowgraph window: the **BER box** reads 0.17 while the receiver is not locked, and falls to about 0 (a few 1e-5 at worst) when it locks; the constellation shows four clusters; the received spectrum shows the 1.3 MHz wide bump about 25 dB above the noise, with a narrow spike at the centre (the P501's LO leakage, harmless).
4. Untick **P501 transmits**: the BER box goes back to 0.17 within a second (and to 0.5 if the decoded stream is stuck).

<!-- FIGURE: qpsk_b210_rx.grc running while the P501 transmits (BER box, constellation, spectrum) - tutorial/img/qpsk_grc_rx.png -->

**If it does not lock**

| what you see | what to do |
|---|---|
| A: AGC gain about 100, random bits (BER estimate 0.17, mismatches at half the bit rate) | nothing arrives: *Transmit* is still OFF in the B210 window, the TX gain is low, the antennas are on the wrong ports (the transmitter uses TX/RX, the receiver RX2) or too far apart, or *Digital loopback* is ticked in the notebook |
| A: *NOT locked after 5 tries*, but the AGC gain is 5 to 10 | the carrier search did not find the offset: check that *Acquisition N* is 100 (a narrow acquisition only pulls in a few kHz), press **Start receiver** again; if it keeps failing, raise the B210 TX gain |
| A: locked, but the display says *NOT LOCKED* in red | the constellation is too noisy or errors continue: narrow *Live loop N*, raise the signal, or press **Start receiver** |
| A: the status line still says *NOT locked...* although the picture says LOCKED | the status line is only written when **Start receiver** is pressed; the picture is the truth |
| B: BER box at 0.17 and the spectrum bump is hardly above the noise | lower the P501 *TX atten*, raise the B210 *RX gain* |
| B: BER box at 0.5 | the decoded stream is stuck (all zeros or ones): there is no valid signal, or the P501 is not transmitting |
| the flowgraph does not start: *No devices found* | another program holds the B210 (the other flowgraph, a script), or the USB 3 link reset: close the other one, replug if needed |

<!-- FIGURE: the Experiment cell output table: cold starts failing, acquire() locking - tutorial/img/qpsk_nb_experiment.png -->

**6. Finish: always.** In the notebook run the last cell, **Stop and silence**: it stops the display, the receiver and the transmitter, switches the digital loopback off and sets the TX attenuation back to 89.75 dB. Close the flowgraph. Both ends are then quiet.

---

# Part F. Results, lessons, troubleshooting

## F.1 Results

| test | result |
|---|---|
| FPGA TX -> B210 / GNU Radio, TX attenuation 30 dB | no errors |
| FPGA TX -> FPGA RX, AD9361 digital loopback | 8 bit errors in the first 30 microseconds, then none in 7.7 million bits |
| FPGA TX -> FPGA RX over the air, 30 dB / 20 dB | 19 / 52 bit errors during pull-in (1.2 ms at most), then none in 9.6 million bits |
| B210 (TX gain 75 dB) -> FPGA RX, 2 pi/100 for 30 ms, then 2 pi/1600 | pull-in 0.6 to 48 ms, **no error in the following 11.5 million bits** (3 of 3 runs) |
| B210 (TX gain 80 dB) -> FPGA RX, 2 pi/100 for 30 ms, then 2 pi/400 or 2 pi/1600 | no error after the pull-in (5 of 5 runs); a cold start with 2 pi/400 locked in 1 of 2 runs |
| measured offsets (B210 -> P501) | carrier **+9.68 to +9.71 kHz**, clock **+9.9 to +10.8 ppm** (chapter 4.0: 9.5 kHz, 10.4 ppm) |
| B210 TX gain 70 / 65 / 60 dB | marginal (BER 2e-6 to 2e-2), poor (6e-4 to 6e-3), not locked |

![Constellations read from the FPGA's capture RAM](img/qpsk_rx_fpga_constellation.png)
![B210 at 75 dB and 80 dB](img/qpsk_rx_fpga_75_vs_80.png)

The extra 5 dB of B210 TX gain narrows the clusters from 10.5 to 8.1 degrees of angular spread (one capture each), in line with the expectation for a signal-to-noise gain of that size.

## F.2 What to try

* **Loop bandwidths:** `rx.set_loops(2*np.pi/d, 2*np.pi/d)` for d = 100, 200, 400, 800, 1600 while the link is up; watch `stats()` and the constellation. Wider = faster acquisition, more noise.
* **Acquisition:** cold start with 2 pi/1600 does not lock; give the receiver the offset with `init_freq_hz=9700` (register `W0`) and try again. How close must the guess be?
* **AGC:** change `REF` to 8192 (symbol magnitude 1.0) with the same loop bandwidths: the loops are four times slower (gain ~ amplitude squared).
* **Levels:** B210 TX gain 60, 65, 70, 75, 80 dB: how does the BER depend on the SNR? Compare with GNU Radio's receiver on a recording of the same level.
* **A preamble and CRC:** the PRBS checker needs no framing; a real link needs frame synchronisation: a correlator for a known word and a CRC (chapter 4e).

## F.3 Lessons from the hardware

1. **A floor in a loop integrator is a bias.** The rate integrator first read `rate += (TB*e) >> 21`. An arithmetic shift in two's complement rounds towards minus infinity: for a narrow loop (small `TB*e`) every update is 0 or -1,
   a drift of **-0.5 LSB per symbol** which the loop cannot balance. It ran the timing integrator into its limit (+-12,500 ppm) within 0.1 s for 2 pi/1600, and even with 2 pi/400 it shifted the reported clock offset to 16 ppm instead of 10.4.
   The bit-exact simulation matched the model perfectly - the model had the same bug. It was found by **sweeping the register-set bandwidths on the hardware**, and confirmed by running the NumPy integer model on a recording (rate 12,499 ppm with the floor, 10.4 ppm with rounding).
   The fix is one constant in the RTL and the model: `(TB*e + 2^20) >> 21`. *Bit-exact against a model proves agreement, not correctness: check the model against an independent measurement (here the two-tone result).*
2. **Pull-in is a different problem from tracking.** A Costas loop with a bandwidth of 0.4 % of the symbol rate (2 pi/1600) cannot pull in a 1 % offset; a wide loop can, but is noisy. Adjustable gains allow both: wide for 30 ms, then narrow.
3. **Gains scale with the square of the amplitude.** The AGC reference is part of the loop design.
4. **Count errors where the data are.** Bit errors counted inside the FPGA at 1.92 Mbit/s remove the question "is it the radio, or the DMA, or the software?".
5. **Start quiet, end quiet** - every script ends with the transmitter off and the TX attenuation at its maximum, even after an error.

## F.4 Troubleshooting

| symptom | likely cause |
|---|---|
| `TimeoutError: DDS update not taken over` | the AD9361 clock `l_clk` is not running: the bring-up did not run or failed (`ad.info["ok"]` is False) |
| `not the QPSK receiver (ID 0x...)` | the wrong overlay is loaded (the receiver is at `0x9C470000` in `p501_qpsk_trx` only) |
| `capture did not complete` | the receiver is not running (`rx.start()`), or `adc_valid` is not toggling |
| the receiver reads 0 Hz carrier and about 2 % errors | the Costas loop did not pull in the 9.7 kHz offset (cold start with narrow loops, or at the edge of the wide loop's range): press *Start receiver* again, or `rx.acquire()` |
| B210: `No devices found` | another program holds the B210 (a second test script, an old flowgraph), or the USB 3 port reset: run one test at a time |
| the BER estimate is about 0.17 and stays there (mismatches on every second bit) | not locked: the signal is too weak (look at `agc_gain`: above about 20 means weak), the offset is out of the loop's pull-in range, or the transmitter is not on |
| `carrier_offset_hz` = 0 and errors continue | the loops are too narrow for the offset (cold start with 2 pi/1600): acquire wide, or set `init_freq_hz` |
| `clock_offset_ppm` = +-12,500 | the timing integrator is at its limit (`MAXR`): the pre-fix RTL with a narrow loop, or no signal |
| `UU` on the host console | B210 underruns: the host cannot keep up; use a USB 3 port and the enlarged buffers |
| the B210 flowgraph's BER box shows 0.17 or 0.5 | 0.17: not locked (signal too weak or off, or the loops did not pull in); 0.5: the decoded stream is stuck (no valid signal) |
| `overruns` > 0 | the engine started more than 200 samples late: the engine clock is too slow or stalled |

## F.5 File index

| path | content |
|---|---|
| `rtl/qpsk_tx.v`, `rtl/qpsk_rrc_coef.v` | transmitter, generated coefficient ROM |
| `rtl/qpsk_rx.v`, `rtl/qpsk_rx_rom.v`, `rtl/qpsk_rx_trig.v` | receiver, generated ROMs |
| `rtl/dds_regs.v` | AXI-Lite register block with the commit hand-over (shared with the DDS) |
| `bd/qpsk_chain.tcl`, `bd/qpsk_rx_chain.tcl`, `tutorial/qpsk/p501_{tx,rx}/steps/*.tcl` | block-design integration |
| `src/dds_cdc.xdc`, `src/qpsk_rx_cdc.xdc` | clock-crossing constraints |
| `notebook/p501_radio.py`, `p501_dds.py`, `p501_qpsk.py`, `p501_qpsk_rx.py` | drivers |
| `tutorial/qpsk/p501_tx/`, `p501_rx/`, `p501_capture/`, `gnuradio/`, `link_up/` | per chapter: models, board and host scripts, simulation, README with the measured numbers |
| `tutorial/PLAN_QPSK.md` | the plan of the chapters 4.0 to 4e |
