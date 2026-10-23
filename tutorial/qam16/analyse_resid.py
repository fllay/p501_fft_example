#!/usr/bin/env python3
"""What is in the part of the capture that the known frame does not explain? The known repeated frame is fitted (3 taps, segments of 1000 samples) and subtracted; the residual is analysed for bursts (power against time) and narrow-band content (spectrum, spectrogram).
python3 analyse_resid.py sim/adc_c1.npy sim/bu/adc_bu_00.npy   -> sim/resid_<name>.png and a summary"""
import sys, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from qam16_frame_tx import one_period
FS = 3.84e6
def residual(f):
    x = np.load(f).astype(complex); x = x - x.mean(); r = one_period(1.0).astype(complex); P = len(r); n = np.arange(len(x)); R = np.conj(np.fft.fft(r)); best = (0, 0)
    for fc in np.arange(-20e3, 20e3, 150.0):
        c = np.abs(np.fft.ifft(np.fft.fft(x[:P] * np.exp(-2j * np.pi * fc * n[:P] / FS)) * R))
        if c.max() > best[0]: best = (c.max(), fc)
    f0 = best[1]
    def per(fc):
        d, g = [], []
        for k in range(0, len(x) - P, P):
            c = np.fft.ifft(np.fft.fft(x[k:k + P] * np.exp(-2j * np.pi * fc * n[k:k + P] / FS)) * R); j = int(np.argmax(np.abs(c))); d.append(j); g.append(c[j])
        return np.array(d), np.array(g)
    for _ in range(3):
        d, g = per(f0); f0 += np.polyfit(np.arange(len(g)) * P / FS, np.unwrap(np.angle(g)), 1)[0] / (2 * np.pi)
    d, g = per(f0); dd = np.unwrap(d.astype(float) * 2 * np.pi / P) * P / (2 * np.pi); slope = np.polyfit(np.arange(len(dd)), dd, 1)[0]
    xc = x * np.exp(-2j * np.pi * f0 * n / FS); res = np.zeros(len(x), complex); SEG = 1000
    for k in range(0, len(x) - SEG - 64, SEG):
        idx = np.arange(k, k + SEG); dl = int(round(d[0] + slope * (k / P)))
        A = np.stack([r[(idx - dl - j) % P] for j in (-1, 0, 1)], 1); w, *_ = np.linalg.lstsq(A, xc[idx], rcond=None); res[idx] = xc[idx] - A @ w
    return xc, res, f0
fig, axs = plt.subplots(len(sys.argv) - 1, 3, figsize=(17, 3.6 * (len(sys.argv) - 1)), squeeze=False)
for row, f in enumerate(sys.argv[1:]):
    xc, res, f0 = residual(f); res = res[2000:-2000]; name = os.path.basename(f)[:-4]
    W = 384; pw = np.mean(np.abs(res[:len(res) // W * W]).reshape(-1, W) ** 2, axis=1)                      # 100 microsecond windows
    N = 4096; b = res[:len(res) // N * N].reshape(-1, N) * np.hanning(N); p = np.fft.fftshift((np.abs(np.fft.fft(b, axis=1)) ** 2).mean(axis=0)); fr = np.fft.fftshift(np.fft.fftfreq(N, 1 / FS)) / 1e3
    ps = 10 * np.log10(p + 1e-9); med = np.median(ps[np.abs(fr) < 1500])
    S = 256; sg = np.abs(np.fft.fftshift(np.fft.fft(res[:len(res) // S * S].reshape(-1, S) * np.hanning(S), axis=1), axes=1)) ** 2
    print("%-12s carrier %+6.0f Hz | residual rms %.1f counts | power in 100 us windows: mean %.0f, std/mean %.3f (white noise: %.3f), max/mean %.2f | spectrum max %.1f dB above median at %+.0f kHz" %
          (name, f0, np.sqrt(np.mean(np.abs(res) ** 2)), pw.mean(), pw.std() / pw.mean(), 1 / np.sqrt(W), pw.max() / pw.mean(), ps[np.abs(fr) < 1500].max() - med, fr[np.abs(fr) < 1500][np.argmax(ps[np.abs(fr) < 1500])]))
    a = axs[row]; a[0].plot(fr, ps, lw=0.6); a[0].set(title=name + ": residual spectrum", xlabel="kHz", xlim=(-1900, 1900)); a[0].grid(alpha=0.3)
    a[1].plot(np.arange(len(pw)) * W / FS * 1e3, pw, lw=0.6); a[1].set(title="residual power, 100 us windows", xlabel="ms", xlim=(0, 60)); a[1].grid(alpha=0.3)
    a[2].imshow(10 * np.log10(sg[:min(len(sg), 800)] + 1).T, aspect="auto", origin="lower", extent=[0, min(len(sg), 800) * S / FS * 1e3, -1920, 1920]); a[2].set(title="spectrogram (first 53 ms)", xlabel="ms", ylabel="kHz")
fig.tight_layout(); fig.savefig("sim/resid.png", dpi=90)
