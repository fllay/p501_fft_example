"""Tone, image, DC and harmonics from the captures of p501_iq_image.py (/tmp/iq/iq_<tag>_<bring-up>_<tone kHz>.npy).    python3 analyse_iq_image.py /tmp/iq a"""
import sys, glob, re
import numpy as np
FS = 3.84e6; N = 8192
d, tag = sys.argv[1], sys.argv[2]
rows = []
for f in sorted(glob.glob("%s/iq_%s_*.npy" % (d, tag))):
    b, k = [int(v) for v in re.findall(r"iq_%s_(\d+)_(\d+)\.npy" % tag, f)[0]]
    x = np.load(f).astype(complex); x -= 0                                   # the DC is measured, not removed
    seg = x[:len(x) // N * N].reshape(-1, N); w = np.hanning(N)
    P = (np.abs(np.fft.fft(seg * w, axis=1)) ** 2).mean(0); P /= np.sum(w ** 2) / N                                          # power per bin, a tone of power p gives p * N^2 ... compared in ratios only
    fr = np.fft.fftfreq(N, 1 / FS); ib = lambda fk: int(np.argmin(np.abs(fr - fk * 1e3)))
    def band(c, h=3): return P[max(c - h, 0):c + h + 1].sum()
    t, im, dc = band(ib(k)), band(ib(-k)), band(ib(0))
    h2, h3 = band(ib(2 * k)), band(ib(3 * k)); nz = np.median(P) * 7
    # the noise floor around the image for the image-to-noise comparison
    rows.append((b, k, 10 * np.log10(im / t), 10 * np.log10(dc / t), 10 * np.log10(h2 / t), 10 * np.log10(h3 / t), 10 * np.log10(nz / t)))
print("%8s %8s %14s %10s %10s %10s %12s" % ("bring-up", "tone kHz", "image (dBc)", "DC (dBc)", "2nd (dBc)", "3rd (dBc)", "noise (dBc, 7 bins)"))
for r in rows: print("%8d %8d %14.1f %10.1f %10.1f %10.1f %12.1f" % r)
for k in sorted({r[1] for r in rows}):
    im = [r[2] for r in rows if r[1] == k]; print("tone %d kHz: image %.1f dBc mean, %.1f .. %.1f over %d bring-ups" % (k, np.mean(im), min(im), max(im), len(im)))
