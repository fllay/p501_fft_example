# Chapter 4d: the QPSK receiver in the FPGA (adjustable loops)

Status: **stage 1 of 4 done** (the reference receivers, below); the RTL, the integration and the live tests follow.

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
