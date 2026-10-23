#!/usr/bin/env python3
"""Spectrum from the LO scan of p501_scan.py: python3 analyse_scan.py sim/scan_s1.npz [name]  -> sim/scan_<name>.png and a table.
Every step is a +-1.5 MHz slice (the AD9361's 3.84 MS/s window, edges cut); the slices are joined on an absolute frequency axis. Levels are 'dB above the receiver's own noise floor' (median of all slices); the floor corresponds to about -105 dBm
in 3.84 MHz (thermal -108 dBm + a noise figure of about 3 dB: an estimate, not a calibration)."""
import sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
d = np.load(sys.argv[1]); name = sys.argv[2] if len(sys.argv) > 2 else "scan"
lo, x = d["lo_hz"], d["x"]; FS = 3.84e6; N = 2048
fr = np.fft.fftshift(np.fft.fftfreq(N, 1 / FS)); keep = np.abs(fr) < 1.5e6
F, P = [], []
for l, xi in zip(lo, x):
    xi = xi.astype(complex); xi = xi - xi.mean(); b = xi[:len(xi) // N * N].reshape(-1, N) * np.hanning(N)
    p = np.fft.fftshift((np.abs(np.fft.fft(b, axis=1)) ** 2).mean(axis=0)); c = np.abs(fr) < 4e3; p[c] = np.median(p)               # the DC line of every slice is the receiver's own
    F.append((l + fr[keep]) / 1e6); P.append(10 * np.log10(p[keep]))
F, P = np.concatenate(F), np.concatenate(P)
order = np.argsort(F); F, P = F[order], P[order]
med = np.median(P); rel = P - med
fig, ax = plt.subplots(figsize=(14, 5)); ax.plot(F, rel, lw=0.4); ax.set(xlabel="MHz", ylabel="dB above the receiver noise floor", title="P501 scan, RX gain index 76, 3 MHz steps"); ax.grid(alpha=0.3)
for a, b, t in ((824, 849, "LTE B5 UL"), (869, 894, "B5 DL"), (880, 915, "GSM900/B8 UL"), (925, 960, "GSM900/B8 DL"), (902, 928, "US ISM")): ax.axvspan(a, b, alpha=0.06, color="C%d" % (len(t) % 9)); ax.text((a + b) / 2, rel.max() * 0.9, t, ha="center", fontsize=7)
fig.savefig("sim/scan_%s.png" % name, dpi=100, bbox_inches="tight")
print("floor (median): %.1f dB; per 5 MHz: strongest 100 kHz bin above the floor, and the mean power above the floor" % med)
print("   MHz         max     mean over the 5 MHz")
for a in np.arange(830, 980, 5.0):
    m = (F >= a) & (F < a + 5)
    if m.sum(): print("   %3.0f-%3.0f   %5.1f dB   %5.1f dB" % (a, a + 5, np.max(np.convolve(rel[m], np.ones(53) / 53, "same")), 10 * np.log10(np.mean(10 ** (rel[m] / 10)))))
