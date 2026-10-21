# Chapter 4d, extension 2: the 4th-power frequency estimator in the FPGA (overlay `p501_qpsk_trx_fe`)

Status: **done**: integer model, RTL bit-exact in simulation, own overlay built (timing met), tested over the air against the B210 / GNU Radio and compared with the FLL and the Costas loop.

The overlay contains the receiver of `p501_qpsk_trx_fll` (FLL -> polyphase -> Costas) **plus** an open-loop estimator, so that all methods can be compared on the same signal by the same hardware.
Nothing of the earlier overlays is changed.

```
symbols m after the AGC, before the Costas loop (the engine's mi2, mq2), one per symbol, ~23 of the 104 clock cycles:
  d = m x conj(m_previous)              4 multipliers, round(>>15), clip +-16383
  (angle, |d|) = CORDIC vectoring of 8 d, 13 iterations (adds and shifts)
  psi = 4 x angle                        the DQPSK data steps (multiples of 90 degrees) become multiples of 360 degrees and vanish
  (c, s) = exp(j psi) from the 1024-entry sine/cosine table of the receiver
  window of N symbols:  ACC_RE += c,  ACC_IM += s,  ACC_ABS += |d|     (registers; N = FE_N, 1 .. 65535)
Python:  f = atan2(ACC_IM, ACC_RE) / (8 pi) x 960 kHz     (unambiguous for |f| < 120 kHz)      quality = |ACC| / (N x 32767)
```
Why the angle and not the plain 4th power `d^4`: the plain version weights each pair by `|d|^4` and the phase step depends on the amplitude on the real signal, which biased it by -15 % (`qpsk_fe_fixed.py`, `fe_study.py`);
with unit magnitude (the CORDIC angle) the bias is gone. The estimator sees the signal *after the FLL*: with the FLL loop off and `FLL_FREQ` = 0 it measures the whole offset, otherwise what is left;
the offset at the antenna is `f - FLL frequency`.

| file | what |
|---|---|
| `rtl/qpsk_fe.v` | the estimator (one pulse per symbol in, accumulators out) |
| `rtl/qpsk_rx_fe.v` | `qpsk_rx_fll.v` plus the estimator, ID `0xDD520003`; registers `0x74 FE_CTRL` (rising edge of bit 0 arms a window), `0x78 FE_N`, `0x7C FE_STATUS` (bit 0 active, bit 1 done), `0x80 FE_CNT`, `0x84 ACC_RE`, `0x88 ACC_IM`, `0x8C ACC_ABS` (saturates at 2^31-1), `0x90 FE_FIRST` (index of the first symbol of the window) |
| `tutorial/qpsk/p501_rx_fll/qpsk_fe_fixed.py` | the bit-exact integer model (and `fe_study.py`, the offline study) |
| `sim/tb_qpsk_rx_fe.v`, `sim/compare_fe.py` | RTL testbench (two windows) and the comparison with the model |
| `steps/`, `bd/qpsk_rx_fe_chain.tcl`, `QPSKRXFE=1` in `create_project.tcl` | the project; the clock-crossing constraints are those of the FLL receiver (`src/qpsk_rx_fll_cdc.xdc`) |
| `notebook/p501_qpsk_rx_fe.py` | driver `P501QpskRxFe`: `measure(n)`, `estimate_freq(n, windows)`, `acquire_fe(apply="fll"\|"w0")` (+ everything of the FLL driver) |
| `p501_fe_link.py`, `run_fe_test.py` | board side and host side of the over-the-air tests (`--what stats\|acquire\|settle`) |

## Verification

1. **RTL vs integer model** (xsim, the 60000-sample recording, windows of 1024 and 500 symbols): all accumulators (`ACC_RE`, `ACC_IM`, `ACC_ABS`, count, first index) **identical**, and the FLL stage and the 8 engine columns still match, in three configurations
   (FLL on, FLL held at 0 Hz, narrow FLL gain with F0 = -5 MHz). `overruns = 0`, `fll late = 0`.
2. **Build** (`... -tclargs FFT=0 QPSK=1 QPSKRXFE=1 RUN=bit`): WNS +0.417 ns, WHS +0.011 ns. 16248 LUTs, 8.5 BRAM tiles, 77 DSPs: the estimator costs 504 LUTs and 4 DSPs on top of the FLL receiver (the FLL costs 20 DSPs and 1650 LUTs).
   Files `build/overlay/p501_qpsk_trx_fe.{bit,hwh}`, board folder `/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fe/`.
