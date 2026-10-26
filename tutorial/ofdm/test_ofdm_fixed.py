#!/usr/bin/env python3
"""The integer receiver against the float receiver on the same channel: python3 test_ofdm_fixed.py [sts]   (sts: the 128-sample STS frame and detector, results_ofdm_fixed_sts.txt)"""
import sys, time
import numpy as np
from multiprocessing import Pool
import ofdm_model as Fm, ofdm_fixed as X
LEAD = 300
STS = len(sys.argv) > 1 and sys.argv[1] == "sts"; V = X.STS if STS else X.SC
def one(a):
    snr, rms, seed, kw = a; rng = np.random.default_rng(seed)
    x, d = Fm.tx_frame(preamble=V["preamble"]); cfo = kw.get("cfo", rng.uniform(-20e3, 20e3)); tau = kw.get("tau", rng.uniform(0, 12))
    y = Fm.channel(x, snr, cfo_hz=cfo, tau=tau, ppm=kw.get("ppm", 10.0), rng=rng, lead=LEAD)
    rf = Fm.receive(y, return_all=True, sync=V["sync"], gsmooth=5); ef, sf = (Fm.metrics(rf["Z"], d) if rf else (np.nan, np.nan))
    xi, xq = X.to_adc(y, rms); ri = X.receive_fixed(xi, xq, var=V)
    if ri is None: return ef, sf, np.nan, np.nan, np.nan, np.nan, None
    sc = X.score(ri); return ef, sf, sc["evm"], sc["ser"], ri["s0"] - (LEAD + tau), ri["hz"] - cfo, ri["G"]
if __name__ == "__main__":
    pool = Pool(14); t0 = time.time()
    print("EVM / SER of the float and the integer receiver, 120 frames per point, carrier +-20 kHz, delay 0-12, 10 ppm; ADC level = rms counts of the signal at the input")
    print("Es/N0  ADC rms   float EVM  SER        int EVM   SER        int missed  start err mean/std   carrier err std   gain G")
    for snr, rms in ((16, 200), (20, 200), (24, 200), (28, 200), (24, 60), (24, 40), (24, 600), (24, 900)):
        res = pool.map(one, [(snr, rms, 100 + i, {}) for i in range(120)], chunksize=4); ok = [r for r in res if r[6] is not None]
        print("%4d   %5d     %6.1f dB  %.1e   %6.1f dB  %.1e    %3d       %+5.2f / %4.2f        %6.0f Hz        %s" % (snr, rms, np.nanmean([r[0] for r in res]), np.nanmean([r[1] for r in res]), np.mean([r[2] for r in ok]) if ok else 0, np.mean([r[3] for r in ok]) if ok else 1, len(res) - len(ok),
              np.mean([r[4] for r in ok]) if ok else 0, np.std([r[4] for r in ok]) if ok else 0, np.std([r[5] for r in ok]) if ok else 0, int(np.mean([r[6] for r in ok])) if ok else 0))
    print("\nfalse alarms on noise only (12-bit noise of 14 counts rms, 3840 samples, 2000 trials): ", end="")
    rng = np.random.default_rng(5); fa = fa2 = 0
    for i in range(2000):
        xi = np.round(rng.standard_normal(3840) * 14).astype(np.int64); xq = np.round(rng.standard_normal(3840) * 14).astype(np.int64)
        c, m, *_ = X.metric(xi, xq, V); fa += bool(c.any()); fa2 += X.receive_fixed(xi, xq, var=V) is not None
    print("detector alone %d, with the training-symbol check %d" % (fa, fa2))
    print("(%.0f s)" % (time.time() - t0))
