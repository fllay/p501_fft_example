#!/usr/bin/env python3
"""Vectors for ofdm_chan.v (with ofdm_fft.v): chan_in.hex (per case 128 samples: T1 then T2 windows after the gain and derotation, {im, re}) and chan_exp.txt (28 lines 'Hr Hi Wr Wi', then the noise sum) from ofdm_fixed.receive_fixed."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ofdm_model as Fm, ofdm_fixed as X
cases = []
def echo(amp, delay, ph): t = np.zeros(delay + 1, complex); t[0] = 1.0; t[delay] = amp * np.exp(1j * ph); return t
i = 0
for snr in (12, 16, 20, 24, 28, 34):
    for rms in (50, 200, 900):
        for taps in (None, echo(0.5, 5, 1.0), echo(0.95, 8, 2.0), echo(0.99, 3, 0.3)):
            rng = np.random.default_rng(1000 + i); i += 1
            x, d = Fm.tx_frame(preamble="scu"); y = Fm.channel(x, snr, cfo_hz=rng.uniform(-20e3, 20e3), tau=rng.uniform(0, 12), taps=taps, rng=rng, lead=300)
            xi, xq = X.to_adc(y, rms); r = X.receive_fixed(xi, xq, check=False)
            if r is None: continue
            cases.append((r["T1"], r["T2"], r["H"], r["W"], r["noise"]))
z = np.zeros(64, dtype=np.int64); cases.append(((z, z), (z, z), None, None, None))                                       # all zero: H = 0, W = 0
rng = np.random.default_rng(5); t = tuple(rng.integers(-1, 2, 64) for _ in range(2)); t2 = tuple(rng.integers(-1, 2, 64) for _ in range(2)); cases.append((t, t2, None, None, None))      # tiny signals: huge weights
lines, exp = [], []
for t1, t2, H, W, nz in cases:
    for (xr, xi) in (t1, t2):
        lines += ["%08x" % (((int(b) & 0xFFFF) << 16) | (int(a) & 0xFFFF)) for a, b in zip(xr, xi)]
    if H is None:                                                                                                          # the model on the raw windows
        Ar, Ai = X.fft64(*t1); Br, Bi = X.fft64(*t2); kb = X.KB; sr_, si_ = Ar[kb] + Br[kb], Ai[kb] + Bi[kb]
        u = X.TR_S[0] * sr_ + X.TR_S[1] * si_; v = X.TR_S[0] * si_ - X.TR_S[1] * sr_
        Hr = (((u * X.SQ2 + 128) >> 8) + 1) >> 1; Hi = (((v * X.SQ2 + 128) >> 8) + 1) >> 1; nz = int(((Ar[kb] - Br[kb]) ** 2 + (Ai[kb] - Bi[kb]) ** 2).sum()); H = (Hr, Hi)
        K = X.R << 14; Wr = np.zeros(28, dtype=np.int64); Wi = np.zeros(28, dtype=np.int64)
        for j in range(28):
            den = int(Hr[j]) ** 2 + int(Hi[j]) ** 2
            if den: Wr[j] = X.rdiv(int(Hr[j]) * K, den); Wi[j] = X.rdiv(-int(Hi[j]) * K, den)
        W = (Wr, Wi)
    exp += ["%d %d %d %d" % (H[0][j], H[1][j], W[0][j], W[1][j]) for j in range(28)] + ["%d" % nz]
open("chan_in.hex", "w").write("\n".join(lines) + "\n"); open("chan_exp.txt", "w").write("\n".join(exp) + "\n"); print("%d cases" % len(cases))
