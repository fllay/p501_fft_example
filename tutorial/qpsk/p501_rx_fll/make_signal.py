"""Synthetic ADC signals for the frequency-estimator study: the bit-exact transmitter model (qpsk_model.py), a carrier offset, a sample-clock offset, noise, 12-bit quantisation."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "p501_tx"))
from qpsk_model import model

FS = 3.84e6


def synth(n_samples, f_off_hz=9700.0, snr_db=20.0, ppm=10.4, rms_counts=33.0, seed=1, phase0=0.0):
    """int arrays (xi, xq) of ADC counts. snr_db: signal power to noise power in the 3.84 MHz sample bandwidth (the matched filter adds about 6 dB); ppm: sample-clock offset."""
    n_tx = int(n_samples * (1 + abs(ppm) * 1e-6)) + 64
    i, q = model(n_tx, amp=0x4000)
    x = (i + 1j * q).astype(complex)
    if ppm:                                                              # the receiver's clock is ppm faster/slower: resample by linear interpolation (fine at 4 samples per symbol is not exact, 16-point sinc would be)
        t = np.arange(n_samples) * (1 + ppm * 1e-6)
        k = np.floor(t).astype(int); fr = t - k
        x = x[k] * (1 - fr) + x[k + 1] * fr
    else:
        x = x[:n_samples]
    x = x * np.exp(1j * (2 * np.pi * f_off_hz / FS * np.arange(len(x)) + phase0))
    x = x / np.sqrt(np.mean(np.abs(x[2000:]) ** 2)) * rms_counts
    rng = np.random.RandomState(seed)
    sig = np.mean(np.abs(x) ** 2)
    noise = (rng.randn(len(x)) + 1j * rng.randn(len(x))) * np.sqrt(sig / 10 ** (snr_db / 10) / 2)
    y = x + noise
    return np.clip(np.round(y.real), -2047, 2047).astype(np.int64), np.clip(np.round(y.imag), -2047, 2047).astype(np.int64)
