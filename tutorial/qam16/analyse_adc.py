"""Spectrum of the raw ADC captures of p501_adc_capture.py: python3 analyse_adc.py off [on] -> adc_spectrum.png and a summary (noise floor, spurs, in-band level)."""
import sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
FS, N = 3.84e6, 4096
f = np.fft.fftshift(np.fft.fftfreq(N, 1 / FS)) / 1e3
fig, ax = plt.subplots(figsize=(11, 5))
for tag in sys.argv[1:]:
    x = np.load("sim/adc_%s.npy" % tag).astype(complex)
    print("%-4s rms %.1f counts, DC (%.1f, %.1f), I rms %.1f Q rms %.1f" % (tag, np.sqrt(np.mean(np.abs(x - x.mean()) ** 2)), x.real.mean(), x.imag.mean(), x.real.std(), x.imag.std()))
    b = (x[: len(x) // N * N] - x.mean()).reshape(-1, N) * np.hanning(N)
    p = np.fft.fftshift((np.abs(np.fft.fft(b, axis=1)) ** 2).mean(axis=0))
    d = 10 * np.log10(p + 1e-9)
    inb = np.abs(f) < 480
    ref = np.median(d[inb])
    print("     median level %.1f dB, max %.1f dB at %+.1f kHz (%.1f dB above median), band |f|<480 kHz: mean %.1f dB" % (ref, d.max(), f[np.argmax(d)], d.max() - ref, 10 * np.log10(p[inb].mean())))
    top = np.argsort(d)[-6:][::-1]
    print("     strongest bins (kHz, dB above median):", ", ".join("%+.1f:%.1f" % (f[i], d[i] - ref) for i in top))
    ax.plot(f, d, lw=0.7, label=tag)
ax.set(xlabel="kHz from 915 MHz", ylabel="dB (counts^2, relative)", title="P501 ADC spectrum"); ax.legend(); ax.grid(alpha=0.3)
fig.savefig("sim/adc_spectrum.png", dpi=110, bbox_inches="tight")
