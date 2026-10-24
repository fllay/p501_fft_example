#!/usr/bin/env python3
"""Vectors for ofdm_fft.v: fft_in.hex (64 samples per transform, {im[15:0], re[15:0]}) and fft_exp.txt (the 64 bins of ofdm_fixed.fft64). Random inputs of several amplitudes and real OFDM windows (derotated T1 / data windows)."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ofdm_model as Fm, ofdm_fixed as X
rng = np.random.default_rng(21); ins, outs = [], []
def add(xr, xi):
    xr, xi = np.asarray(xr, dtype=np.int64), np.asarray(xi, dtype=np.int64); r, i = X.fft64(xr, xi); ins.append((xr, xi)); outs.append((r, i))
for amp in (30, 500, 3000, 8000, 8000, 3000):                                                          # random, uniform
    for _ in range(25): add(rng.integers(-amp, amp + 1, 64), rng.integers(-amp, amp + 1, 64))
add(np.zeros(64), np.zeros(64)); add(np.full(64, 8000), np.zeros(64)); add(np.zeros(64), np.full(64, -8000))                 # a constant (all the energy in bin 0), zeros
n = np.arange(64); add(np.round(8000 * np.cos(2 * np.pi * 5 * n / 64)), np.round(8000 * np.sin(2 * np.pi * 5 * n / 64)))      # a tone
for seed in range(40):                                                                                          # real OFDM windows after the gain and the derotation
    r2 = np.random.default_rng(100 + seed); x, d = Fm.tx_frame(preamble="scu"); y = Fm.channel(x, 24, cfo_hz=r2.uniform(-20e3, 20e3), tau=r2.uniform(0, 12), rng=r2, lead=300)
    xi, xq = X.to_adc(y, 200 * (1 + seed % 4)); di = X.detect_info(xi, xq)
    s0 = di["s0"]; l = int(r2.integers(0, 44)); ws = s0 + 240 + l * 80 + 10
    yr, yi = X.derotate(xi, xq, ws, 64, s0, di["w_c"], di["G"]); add(yr, yi)
open("fft_in.hex", "w").write("\n".join("%08x" % (((int(b) & 0xFFFF) << 16) | (int(a) & 0xFFFF)) for xr, xi in ins for a, b in zip(xr, xi)) + "\n")
open("fft_exp.txt", "w").write("\n".join("%d %d" % (a, b) for r, i in outs for a, b in zip(r, i)) + "\n")
print("%d transforms" % len(ins))
