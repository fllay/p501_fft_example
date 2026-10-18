#!/usr/bin/env python3
"""Carrier and sample-clock offset between the B210 and the P501 from a capture of two tones at +-1.5 MHz (run_capture_4b.py --signal twotone).

A tone of nominal frequency f_k sent by the B210 arrives in the P501's samples at  f_k*(1+d) + dLO, where d = fs_B210/fs_P501 - 1 is the
sample-clock offset and dLO the offset of the two LOs. The two tones therefore give   dLO = (f+ + f-)/2   and   d = (f+ - f-)/3 MHz - 1."""
import sys
import numpy as np
x = np.fromfile(sys.argv[1], dtype=np.complex64); fs = 3.84e6
N = 1 << 21; seg = x[100000:100000 + N]; w = np.hanning(N)
X = np.abs(np.fft.fftshift(np.fft.fft(seg * w)))**2; f = np.fft.fftshift(np.fft.fftfreq(N, 1/fs))
def peak(lo, hi):
    m = (f > lo) & (f < hi); i = np.where(m)[0][np.argmax(X[m])]; a, b, c = np.log(X[i-1]), np.log(X[i]), np.log(X[i+1]); return f[i] + 0.5*(a - c)/(a - 2*b + c)*(fs/N), 10*np.log10(X[i]/np.median(X))
fp, sp = peak(1.40e6, 1.60e6); fm, sm = peak(-1.60e6, -1.40e6)
print(f"tone near +1.5 MHz: {fp:.2f} Hz ({sp:.0f} dB over the median);  tone near -1.5 MHz: {fm:.2f} Hz ({sm:.0f} dB)")
dlo = (fp + fm) / 2; d = (fp - fm) / 3.0e6 - 1
print(f"LO offset (B210 - P501): {dlo:+.1f} Hz = {dlo/915e6*1e6:+.2f} ppm at 915 MHz")
print(f"sample-clock offset (B210 / P501 - 1): {d*1e6:+.2f} ppm  ->  {d*3.84e6:+.1f} Hz of 3.84 MSPS, {d*960e3:+.2f} symbols/s of timing slip at 960 ksym/s")
