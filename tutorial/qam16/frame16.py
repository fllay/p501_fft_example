"""The 16-QAM / Zadoff-Chu frame of the handoff (ref/HANDOFF.md) at 1 sample per symbol, without GNU Radio, plus a symbol-rate channel.

  frame = [CP 8 | ZC 63 (root 1) | 14 x (63 16-QAM + 1 pilot)] = 967 symbols, unit average power (the ZC word has amplitude 1)
  payload 'prbs15': the 882 data symbols come from a PRBS-15 (x^15 + x^14 + 1, seed 0x7FFF, MSB first, 4 bits per symbol: I = top two bits, Q = bottom two) RESTARTED IN EVERY FRAME,
                    the pattern an FPGA can reproduce (the handoff's numpy RandomState cannot be); 'numpy': the handoff's fixed payload (seed), 'random': new random data every frame
  Gray levels per axis: index 00 -> -3, 01 -> -1, 10 -> +3, 11 -> +1 (all / sqrt 10), as ref/gnuradio/tx_block.py
"""
import numpy as np

N_ZC, ROOT, N_CP, N_BLK, N_DATA = 63, 1, 8, 14, 63
N_PAY = N_BLK * N_DATA                        # 882 data symbols
BLK = N_DATA + 1
PAY_LEN = N_BLK * BLK                         # 896 (data + pilots)
FRAME = N_CP + N_ZC + PAY_LEN                 # 967
S10 = np.sqrt(10.0)
GRAY = np.array([-3, -1, 3, 1]) / S10         # 2-bit index -> level
LEVEL_IDX = {-3: 0, -1: 1, 1: 3, 3: 2}        # level (x sqrt 10) -> 2-bit index
PILOTS = np.array([1, 1, -1, 1, -1, -1, 1, 1, 1, -1, -1, 1, -1, 1], dtype=float)
_N = np.arange(N_ZC)
ZC = np.exp(-1j * np.pi * ROOT * _N * (_N + 1) / N_ZC)
RS = 960e3


def prbs15_bits(n):
    s, out = 0x7FFF, np.empty(n, dtype=np.uint8)
    for i in range(n):
        out[i] = (s >> 14) & 1
        s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
    return out


def prbs15_indices():
    """the 882 symbol indices (4-bit values, I = idx >> 2, Q = idx & 3) of the payload of every frame"""
    b = prbs15_bits(4 * N_PAY).reshape(N_PAY, 4).astype(int)
    return b[:, 0] * 8 + b[:, 1] * 4 + b[:, 2] * 2 + b[:, 3]


def qam(idx):
    idx = np.asarray(idx)
    return GRAY[idx >> 2] + 1j * GRAY[idx & 3]


def make_frames(nfr, payload="prbs15", seed=1):
    """nfr frames back to back: complex symbols, and the payload indices of every frame (nfr x 882)"""
    rng = np.random.RandomState(int(seed))
    fixed = rng.randint(0, 16, N_PAY) if payload == "numpy" else None
    pr = prbs15_indices() if payload == "prbs15" else None
    out, ids = [], []
    for _ in range(nfr):
        idx = pr if payload == "prbs15" else fixed if payload == "numpy" else rng.randint(0, 16, N_PAY)
        data = qam(idx).reshape(N_BLK, N_DATA)
        pay = np.concatenate([data, PILOTS[:, None].astype(complex)], axis=1).reshape(-1)
        out.append(np.concatenate([ZC[-N_CP:], ZC, pay])); ids.append(idx)
    return np.concatenate(out), np.array(ids)


def channel(s, snr_db, cfo_hz=0.0, rs=RS, phase=0.9, gain=1.0, lead=137, seed=5, noise_only=False, pn_std=0.0, drift_hz_s=0.0):
    """symbol-rate channel after matched filter and timing recovery: carrier offset, phase, gain error, complex noise of Es/N0 = snr_db (unit-power symbols), `lead` noise-only symbols in front"""
    rng = np.random.default_rng(seed)
    n = np.arange(len(s))
    ph = 2 * np.pi * cfo_hz / rs * n + phase + np.pi * drift_hz_s / rs ** 2 * n ** 2          # carrier offset, and a frequency ramp of drift_hz_s Hz per second
    if pn_std > 0: ph = ph + np.cumsum(pn_std * rng.standard_normal(len(s)))                  # Wiener phase noise, pn_std rad per symbol (a linewidth of d Hz is sqrt(2 pi d / rs))
    sig = 0 * s if noise_only else s * np.exp(1j * ph) * gain
    nz = 10 ** (-snr_db / 20) / np.sqrt(2)
    x = sig + nz * (rng.standard_normal(len(s)) + 1j * rng.standard_normal(len(s)))
    return np.concatenate([nz * (rng.standard_normal(lead) + 1j * rng.standard_normal(lead)), x])


def level(a):
    """slicer on a value in units of 1/sqrt(10): -3, -1, 1, 3"""
    return -3 if a < -2 else (-1 if a < 0 else (1 if a < 2 else 3))
