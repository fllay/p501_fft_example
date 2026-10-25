#!/usr/bin/env python3
"""A recording for the File Source of ofdm_b210_frame_rx.grc, made with the model instead of a B210: 60 OFDM frames (60 ms) through a channel with a carrier offset (9 kHz, as between the P501 and the B210), a delay
with a fraction of a sample, a sample clock error and noise. Complex float samples (the GNU Radio file format), 3.84 MS/s, rms 0.1, replayed in a loop.

    python3 make_ofdm_capture.py [out.c64] [SNR dB, default 24] [carrier offset Hz, default 9000] [DC offset (real and imaginary part), default 0]
A DC offset of 0.014 (0.2 of the rms of 0.1) is what the B210 leakage looks like: without the DC removal of the receiver it fires the detector in the idle slot."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ofdm_model as Fm
out = sys.argv[1] if len(sys.argv) > 1 else "ofdm_b210_capture.c64"
snr = float(sys.argv[2]) if len(sys.argv) > 2 else 24.0
cfo = float(sys.argv[3]) if len(sys.argv) > 3 else 9000.0
dc = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
x, d = Fm.tx_frame(preamble="scu")
y = Fm.channel(np.tile(x, 60), snr, cfo_hz=cfo, tau=3.4, ppm=10.0, rng=np.random.default_rng(5), lead=300, trail=300)
y = (y / np.sqrt(np.mean(np.abs(y) ** 2)) * 0.1 + dc * (1 + 1j)).astype(np.complex64)
y.tofile(out)
print("%s: %d samples (%.1f ms), SNR %.0f dB, carrier offset %.0f Hz, DC %.3f" % (out, len(y), 1e3 * len(y) / Fm.FS, snr, cfo, dc * np.sqrt(2)))
