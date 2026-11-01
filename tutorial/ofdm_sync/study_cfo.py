#!/usr/bin/env python3
"""E1 and E2 of PLAN_OFDM_SYNC.md.
E1: how accurate is each fine-carrier method (rms error of the final carrier, Hz) against the SNR, for a long field of L = 1, 2, 4, 8 symbols after the 128-sample STS?
E2: how accurate must it be? EVM and symbol error rate when the receiver is given the true carrier plus a fixed error (0 .. 6 kHz).
    python3 study_cfo.py [frames per point, default 200] | tee results_cfo.txt"""
import sys
import numpy as np
from ofdm_sync_lab import Cfg, run, summary

NFR = int(sys.argv[1]) if len(sys.argv) > 1 else 200
SNRS = (23, 18, 14, 10)
print("E1: rms error of the carrier estimate (Hz); carrier offset uniform in +-30 kHz, random fractional delay, AWGN at the given SNR per subcarrier; %d frames per point" % NFR)
print("    theory for the two-symbol estimate (lag 64, 64 products): sigma_f = sqrt(1 / (64 SNR_t)) / (2 pi 64 / fs), SNR_t = 0.4375 / noise variance per sample")
print()
methods = [("coarse only (STS lag 16)", []), ("short_multi (lags 16 .. 112, no long field)", ["short_multi"]), ("orig: lag 64, T1 and T2", ["orig"]), ("lag1: lag 64, whole long field", ["lag1"]),
           ("multi: lags 64 .. L x 64", ["multi"]), ("short_multi, then multi", ["short_multi", "multi"])]
for L in (1, 2, 4, 8):
    cfg = Cfg("sts", 128, L)
    print("long field L = %d (frame preamble %d samples, overhead %.1f %%)" % (L, cfg.preamble, 100 * cfg.overhead))
    print("  %-46s" % "method" + "".join("%9s" % ("%d dB" % s) for s in SNRS))
    for name, fine in methods:
        if L < 2 and ("orig" in fine or "multi" in fine): continue
        row = []
        for s in SNRS:
            o = run(cfg, s, NFR, fine=fine, rng=np.random.default_rng(10 + s)); S = summary(o)
            row.append("%9.0f" % S["f_rms"] if S.get("found", 0) > 0.9 else "%9s" % "lost")
        print("  %-46s" % name + "".join(row))
    th = []
    for s in SNRS:
        snr_t = 0.4375 / 10 ** (-s / 10); th.append("%9.0f" % (np.sqrt(1 / (64 * snr_t)) / (2 * np.pi * 64 / 3.84e6)))
    print("  %-46s" % "theory, orig" + "".join(th)); print()

print("E2: what a carrier error costs. Frame A (STS 128, L = 2); the receiver is given the true carrier + the error (no estimate of its own); EVM (dB) and symbol error rate, mean over %d frames" % NFR)
print("    inter-carrier interference of an error df: (pi df / 60 kHz)^2 / 3, i.e. -41 dB at 290 Hz, -29 dB at 1 kHz, -19 dB at 3 kHz")
for s in (23, 18, 14):
    print("  SNR %d dB:" % s)
    print("   %9s %10s %10s" % ("error Hz", "EVM dB", "SER"))
    for ferr in (0, 100, 300, 1000, 3000, 6000):
        o = run(Cfg("sts", 128, 2), s, NFR, fine=[], ferr=float(ferr), rng=np.random.default_rng(100 + s)); S = summary(o)
        print("   %9d %10.2f %10.1e   (frames lost %.0f %%)" % (ferr, S["evm"], S["ser"], 100 * S["bad"]))

print()
print("E1b: the carrier left after the fine estimate, measured by the PILOTS: the slope of the phase of the pilot gain over the 44 data symbols (a baseline of 3520 samples, no extra sequence).")
print("     Frame A, fine = orig; rms error (Hz) of the pilot estimate of the residual (true carrier - the receiver's carrier) and of the receiver's own carrier before it")
print("     theory: phase noise of one symbol's gain, 4 pilots: var = noise / 8; slope of a line through 44 points; sigma_f = sigma_slope / (2 pi 80 / fs)")
print("   %8s %20s %20s %10s" % ("SNR dB", "own estimate (Hz)", "pilot estimate (Hz)", "theory"))
for s in (23, 18, 14, 10):
    o = run(Cfg("sts", 128, 2), s, NFR, fine=["orig"], rng=np.random.default_rng(200 + s)); S = summary(o)
    pe = o["f_pilot"] + o["f_err"]                       # pilot estimate of (true - used) = -f_err: the error of the pilot estimate is f_pilot - (-f_err)
    sig = 10 ** (-s / 10); sp = np.sqrt(sig / 8); n = 44; sl = sp * np.sqrt(12 / (n * (n * n - 1))); th = sl / (2 * np.pi * 80 / 3.84e6)
    print("   %8d %20.0f %20.1f %10.1f" % (s, S["f_rms"], np.sqrt(np.mean(pe ** 2)), th))
print("     a carrier measured to a few Hz per frame, and the frame-to-frame average of it, is far more accurate than any preamble; it can only be used for the NEXT frame (the data have gone by),")
print("     which is fine because the carrier of two oscillators does not move in a millisecond.")
