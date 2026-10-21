# Chapter 4d, extension 3: polyphase -> 4th power -> Costas, with no software in the loop (overlay `p501_qpsk_trx_4p`)

Status: **done and tested** (chain 3 of the three-way comparison; chains 1 and 2 are the overlays `p501_qpsk_trx` and `p501_qpsk_trx_fll`, each its own project). Integer model, RTL bit-exact in simulation, own overlay built (timing met), tested over the air against the B210 / GNU Radio.
The comparison of the three chains is **not** done here; this README only checks that chain 3 works and how well.

```
ADC -> polyphase matched filter + timing loop + AGC -> m (one symbol every 104 clock cycles) -> Costas loop -> bits -> PRBS-15 checker
                                                         |                                  ^
                                                         +-> 4th-power estimator: d = m conj(m_prev), CORDIC angle, x4, sine table, sum over N symbols
                                                             -> atan2 by a CORDIC -> w = turns per symbol x 2^32 -> gate (quality >= q_min) -> LOADS the Costas frequency OMEGA at the next symbol
```
The FPGA does everything: Python only writes `FE_AUTO` (enable) and reads counters. There is no FLL in this overlay (it is the receiver of chapter 4d, `qpsk_rx.v`, plus the estimator).

| file | what |
|---|---|
| `rtl/qpsk_fe.v` | the accumulators of the estimator (shared with the overlay `p501_qpsk_trx_fe`) |
| `rtl/qpsk_fe_auto.v` | the controller: arms the windows itself, atan2 CORDIC (18 iterations, angle in turns x 2^20), gate, load request |
| `rtl/qpsk_rx_4p.v` | `qpsk_rx.v` + estimator; ID `0xDD520004`; at the S7 state of the symbol after a window the Costas frequency is replaced by the estimate instead of the integrator update |
| `qpsk_fe_auto_fixed.py` | bit-exact integer model (`auto_sequence`: the windows, estimates, gate and load positions); `qpsk_rx_fixed.receive_fixed(..., omega_loads=...)` applies the loads |
| `sim/tb_qpsk_rx_4p.v`, `sim/compare_4p.py` | RTL testbench (auto mode, N, q_min as plusargs) and the comparison with the model |
| `steps/`, `bd/qpsk_rx_4p_chain.tcl`, `QPSKRX4P=1` in `create_project.tcl` | the project (the clock-crossing constraints of `src/qpsk_rx_cdc.xdc`) |
| `notebook/p501_qpsk_rx_4p.py` | driver `P501QpskRx4p`: `acquire_4p()`, `set_auto()`, `enable_auto(continuous)`, `auto_status()`, `measure(n)` (a manual window), `timed_lock(mode)` |
| `p501_4p_link.py`, `run_4p_test.py` | board side and host side of the tests (`--what acquire\|stats\|sweep\|both`) |