3. **Hardware**, B210 at 915 MHz + offset, TX gain 80 dB, P501 RX gain index 70, DQPSK PRBS-15. The signal level of the B210 drifted during the day (AGC gain 7 to 10; estimator quality 0.82 in the good moments, 0.5 in the poor ones),
   so the numbers are grouped by it.

### Accuracy of one measurement (natural offset +9.5 kHz, quality 0.82, FLL held at 0)

Reference: the Costas loop's long-run mean, +9497 Hz. 20 windows each.

| N (symbols) | time | estimator mean - reference | estimator std |
|---|---|---|---|
| 128 | 0.13 ms | +36 Hz | 330 Hz |
| 256 | 0.27 ms | +68 Hz | 198 Hz |
| 512 | 0.53 ms | +52 Hz | 152 Hz |
| 1024 | 1.07 ms | +20 Hz | 117 Hz |
| 2048 | 2.1 ms | +31 Hz | 58 Hz |
| 4096 | 4.3 ms | +33 Hz | 58 Hz |
| 16384 | 17 ms | +11 Hz | 19 Hz |

The FLL's frequency (loop on, narrow gain 0.0003) scatters with a std of **1030 Hz** around its mean in the same conditions (instantaneous readings; 944 Hz in an earlier run): the estimator is about 10 times quieter at N = 1024 and 50 times at N = 2048.
At +79 kHz and a poor signal (quality 0.5) the std was 447 Hz at N = 1024, 344 Hz at 2048, 208 Hz at 16384, against 1.7 kHz for the FLL.
How long the receiver must run before the estimate is good (cold start, error against a 16384-symbol window, 10 trials): 500 symbols: 121 Hz rms, 1000: 69 Hz, 2000: 52 Hz, 4000: 31 Hz at +9.5 kHz; at +79 kHz 920 / 248 / 280 / 178 Hz.
So the driver waits 2000 symbols (2.1 ms) and then measures 1024 (1.1 ms).

### Range

Estimates against the Costas loop's total offset (same signal, good moments): +9.5 kHz: +9.53; -60.3 kHz: -60.3 (4 trials, within 0.3 kHz); +79.3 kHz: +79.3; -90.4 kHz: -90.4; **+109.6 kHz: +109.7**. The limit is +-120 kHz (1/8 of the symbol rate).

### Lock from cold, no hint (time of the last mismatch after the start, mismatch counter polled without a pause)

* `costas`: wide Costas loop (2 pi/100) only, FLL held at 0.   * `fll`: FLL (gain 0.002) + Costas.
* `fe-fll`: 2000 symbols settling (Costas held at 0 Hz), one window of 1024 symbols, the derotator loaded with minus the estimate, FLL loop off, then the Costas loop starts.   * `fe-w0`: the same, then a restart with W0 = the estimate.

Natural offset +9.7 kHz, 10 trials each (good signal):

| method | locked | lock time median (max) | total offset (Costas - FLL) mean, std of the one-shot values |
|---|---|---|---|
| costas | 10/10 | 0.5 ms (1.2) | +9481 Hz, 490 Hz |
| fll | 10/10 | 0.2 ms (1.5) | +9705 Hz, 1633 Hz |
| fe-fll | 10/10 | 3.5 ms (3.6) | +9706 Hz, **309 Hz** |
| fe-w0 | 10/10 | 3.6 ms (4.5) | +9450 Hz, 458 Hz |

Large offsets (earlier series with the good signal, 4 to 8 trials; the estimator then waited 6000 symbols, 8.5 ms):

| offset | costas | fll | fe-fll |
|---|---|---|---|
| +79.5 kHz | 4/4, 2 to 8 ms | 4/4, 0.2 to 0.4 ms | 4/4 |
| -60.3 kHz | 4/4, 0.7 to 1.8 ms | 4/4, 0.2 to 1 ms | 4/4 |
| +109.6 kHz | **5/8** (3 times it ended at -130 kHz, mirror of the true one) | 4/4, 0.3 to 1.1 ms | 8/8 |
| -90.4 kHz | 8/8 (1 slow: 279 ms) | 4/4, 0.4 to 0.8 ms | 7/8 |

