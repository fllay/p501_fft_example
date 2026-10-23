#!/usr/bin/env python3
"""Is there an IQ-imbalance image in the P501's receive path (it is random after every AD9361 bring-up)? Least-squares fit of the known repeated frame to the capture, per segment, with and without the mirrored (conjugate)
copy of the frame as a second regressor. python3 analyse_image.py sim/adc_c1.npy [up]   (up = 2 for the 480 ksym/s capture: its period is 2 x 3868 samples)"""
import sys
import numpy as np
from scipy.signal import resample_poly
from qam16_frame_tx import one_period
f = sys.argv[1]; up = int(sys.argv[2]) if len(sys.argv) > 2 else 1
x = np.load(f).astype(complex); x = x - x.mean()
r = one_period(1.0).astype(complex)
if up > 1: r = resample_poly(r, up, 1)
P = len(r); n = np.arange(len(x)); SEG = 1000; FS = 3.84e6
R = np.conj(np.fft.fft(r)); best = (0, 0, 0)
for fc in np.arange(-20e3, 20e3, 150.0):
    y = x[:P] * np.exp(-2j * np.pi * fc * n[:P] / FS); c = np.abs(np.fft.ifft(np.fft.fft(y) * R))
    if c.max() > best[0]: best = (c.max(), fc, int(np.argmax(c)))
f0 = best[1]
def per_period(fc):
    d, g = [], []
    for k in range(0, len(x) - P, P):
        y = x[k:k + P] * np.exp(-2j * np.pi * fc * n[k:k + P] / FS); c = np.fft.ifft(np.fft.fft(y) * R); j = int(np.argmax(np.abs(c))); d.append(j); g.append(c[j])
    return np.array(d), np.array(g)
for _ in range(3):
    d, g = per_period(f0); ph = np.unwrap(np.angle(g)); f0 += np.polyfit(np.arange(len(ph)) * P / FS, ph, 1)[0] / (2 * np.pi)
d, g = per_period(f0); dd = np.unwrap(d.astype(float) * 2 * np.pi / P) * P / (2 * np.pi); slope = np.polyfit(np.arange(len(dd)), dd, 1)[0]
xc = x * np.exp(-2j * np.pi * f0 * n / FS); dly = lambda k: int(round(d[0] + slope * (k / P)))
res = {}
for name, L, image in (("1 tap", 1, False), ("1 tap + image", 1, True), ("3 taps", 3, False), ("3 taps + image", 3, True), ("9 taps", 9, False), ("9 taps + image", 9, True)):
    h = L // 2; e_tot = s_tot = 0.0; W = []; V = []
    for k in range(0, len(x) - SEG - 64, SEG):
        idx = np.arange(k, k + SEG); cols = [r[(idx - dly(k) - j) % P] for j in range(-h, h + 1)]
        if image: cols += [np.conj(r[(idx - dly(k) - j) % P]) * np.exp(-2j * np.pi * (2 * f0) * idx / FS) for j in range(-h, h + 1)]
        A = np.stack(cols, 1); w, *_ = np.linalg.lstsq(A, xc[idx], rcond=None); e = xc[idx] - A @ w
        e_tot += np.sum(np.abs(e) ** 2); s_tot += np.sum(np.abs(A[:, :L] @ w[:L]) ** 2); W.append(w[:L].sum()); V.append(w[L:].sum() if image else 0)
    res[name] = (10 * np.log10(e_tot / s_tot), 20 * np.log10(abs(np.mean(V)) / abs(np.mean(W))) if image else None, 20 * np.log10(np.mean(np.abs(V)) / np.mean(np.abs(W))) if image else None)
print("%s: carrier offset %+.0f Hz, clock %+.1f ppm, rms %.1f counts" % (f.split("/")[-1], f0, slope / P * 1e6 * (1 if up == 1 else 1), np.sqrt(np.mean(np.abs(x) ** 2))))
for k, v in res.items(): print("   %-16s residual %.1f dB%s" % (k, v[0], ("   image / signal %.1f dB (mean taps) %.1f dB (per segment)" % (v[1], v[2])) if v[1] is not None else ""))
