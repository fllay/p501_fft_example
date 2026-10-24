#!/usr/bin/env python3
"""Test vectors for the OFDM detector and the derotator: sc_a..e.hex (ADC samples {xq, xi}), derot_vec.hex.   python3 gen_sync_vectors.py"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ofdm_model as Fm, ofdm_fixed as X
def hexline(xi, xq): return "%08x" % ((int(xq) & 0xFFFF) << 16 | (int(xi) & 0xFFFF))
cases = {"a": dict(snr=24, cfo=9700.0, tau=4.3, rms=200, seed=1), "b": dict(snr=20, cfo=-15200.0, tau=9.6, rms=60, seed=2), "c": dict(snr=28, cfo=31000.0, tau=0.2, rms=600, seed=3),
         "d": dict(snr=16, cfo=2500.0, tau=11.0, rms=300, seed=4), "e": dict(snr=24, cfo=9700.0, tau=4.3, rms=1200, seed=5)}
for name, c in cases.items():
    rng = np.random.default_rng(c["seed"]); x, d = Fm.tx_frame(preamble="scu"); y = Fm.channel(x, c["snr"], cfo_hz=c["cfo"], tau=c["tau"], ppm=10.0, rng=rng, lead=300)
    xi, xq = X.to_adc(y, c["rms"]); n = 900
    open("sc_%s.hex" % name, "w").write("\n".join(hexline(a, b) for a, b in zip(xi[:n], xq[:n])) + "\n")
rng = np.random.default_rng(21); x, d = Fm.tx_frame(preamble="scu")                                               # case q: the tail of the previous frame (320 active samples + the 80 quiet ones, 24 dB) in front of the frame: the falling edge must not fire the detector
y = Fm.channel(np.concatenate([x[-400:], x]), 24, cfo_hz=9700.0, tau=4.3, ppm=10.0, rng=rng, lead=0); xi, xq = X.to_adc(y, 170)
open("sc_q.hex", "w").write("\n".join(hexline(a, b) for a, b in zip(xi[:1000], xq[:1000])) + "\n")
rng = np.random.default_rng(9)                                                                                  # noise only, 14 counts rms: no detection
xi = np.clip(np.round(rng.standard_normal(1500) * 14), -2047, 2047); xq = np.clip(np.round(rng.standard_normal(1500) * 14), -2047, 2047)
open("sc_n.hex", "w").write("\n".join(hexline(a, b) for a, b in zip(xi, xq)) + "\n")
NV = 4000; rng = np.random.default_rng(11); lines = []
for i in range(NV):
    xi_, xq_ = int(rng.integers(-2047, 2048)), int(rng.integers(-2047, 2048)); m = int(rng.integers(0, 3841))
    w = int(rng.integers(-2 ** 31, 2 ** 31)) if i % 3 else int(rng.integers(-3 * 10 ** 6, 3 * 10 ** 6)); g = int(rng.choice([100, 114, 513, 1736, 2612, 5000, 65535])) if i % 2 else int(rng.integers(0, 65536))
    lines.append("%024x" % (((g & 0xFFFF) << 80) | ((w & 0xFFFFFFFF) << 48) | (m << 32) | ((xq_ & 0xFFFF) << 16) | (xi_ & 0xFFFF)))
    yr, yi = X.derotate(np.array([xi_]), np.array([xq_]), 0, 1, -m, w, g); lines.append(None) if False else None
open("derot_vec.hex", "w").write("\n".join(lines) + "\n")
exp = []
rng = np.random.default_rng(11)
for i in range(NV):
    xi_, xq_ = int(rng.integers(-2047, 2048)), int(rng.integers(-2047, 2048)); m = int(rng.integers(0, 3841))
    w = int(rng.integers(-2 ** 31, 2 ** 31)) if i % 3 else int(rng.integers(-3 * 10 ** 6, 3 * 10 ** 6)); g = int(rng.choice([100, 114, 513, 1736, 2612, 5000, 65535])) if i % 2 else int(rng.integers(0, 65536))
    yr, yi = X.derotate(np.array([xi_]), np.array([xq_]), 0, 1, -m, w, g); exp.append("%d %d" % (yr[0], yi[0]))
open("derot_exp.txt", "w").write("\n".join(exp) + "\n"); print("wrote vectors")
