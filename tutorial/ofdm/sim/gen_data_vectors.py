#!/usr/bin/env python3
"""Vectors for ofdm_data.v (with ofdm_fft.v in front): per case the weights W (28 x 'Wr Wi'), the 44 derotated data windows (64 samples each, {im, re}) and the expected outputs:
the corrected data symbols (44 x 24 'Zr Zi'), the PRBS checker counts and the EVM sums, from ofdm_fixed.receive_fixed.   python3 gen_data_vectors.py"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ofdm_model as Fm, ofdm_fixed as X
def echo(amp, delay, ph): t = np.zeros(delay + 1, complex); t[0] = 1.0; t[delay] = amp * np.exp(1j * ph); return t
cases = []; i = 0
for snr, rms, taps, ppm in ((30, 200, None, 10.0), (24, 200, None, 10.0), (20, 60, None, -40.0), (16, 600, None, 30.0), (22, 300, echo(0.5, 5, 1.0), 10.0), (22, 300, echo(0.9, 8, 2.0), -20.0),
                            (26, 100, echo(0.7, 3, 0.4), 60.0), (18, 400, None, 0.0), (12, 200, None, 10.0), (34, 900, echo(0.3, 10, 1.3), 10.0)):
    rng = np.random.default_rng(2000 + i); i += 1
    x, d = Fm.tx_frame(preamble="scu"); y = Fm.channel(x, snr, cfo_hz=rng.uniform(-20e3, 20e3), tau=rng.uniform(0, 12), ppm=ppm, taps=taps, rng=rng, lead=300)
    xi, xq = X.to_adc(y, rms)
    try: r = X.receive_fixed(xi, xq, check=False)
    except AssertionError as e: print("case skipped:", e); continue
    if r is None: continue
    cases.append(r)
bits = Fm.payload_bits().reshape(44, 24, 4).astype(int); ridx = bits[..., 0] * 8 + bits[..., 1] * 4 + bits[..., 2] * 2 + bits[..., 3]
hexl, exp = [], []
for r in cases:
    Wr, Wi = r["W"]; exp.append("W")
    for j in range(28): hexl.append("%08x" % (int(Wr[j]) & 0xFFFFFFFF)); hexl.append("%08x" % (int(Wi[j]) & 0xFFFFFFFF))
    for yr, yi in r["wins"]:
        for a, b in zip(yr, yi): hexl.append("%08x" % (((int(b) & 0xFFFF) << 16) | (int(a) & 0xFFFF)))
    sc = X.score(r); si, sq = X.LEVEL(r["Zr"]), X.LEVEL(r["Zi"]); gi = np.vectorize(X.GRAY_IDX.get)(si) * 4 + np.vectorize(X.GRAY_IDX.get)(sq)
    sym_err = int(np.sum(gi != ridx)); bit_err = int(sum(bin(int(a) ^ int(b)).count("1") for a, b in zip(gi.ravel(), ridx.ravel())))
    err = int((((r["Zr"] - si * X.LV) ** 2 + (r["Zi"] - sq * X.LV) ** 2)).sum()); ref = int((((si ** 2 + sq ** 2) * X.LV * X.LV)).sum())
    for l in range(44):
        for j in range(24): exp.append("%d %d" % (r["Zr"][l, j], r["Zi"][l, j]))
    exp.append("%d %d %d %d %d" % (44 * 24, sym_err, bit_err, err, ref))
dbg = []
for r in cases:
    for l in range(44): dbg.append("%d %d %d" % (r["g_raw"][l, 0], r["g_raw"][l, 1], r["sl_raw"][l]))
    Zr, Zi = r["Zeq"]; D = X.D_IDX
    for l in range(4):
        for j in range(24): dbg.append("%d %d" % (Zr[l, D[j]], Zi[l, D[j]]))
open("data_dbg_exp.txt", "w").write("\n".join(dbg) + "\n")
open("data_in.hex", "w").write("\n".join(hexl) + "\n"); open("data_exp.txt", "w").write("\n".join(l for l in exp if l != "W") + "\n"); print("%d cases" % len(cases))