(In the first series the first line of each run was lost in the log, merged with the console's underrun characters, so those rows count the trials that were logged: costas and fll at +79.5 and -60.3 kHz 3/3 logged, fe-fll 3/3 and the rest as shown.)

Findings that changed the design:

* **Hold the Costas loop during the measurement.** In the first version the Costas loop ran (CA = CB = 0 was not set); it pulled in to the offset by itself during the settling, and the derotator load, which removes the same offset, then left it pulling the wrong way:
  fe-fll failed 2 of 16 at +-90..110 kHz. Writing CA = CB = 0 until the load (`acquire_fe`) fixed it (15 of 16 at these offsets, the failure being a 0.3 s window that ended just before the lock).
* The FLL needs no such care and is the fastest (0.2 to 1 ms); the estimator route is a fixed 3.5 ms (settling + window + load) and does not depend on the offset up to 110 kHz.
* In a later series the B210 signal was poor (AGC gain 10, estimator quality 0.5): at +79.6 kHz 4/10 (costas), 7/10 (fll), 7/10 (fe-fll), 3/10 (fe-w0) locked, at -90.5 kHz 0/10, 2/10, 2/10, 1/10. A receiver that cannot lock for lack of signal says little
  about the methods; those numbers are not in the tables above.

## What the comparison says

| | Costas alone | FLL (band-edge) | 4th-power estimator |
|---|---|---|---|
| range | pull-in grows slowly with the offset, failures at 110 kHz | verified to 110 kHz | +-115 kHz verified, +-120 kHz by design |
| time to lock | 0.5 ms at 9.7 kHz, several ms at 80 kHz | 0.2 to 1 ms | 3.5 ms (2000 symbols settling + 1024 window) |
| noise of the frequency | follows the data | **~1 kHz** std, always | 117 Hz (N = 1024), 58 Hz (2048), 19 Hz (16384): shrinks with the window |
| bias against the Costas total | - | -3.7 kHz alone on the P501 path (RX passband tilt; the Costas loop takes it up) | +10 to +70 Hz |
| closed loop | yes | yes (tracks drift, follows the tilt of a fading channel) | no: one measurement per request |
| cost | in the engine | 20 DSPs, 1650 LUTs | 4 DSPs, 504 LUTs |

Use both: the FLL for the fast first lock and for tracking a drifting offset; the estimator when a precise value is wanted (set the derotator once with it, freeze the FLL, and the Costas loop has almost nothing left to do:
Costas std 0.3 kHz in the frozen runs of the FLL notebook, the residual after `fe-fll` was +-200 Hz).
**Not tested here:** whether the estimator-then-freeze receiver survives the movement near the antennas that unlocked the FLL (the multipath tilt moves the FLL's band-edge balance; the estimator has no such bias in principle, because it measures phase steps, but it is a hypothesis until measured).

## Run it

```
# board folder (once): bit, hwh, p501_qpsk.py, p501_qpsk_rx.py, p501_qpsk_rx_fll.py, p501_qpsk_rx_fe.py -> /home/xilinx/jupyter_notebooks/p501_qpsk_trx_fe/ ; p501_fe_link.py -> /tmp/
source tools/gnuradio_env.sh
python3 tutorial/qpsk/p501_rx_fe/run_fe_test.py --out /tmp/p501_fe_run --tx-gain 80 --what stats                     # accuracy against N, FLL scatter
python3 tutorial/qpsk/p501_rx_fe/run_fe_test.py --out /tmp/p501_fe_run --tx-gain 80 --what acquire --trials 10 --freq 915.07e6   # lock from cold at +80 kHz extra offset
python3 tutorial/qpsk/p501_rx_fe/run_fe_test.py --out /tmp/p501_fe_run --tx-gain 80 --what settle --trials 10     # settling time before the estimate is good
```
Simulation: `cd tutorial/qpsk/p501_rx_fe/sim`; `xvlog -sv ../../../../rtl/{qpsk_rx_fe,qpsk_fe,qpsk_fll,qpsk_fll_taps,qpsk_rx_rom,qpsk_rx_trig,qpsk_rrc_coef}.v tb_qpsk_rx_fe.v; xelab -debug off tb -s simfe; xsim simfe -runall [-testplusarg fllc=0]`,
then `python3 compare_fe.py [GI GP F0 FLLC]` (the same values as the plusargs).
