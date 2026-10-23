"""16-QAM / ZC frames as the ADC would see them: 960 ksym/s, 4 samples per symbol (3.84 MSPS), RRC 0.35 (the transmitter's 45-tap filter), carrier offset, sample-clock offset (ppm),
white noise of a given Es/N0, 12-bit quantisation.   Same conventions as tutorial/qpsk/p501_rx_fll/make_signal.py (the QPSK one).

    xi, xq, ids = synth16(nfr, snr_db=22, cfo_hz=3000, ppm=10.4)        # int ADC counts, and the payload indices of the frames
"""
import os, sys
import numpy as np
import frame16 as F
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qpsk", "p501_rx"))
from qpsk_rx_model import rrc_proto

FS, SPS = 3.84e6, 4


def tx_samples(sym):
    """RRC-shaped samples (4 per symbol, unit-energy-per-symbol filter) of a symbol stream"""
    h = rrc_proto(1)
    h = h / np.sqrt(np.sum(h ** 2) / SPS)                    # so that the average sample power of unit-power symbols is 1
    up = np.zeros(len(sym) * SPS, dtype=complex); up[::SPS] = sym
    return np.convolve(up, h)[len(h) // 2:len(h) // 2 + len(up)]


def synth16(nfr, snr_db=22.0, cfo_hz=3000.0, ppm=10.4, rms_counts=100.0, seed=1, phase0=0.4, payload="prbs15", lead=0):
    sym, ids = F.make_frames(nfr, payload, seed=seed)
    x = tx_samples(np.concatenate([np.zeros(lead, dtype=complex), sym, np.zeros(60, dtype=complex)]))
    n_out = int((len(x) - 3) / (1 + abs(ppm) * 1e-6))
    if ppm:                                                    # the receiver's sample clock is ppm faster / slower: linear interpolation
        t = np.arange(n_out) * (1 + ppm * 1e-6); k = np.floor(t).astype(int); fr = t - k
        x = x[k] * (1 - fr) + x[k + 1] * fr
    x = x * np.exp(1j * (2 * np.pi * cfo_hz / FS * np.arange(len(x)) + phase0))
    x = x / np.sqrt(np.mean(np.abs(x[2000:]) ** 2)) * rms_counts
    rng = np.random.RandomState(seed + 100)
    sig = np.mean(np.abs(x) ** 2)
    noise = (rng.randn(len(x)) + 1j * rng.randn(len(x))) * np.sqrt(sig * SPS / 10 ** (snr_db / 10) / 2)       # Es/N0: the noise power per sample is sig * SPS / (Es/N0)
    y = x + noise
    return np.clip(np.round(y.real), -2047, 2047).astype(np.int64), np.clip(np.round(y.imag), -2047, 2047).astype(np.int64), ids