Registers (added to those of the receiver): `0x74 FE_CTRL` (rising edge of bit 0 arms ONE manual window), `0x78 FE_N` (window, symbols, 1..65535, default 1024), `0x7C FE_STATUS`, `0x80 FE_CNT`, `0x84 ACC_RE`, `0x88 ACC_IM`, `0x8C ACC_ABS`, `0x90 FE_FIRST`,
`0x94 FE_AUTO` (bit 0 enable, bit 1 continuous; write 0 then 1/3), `0x98 FE_WEST` (last frequency loaded), `0x9C FE_NLOAD`, `0xA0 FE_QMIN` (gate, `q_min x 32767 x 1.6468`, default 16000 = 0.30), `0xA4 FE_NWIN`, `0xA8 FE_WLAST` (last window's frequency, gate or not).
**Modes.** Once (`FE_AUTO` = 1): windows follow each other from the first symbol after the enable until one passes the gate; that one loads OMEGA, then the Costas loop tracks alone. Continuous (3): every window that passes loads OMEGA.

## Verification

1. **RTL vs integer model** (xsim, the 60000-sample recording; all windows, all loads and the 8 engine columns of all 14990 symbols): **0 mismatches** in four configurations: continuous N = 1024 (11 windows, 11 loads), once (1 window, 1 load),
   once with a strict gate (3 windows, only the third loads: the retry works), continuous N = 256 (46 windows). `overruns = 0`. The atan2 CORDIC is within 1.1 Hz of numpy.
2. **Build** (`... -tclargs FFT=0 QPSK=1 QPSKRX4P=1 RUN=bit`): WNS +0.417 ns, WHS +0.012 ns. 15297 LUTs, 7.5 BRAM tiles, 59 DSPs (the receiver without the estimator: 14097 LUTs, 6.5 BRAM, 53 DSPs: the estimator with its CORDICs costs 1200 LUTs, 1 BRAM, 6 DSPs).
   Files `build/overlay/p501_qpsk_trx_4p.{bit,hwh}`, board folder `/home/xilinx/jupyter_notebooks/p501_qpsk_trx_4p/`.
3. **Hardware**, B210 at 915 MHz + offset, TX gain 80 dB (83 dB for the first run: the transmit flowgraph saved from Companion was running), P501 RX gain index 70, DQPSK PRBS-15, P501 at 915.0 MHz. Natural offset +9.5 kHz.

### Natural offset (+9.5 kHz), strong signal (AGC gain 7.6, estimator quality 0.94)

The estimator loaded the right value without any hint. Autonomous, cold start (wide loops 2 pi/100, estimator enabled after 2000 symbols), loaded value against the Costas loop's mean +9489 Hz:

| window N | loaded value, 10 cold starts | |
|---|---|---|
| 256 | mean +9240 Hz, std 378 Hz (min +8210, max +9608) | 0.27 ms |
| 1024 | mean +9338 Hz, std 150 Hz (min +9022, max +9481) | 1.1 ms |
| 4096 | mean +9431 Hz, std 29 Hz (min +9393, max +9479) | 4.3 ms |

Manual windows on the settled receiver (20 each, same signal): std 127 Hz at N = 128, 54 Hz at 1024, 18 Hz at 2048, 13 Hz at 16384; bias -13 to -56 Hz.
In a later hour with a weaker signal (spread 11 degrees) the same cold starts gave an rms error of 160 to 360 Hz at N = 1024 whatever the settling (1000 to 12000 symbols) and timing-loop bandwidth.

Lock from a cold start (10 trials, mismatch counter polled without a pause; lock = no new mismatch for 50 ms and a sane constellation):

| | locked | lock time median (max) |
|---|---|---|
| Costas loop alone (reference) | 8/9 | 0.8 ms (94) |
| autonomous, once | 10/10 | 0.3 ms (262, one slow start) |
| autonomous, continuous | 10/10 | 0.4 ms (287, one slow start) |

At this offset all three lock at once (the 9.5 kHz is inside the pull-in of the wide Costas loop), so the lock time does not separate them. Steady state, 2 s after the lock with the loops narrowed to 2 pi/400 (strong signal run):
no new mismatch in 3.86 Mbit for all three, Costas std 185 Hz, constellation spread 7.9 degrees for all three, `overruns` 0, one load (once) or 2436 loads in 2 s (continuous).

### Large offsets (weaker signal, AGC gain 10 to 11, spread 11 to 13 degrees)

The strict lock test (no mismatch for 50 ms) failed for every method at +-80..90 kHz because the signal itself was marginal (bit error rate around 1e-4 even when locked), so these rows use the steady-state measurement (2 s after the lock, loops 2 pi/400):

| offset | chain | Costas frequency | mismatches in 3.85 Mbit | spread | Costas std |
|---|---|---|---|---|---|
| +79.5 kHz | Costas alone | +79496 Hz | 284 | 13.3 deg | 132 Hz |
| | autonomous, once | +79498 Hz | 210 | 12.9 deg | 130 Hz |
| | autonomous, continuous | +79345 Hz | **9659** | 13.4 deg | **803 Hz** |
| -90.5 kHz | Costas alone | **+1 Hz: did not pull in** | 1.79 M | 20.4 deg | 178 Hz |
| | autonomous, once | -90496 Hz | 64 | 11.8 deg | 98 Hz |
| | autonomous, continuous | -90250 Hz | 1054 | 12.4 deg | 806 Hz |

* **Once locks where the Costas loop alone does not** (-90 kHz); at +80 kHz it is as good as the Costas loop. The loaded value is a few hundred Hz to 1 kHz off at the first window (rms 700 to 1000 Hz at +78 kHz, N = 1024, wide timing loop; 1.2 to 2.3 kHz with the narrow timing loop and short settling),
  which the wide Costas loop removes in a few milliseconds. Settling longer than 2000 symbols did not help noticeably; the wide timing loop (2 pi/100) was better than the narrow one at this offset.
* **Continuous is worse at large offsets**: every window loads a value that is 1 to 3 kHz low at +-80..90 kHz (the 4th-power estimate is biased by the same effect as the plain version, here about 1 to 3 % of the offset, probably because the P501 receive filter and the matched filter distort the signal more
  the further it is from the band centre), and these loads fight the Costas loop (std 800 Hz, 10 to 40 times the errors). At +-10 kHz the bias is below 100 Hz and continuous is as good as once.
  Use **once** for acquisition; continuous only for small offsets.
* The reference truth moved during the afternoon (the Costas frequency +79.5 kHz in one run, the estimator's long windows 76.5 to 78.8 kHz later): the two radios' references drift by about 1 ppm at warm-up; compare methods back to back.

## Problems found on the way

* A stray load: 1 of 60 reference runs "Costas alone" right after a continuous run still had loads (46 in 48 ms) although `FE_AUTO` read 0. Writing `FE_AUTO` = 0 *before* `stop()` as well (`disable_auto()` in `timed_lock` / `acquire_4p`) removed it: 0 in 120 runs. The cause was not found in the RTL (the registers and the FSM reset with `run`); it looks like an ordering effect of the stop / configure / start sequence, so the driver is defensive.
* The first board run used the transmit flowgraph that was already running (83 dB); later runs used `run_4p_test.py` at 80 dB.

## Run it

```
# board folder (once): bit, hwh, p501_qpsk.py, p501_qpsk_rx.py, p501_qpsk_rx_4p.py -> /home/xilinx/jupyter_notebooks/p501_qpsk_trx_4p/ ; p501_4p_link.py -> /tmp/
source tools/gnuradio_env.sh
python3 tutorial/qpsk/p501_rx_4p/run_4p_test.py --out /tmp/p501_4p_run --tx-gain 80 --what acquire --trials 10 [--freq 915.07e6]
python3 tutorial/qpsk/p501_rx_4p/run_4p_test.py --out /tmp/p501_4p_run --tx-gain 80 --what stats
python3 tutorial/qpsk/p501_rx_4p/run_4p_test.py --out /tmp/p501_4p_run --tx-gain 80 --what sweep --trials 10     # first estimate against settling time and timing-loop bandwidth
```
Simulation: `cd tutorial/qpsk/p501_rx_4p/sim`; `xvlog -sv ../../../../rtl/{qpsk_rx_4p,qpsk_fe_auto,qpsk_fe,qpsk_rx_rom,qpsk_rx_trig,qpsk_rrc_coef}.v tb_qpsk_rx_4p.v; xelab -debug off tb -s sim4p; xsim sim4p -runall [-testplusarg auto=1 -testplusarg n=256 -testplusarg qmin=30500]`,
then `python3 compare_4p.py N QMIN AUTO` (the same values).
