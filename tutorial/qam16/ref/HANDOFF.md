# Handoff: 16-QAM continuous stream with Zadoff-Chu frame sync (from the design session)

Context: existing P501 QPSK modem (TUTORIAL_QPSK.md, repo p501_fft_example): 960 ksym/s, 4 sps, RRC 0.35, AD9361, receiver engine at 100 MHz once per symbol
(4 shared multipliers, 16-arm polyphase timing loop, AGC, Costas loop; 53 DSP / 14.1k LUT). Goal: move to 16-QAM, continuous stream, ZC sync word per frame.

## Decisions made
- Continuous stream, one sync word per frame. Sync word = Zadoff-Chu, length 63, root 1, constant amplitude, with an 8-symbol cyclic prefix (last 8 symbols of the ZC).
- Frame = [CP 8 | ZC 63 | 14 x (63 x 16-QAM + 1 pilot)] = 967 symbols (1.007 ms at 960 ksym/s), 8.8 % overhead, 882 data symbols/frame.
  Pilots: known +-1 symbols, sequence [1,1,-1,1,-1,-1,1,1,1,-1,-1,1,-1,1]. 16-QAM unit average power, Gray levels {00:-3, 01:-1, 10:+3, 11:+1}/sqrt(10) per axis.
  Sync word at average payload power (or +2.6 dB if boosted; then freeze the AGC over it).
- Receiver chain: AGC (power-based, slow) -> mixer/NCO + band-edge FLL (coarse CFO) -> RRC matched + polyphase timing (1 sps) ->
  ZC correlator frame sync (SEARCH -> VERIFY at +967 -> LOCKED; initial phase, gain, frequency from the word) -> derotate + 2nd-order PLL
  (data-aided on pilots, decision-directed on data; frozen over CP + sync word) -> 16-QAM slicer. Sync peak missing for >3 frames -> back to SEARCH.
- Why ZC: constant amplitude, ideal periodic autocorrelation. Limit: CFO shifts the correlation peak in time (time/frequency ambiguity).
  Unambiguous only while |CFO| < Rs/(2N) = 7.6 kHz at 960 ksym/s (N=63). The FLL must leave less than that. (5G NR PSS uses an m-sequence for this reason.)
- d^4 estimator trick does not work for QAM; use m^4 or the sync word. costas_loop_cc in GNU Radio supports only orders 2/4/8, so the carrier PLL is custom.

## What was validated (Python/NumPy and GNU Radio 3.10.9.2 on Ubuntu 24.04, python3.12)
- gnuradio/rx_block.py (class FrameRx) is a floating-point golden model of the sync + PLL. Offline test (test_blocks.py, 250 ksym/s, sync block alone, no FLL):
  0 symbol errors at 40 dB/0 Hz, 30 dB/+-1.5 kHz, 25 dB/-1.5 kHz; SER ~1e-3 at 18 dB/800 Hz, ~2e-2 at 15 dB, ~0.12 at 12 dB.
  Fails (SER 0.93) at 2.4 kHz and 5 kHz offset, i.e. beyond Rs/(2N) = 1.98 kHz at 250 ksym/s, as expected.
- qam16_zc_loopback.grc (AGC -> FLL -> pfb_clock_sync -> sync block, 1 MS/s, noise 0.02, 1.5 kHz CFO, 10 ppm clock): 0 errors in ~2.8 M symbols, residual CFO ~tens of Hz, EVM ~-29 dB.
- Earlier sims in sims/: m-seq vs ZC peak vs CFO, frequency estimate vs CRLB, sidelobes in random 16-QAM (~3:1), CP gives zero sidelobes before the peak.
## NOT validated
Detection / false-alarm probability vs SNR with noise, timing and carrier loop lock times, multipath, equalizer, fixed-point effects, any FPGA resource figure.

## FPGA mapping suggestions (not implemented)
- ZC correlator: sliding 63-tap complex correlator on 1 sps; ZC phases are 126th roots of unity -> small ROM, or reuse the 4 shared multipliers over several cycles (data rate is 960 kHz vs 100 MHz clock, ~104 cycles per symbol).
  Normalise by running energy (rho = |corr| / sqrt(63 * sum|x|^2)); threshold 0.6 search / 0.45 lock.
- Frame counter after lock (967), correlate only in a +-4 window; gain = |sum(x conj(ZC))|/63; frequency from the word (FFT/tone estimate, or phase of two half-word correlations, cheaper than an FFT).
- Pilot/decision-directed PLL: reuse the existing Costas loop; replace the QPSK phase detector with Im(z conj(slicer(z))) for 16-QAM and add pilot weighting 3.0; loop_bw 0.02 normalised.
- Reuse the existing polyphase timing loop and AGC; AGC must be power-based for 16-QAM.

## Files
gnuradio/: tx/rx/loopback .grc, tx_block.py, rx_block.py (golden model), test_blocks.py, gen_grc.py (regenerates the .grc files, needs python3.12 + GNU Radio)
sims/: the earlier experiments; plots/: their PNGs.
Claude Doc (why NR uses an m-sequence): https://claude.ai/artifact/AFTy7VoHbznW5oS1dwqvzp
