#!/usr/bin/env python3
"""Is the impairment of the B210 -> P501 link a linear channel (multipath / filter ISI) or noise? The B210 transmits one known period (3868 samples, qam16_frame_tx.one_period) over and over; the raw ADC capture of
p501_adc_capture.py is cut into segments of SEG samples, each is fitted by least squares as a short FIR (taps at 3.84 MSPS) of that known waveform (the carrier offset and the clock offset are removed first). The residual
power versus the signal power, as a function of the number of taps, says which it is: a residual that drops with more taps is a linear channel, one that does not is noise / phase noise / non-linearity.
    source tools/gnuradio_env.sh; python3 analyse_adc_ls.py sim/adc_long.npy"""
import sys
import numpy as np
from qam16_frame_tx import one_period
x = np.load(sys.argv[1]).astype(complex); x = x - x.mean()
r = one_period(1.0); P = len(r); SEG = 1000
n = np.arange(len(x))
# coarse carrier offset: best FFT-correlation peak over a frequency grid on the first 3 periods
best = (0, 0, 0)
R = np.conj(np.fft.fft(r))
for f in np.arange(-20e3, 20e3, 150.0):
    y = (x[:P] * np.exp(-2j * np.pi * f * n[:P] / 3.84e6))
    c = np.abs(np.fft.ifft(np.fft.fft(y) * R))
    if c.max() > best[0]: best = (c.max(), f, int(np.argmax(c)))
f0 = best[1]; print("coarse carrier offset %+.0f Hz, first alignment %d" % (f0, best[2]))
def fit_phase_delay(f):
    ds, gs = [], []
    for k in range(0, len(x) - P, P):
        y = x[k:k + P] * np.exp(-2j * np.pi * f * n[k:k + P] / 3.84e6)
        c = np.fft.ifft(np.fft.fft(y) * R); j = int(np.argmax(np.abs(c))); ds.append(j); gs.append(c[j] / np.sum(np.abs(r) ** 2))
    return np.array(ds), np.array(gs)
for it in range(3):                                           # refine the carrier from the phase slope of the per-period gain
    d, g = fit_phase_delay(f0)
    ph = np.unwrap(np.angle(g)); t = np.arange(len(ph)) * P / 3.84e6
    f0 += np.polyfit(t, ph, 1)[0] / (2 * np.pi)
d, g = fit_phase_delay(f0)
dd = np.unwrap(d.astype(float) * 2 * np.pi / P) * P / (2 * np.pi)
slope = np.polyfit(np.arange(len(dd)), dd, 1)[0]
print("carrier offset %+.1f Hz, delay drift %+.3f samples/period (clock %+.1f ppm), gain |g| %.1f counts (std %.1f%%)" % (f0, slope, slope / P * 1e6, np.abs(g).mean(), 100 * np.abs(g).std() / np.abs(g).mean()))
xc = x * np.exp(-2j * np.pi * f0 * n / 3.84e6)
dly = lambda k: int(round(d[0] + slope * (k / P)))            # integer delay of the segment starting at sample k (the drift is followed segment by segment)
for L in (1, 3, 9, 17, 33):
    h = L // 2; res = sig = 0.0; taps = []
    for k in range(0, len(x) - SEG - 64, SEG):
        idx = np.arange(k, k + SEG)
        A = np.stack([r[(idx - dly(k) - j) % P] for j in range(-h, h + 1)], 1)
        w, *_ = np.linalg.lstsq(A, xc[idx], rcond=None)
        e = xc[idx] - A @ w
        res += np.sum(np.abs(e) ** 2); sig += np.sum(np.abs(A @ w) ** 2); taps.append(w)
    print("taps %2d: residual %.1f dB below the fitted signal" % (L, 10 * np.log10(res / sig)) + ("   (thermal floor alone: %.1f dB)" % (10 * np.log10((13.9 ** 2 * 1.0) / np.mean(np.abs(xc) ** 2))) if L == 1 else ""))
    if L == 9: print("   mean tap magnitudes (dB rel. to the strongest):", np.round(20 * np.log10(np.abs(np.mean(taps, axis=0)) / np.abs(np.mean(taps, axis=0)).max()), 1))
