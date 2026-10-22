"""Synthetic ADC signals with frames for the sync study and the RTL simulation: the bit-exact transmitter model (qpsk_model.py) fed with frames_bits(), a carrier offset,
a sample-clock offset, noise, optional gaps (the signal blanked: a lost frame), 12-bit quantisation."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "p501_tx"))
from qpsk_model import model
from qpsk_frame import frames_bits, PRE_SYMBOLS

FS = 3.84e6


def synth_frames(n_samples, pl=192, f_off_hz=9700.0, snr_db=20.0, ppm=10.4, rms_counts=33.0, seed=1, phase0=0.0, gaps=()):
    """int arrays (xi, xq) of ADC counts. gaps: [(first_symbol, last_symbol)]: the signal (and its noise) is replaced by noise only there."""
    fl = PRE_SYMBOLS + pl
    n_tx = int(n_samples * (1 + abs(ppm) * 1e-6)) + 64
    nframes = n_tx // 4 // fl + 3
    i, q = model(n_tx, amp=0x4000, bits=frames_bits(pl, nframes))
    x = (i + 1j * q).astype(complex)
    if ppm:
        t = np.arange(n_samples) * (1 + ppm * 1e-6); k = np.floor(t).astype(int); fr = t - k
        x = x[k] * (1 - fr) + x[k + 1] * fr
    else:
        x = x[:n_samples]
    x = x * np.exp(1j * (2 * np.pi * f_off_hz / FS * np.arange(len(x)) + phase0))
    x = x / np.sqrt(np.mean(np.abs(x[2000:]) ** 2)) * rms_counts
    for a, b in gaps:
        x[a * 4:(b + 1) * 4] = 0
    rng = np.random.RandomState(seed)
    sig = rms_counts ** 2
    noise = (rng.randn(len(x)) + 1j * rng.randn(len(x))) * np.sqrt(sig / 10 ** (snr_db / 10) / 2)
    y = x + noise
    return np.clip(np.round(y.real), -2047, 2047).astype(np.int64), np.clip(np.round(y.imag), -2047, 2047).astype(np.int64)
