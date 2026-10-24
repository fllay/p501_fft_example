#!/usr/bin/env python3
"""The delay-and-correlate detector of PLAN_OFDM.md (STS with period 16, 128 samples) against Schmidl and Cox (one 80-sample symbol with two identical halves, lag 32), same channel, same receiver after the detection.
python3 ofdm_sync_compare.py -> results_sync_compare.txt"""
import time
import numpy as np
from multiprocessing import Pool
import ofdm_model as M
LEAD = 300
METHODS = [("sts16 (ours)", "sts16", "sts16"), ("S&C, plateau", "sc", "sc_plateau"), ("S&C, argmax", "sc", "sc_argmax")]
out = []
def P(s=""): out.append(s); print(s, flush=True)


def trial(a):
    pre, sync, snr, seed, kw = a; rng = np.random.default_rng(seed)
    x, d = M.tx_frame(preamble=pre)
    cfo = kw.get("cfo", rng.uniform(-20e3, 20e3)); tau = kw.get("tau", rng.uniform(0, 12))
    y = M.channel(x, snr, cfo_hz=cfo, tau=tau, ppm=10.0, taps=kw.get("taps"), rng=rng, lead=LEAD)
    r = M.receive(y, return_all=True, sync=sync, gsmooth=5)
    # first threshold crossing relative to the preamble start (the latency of the decision)
    if sync == "sts16": m, _ = M.timing_metric(y, 16, 48)
    else: m, _ = M.timing_metric(y, 32, 32)
    cross = np.nonzero(m > 0.5)[0]; lat = (cross[0] + 64 - (LEAD + tau)) if len(cross) else np.nan                       # the window of 64 samples (48 + 16 or 32 + 32) must have arrived
    if r is None: return None
    evm, ser = M.metrics(r["Z"], d)
    return r["s0"] - (LEAD + tau), r["f"] - cfo, evm, ser, lat


if __name__ == "__main__":
    pool = Pool(14); t0 = time.time(); nt = 500
    P("Detection compared: our delay-and-correlate on the 128-sample STS (lag 16, 48 products) against Schmidl and Cox (one 80-sample symbol, lag 32, 32 products), %d trials per point, carrier +-20 kHz, delay 0 to 12 samples, 10 ppm, the same LTS, receiver and pilots after the detection" % nt)
    P("The FFT window tolerates a start error between -10 and +6 samples (CP 16, BACK 6): 'outside' = the fraction of the frames beyond that.\n")
    P("== T1: against the SNR per subcarrier")
    P("Es/N0  method          detected  start error mean / std   outside   carrier err std   EVM       SER         first crossing seen after (samples from the preamble start)")
    for snr in (6, 10, 14, 18, 22, 26):
        for name, pre, sync in METHODS:
            res = pool.map(trial, [(pre, sync, snr, 100 + i, {}) for i in range(nt)], chunksize=4); ok = [r for r in res if r]
            te = np.array([r[0] for r in ok]); outside = np.mean((te < -10) | (te > 6)) if len(te) else 1
            P("%4d   %-14s %6.1f %%   %+6.2f / %5.2f          %5.1f %%    %6.0f Hz        %6.1f dB  %.1e   %6.1f" % (snr, name, 100 * len(ok) / nt, te.mean() if len(te) else 0, te.std() if len(te) else 0, 100 * outside, np.std([r[1] for r in ok]) if ok else 0, np.mean([r[2] for r in ok]) if ok else 0, np.mean([r[3] for r in ok]) if ok else 1, np.nanmean([r[4] for r in ok]) if ok else 0))
        P()
    P("== T2: false alarms on noise only (3000 frames of 3840 samples)")
    rng = np.random.default_rng(5)
    for name, pre, sync in METHODS:
        row = []
        for thr in (0.3, 0.4, 0.5, 0.6, 0.7):
            fa = 0
            for i in range(3000):
                y = np.sqrt(0.5 * 10 ** (-20 / 10)) * (rng.standard_normal(3840) + 1j * rng.standard_normal(3840))
                fa += (M.detect(y, thr) if sync == "sts16" else M.detect_sc(y, thr, "plateau")) is not None
            row.append(fa)
        P("   %-14s threshold 0.3: %d   0.4: %d   0.5: %d   0.6: %d   0.7: %d" % (name, *row))
    P("\n== T3: carrier offset range (Es/N0 22 dB, 150 trials each; found / EVM)")
    P("offset    " + "".join("%-30s" % n for n, _, _ in METHODS))
    for cfo in (0, 20e3, 40e3, 55e3, 65e3, 90e3, 115e3):
        row = []
        for name, pre, sync in METHODS:
            res = pool.map(trial, [(pre, sync, 22, 700 + i, dict(cfo=float(cfo), tau=4.3)) for i in range(150)], chunksize=4); ok = [r for r in res if r]
            row.append("%3d of 150, %s" % (len(ok), ("%.1f dB" % np.mean([r[2] for r in ok])) if ok else "-"))
        P("%+7.0f   " % cfo + "".join("%-30s" % c for c in row))
    P("\n== T4: an echo (second tap) at 8 samples: the detector's timing bias and the EVM (Es/N0 22 dB, 150 trials)")
    for amp in (0.0, 0.5, 0.7):
        taps = np.zeros(9, complex); taps[0] = 1.0; taps[8] = amp * np.exp(1j * 1.0)
        for name, pre, sync in METHODS:
            res = pool.map(trial, [(pre, sync, 22, 1100 + i, dict(taps=taps, cfo=9700.0)) for i in range(150)], chunksize=4); ok = [r for r in res if r]; te = np.array([r[0] for r in ok])
            P("   echo %.1f  %-14s start error %+6.2f / %5.2f   outside %5.1f %%   EVM %6.1f dB  SER %.1e" % (amp, name, te.mean(), te.std(), 100 * np.mean((te < -10) | (te > 6)), np.mean([r[2] for r in ok]), np.mean([r[3] for r in ok])))
    P("\n== T5: detection probability against the threshold at 14 dB and 18 dB (500 trials): the price of a threshold high enough for the false-alarm rate")
    for snr in (14, 18):
        for name, pre, sync in METHODS[:2]:
            row = []
            for thr in (0.5, 0.6, 0.7):
                n_ok = 0
                for i in range(300):
                    rng = np.random.default_rng(3000 + i); x, d = M.tx_frame(preamble=pre); y = M.channel(x, snr, cfo_hz=rng.uniform(-20e3, 20e3), tau=rng.uniform(0, 12), rng=rng, lead=LEAD)
                    dd = M.detect(y, thr) if sync == "sts16" else M.detect_sc(y, thr, "plateau"); n_ok += dd is not None
                row.append(100 * n_ok / 300)
            P("   %2d dB  %-14s thr 0.5: %5.1f %%   0.6: %5.1f %%   0.7: %5.1f %%" % (snr, name, *row))
    P("\n(%.0f s)" % (time.time() - t0))
    open("results_sync_compare.txt", "w").write("\n".join(out) + "\n")
