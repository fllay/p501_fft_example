#!/usr/bin/env python3
"""Bit-exact integer model of the carrier-frequency estimator of rtl/qpsk_rx_fe.v (chapter 4d, extension: an automatic W0).

Input: the symbol m = (mi2, mq2) of the receiver engine after the AGC and before the derotation (the Costas loop plays no role: the estimator works while it is unlocked).

    d_n  = m_n * conj(m_{n-1})            the phase step between two symbols: 2 pi f T  +  a multiple of 90 degrees (the DQPSK data)
    psi  = 4 * arg(d_n)                   the data steps (multiples of 90 degrees) become multiples of 360 degrees and vanish
    ACC  = sum over N symbols of exp(j psi)       noise averages down, the useful part adds up in phase
    theta = atan2(ACC_im, ACC_re) = 4 x 2 pi f T         f = theta / (8 pi) x 960 kHz           (unambiguous for |f| < 120 kHz)
    W0   = round(theta / (8 pi) x 2^32)                  the same units and sign as the OMEGA register (turns per symbol x 2^32)

THE DESIGN DECISION (found with the real recordings, see README): the plain 4th power D = d^4 weights every symbol pair by |d|^4, and on the real signal the phase step depends
on the amplitude (4.7 degrees at the weak quarter of the pairs, 2.5 at the strong quarter, for a true 3.56): the weighted sum is 15 % low (+8.0 kHz for +9.49 kHz). With unit
magnitude (every pair counts the same) the estimate is +9.52 kHz, std 24 Hz at N = 2048. So the RTL takes the ANGLE of d (a CORDIC, adds and shifts only), multiplies it by 4 (a shift:
the 16-bit angle wraps by itself) and takes exp(j psi) from the 1024-entry sine/cosine table of the receiver. `fe_symbols_d4` below is the plain version, for comparison.

Fixed point (the RTL does exactly this):
    E1:  d = round((m x conj(m_prev)) >> 15), each component clipped to +-16383                   (15 bit; one complex multiply, 4 multipliers)
    E2+: CORDIC vectoring, 13 iterations, on (d_re << 3, d_im << 3): angle (16 bit, turns x 2^16), magnitude x = 1.647 x 8 x |d|
    E:   psi = (4 x angle) mod 2^16;  (c, s) = table[(psi + 32) >> 6]  (Q15)
    ACC_RE += c, ACC_IM += s, ACC_ABS += x           (32 bit, saturating)
The first symbol after the start has no predecessor and is skipped.  quality = |ACC| / (N x 32767): the mean resultant length, 1 for a clean signal, about 0.9 at 20 dB, towards 0 for noise.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "p501_rx"))
from qpsk_rx_fixed import cos_sin_lut

SYMBOL_RATE = 960e3
SH_D, CLIP_D = 15, 16383
K_ITER = 13
ANG_TAB = [int(round(np.arctan(2.0 ** -i) / (2 * np.pi) * 65536)) for i in range(K_ITER)]
ACC_MAX = 2 ** 31 - 1
COS_L, SIN_L = cos_sin_lut()


def _rshift_round(v, s):
    return (np.asarray(v, dtype=np.int64) + (1 << (s - 1))) >> s


def d_symbols(mi2, mq2):
    """d_n = m_n x conj(m_{n-1}) per symbol (15-bit components), and the valid flag (False for the first symbol)."""
    mi2 = np.asarray(mi2, dtype=np.int64); mq2 = np.asarray(mq2, dtype=np.int64)
    pmi = np.concatenate([[0], mi2[:-1]]); pmq = np.concatenate([[0], mq2[:-1]])
    re = mi2 * pmi + mq2 * pmq                                      # a x conj(b): re = ar br + ai bi
    im = mq2 * pmi - mi2 * pmq                                      #               im = ai br - ar bi
    valid = np.ones(len(mi2), dtype=bool); valid[0] = False
    return np.clip(_rshift_round(re, SH_D), -CLIP_D, CLIP_D), np.clip(_rshift_round(im, SH_D), -CLIP_D, CLIP_D), valid


def cordic_vector(x, y):
    """CORDIC in vectoring mode: (angle in turns x 2^16 modulo 2^16, magnitude x 1.647 x 8). Adds, subtracts and arithmetic shifts only."""
    x = np.asarray(x, dtype=np.int64) << 3; y = np.asarray(y, dtype=np.int64) << 3
    neg = x < 0
    x = np.where(neg, -x, x); y = np.where(neg, -y, y)
    ang = np.where(neg, 0x8000, 0).astype(np.int64)
    for i in range(K_ITER):
        up = y >= 0
        xn = np.where(up, x + (y >> i), x - (y >> i))
        yn = np.where(up, y - (x >> i), y + (x >> i))
        ang = ang + np.where(up, ANG_TAB[i], -ANG_TAB[i])
        x, y = xn, yn
    return ang & 0xFFFF, x


def fe_symbols(mi2, mq2):
    """Per symbol: (c, s, mag, valid): exp(j 4 arg d) in Q15 from the table, the CORDIC magnitude, and the valid flag."""
    dr, di, valid = d_symbols(mi2, mq2)
    ang, mag = cordic_vector(dr, di)
    psi = (ang * 4) & 0xFFFF
    idx = ((psi + 32) >> 6) & 1023
    return COS_L[idx], SIN_L[idx], mag, valid


def fe_symbols_d4(mi2, mq2):
    """The plain 4th power for comparison (magnitude weighted): D = d^4 with the same stages as the first model (shifts 13 and 10, clips 16383 and 65535)."""
    dr, di, valid = d_symbols(mi2, mq2)
    d2r = np.clip(_rshift_round(dr * dr - di * di, 13), -16383, 16383); d2i = np.clip(_rshift_round(2 * dr * di, 13), -16383, 16383)
    Dr = np.clip(_rshift_round(d2r * d2r - d2i * d2i, 10), -65535, 65535); Di = np.clip(_rshift_round(2 * d2r * d2i, 10), -65535, 65535)
    a, b = np.abs(Dr), np.abs(Di)
    return Dr, Di, np.maximum(a, b) + (np.minimum(a, b) >> 1), valid


def window(c, s, mag, valid, start, n):
    """Accumulate n valid symbols from index `start` on (the RTL's window): (acc_re, acc_im, acc_abs, count, first_index)."""
    idx = np.array([k for k in range(start, len(c)) if valid[k]][:n], dtype=np.int64)
    if len(idx) == 0: return 0, 0, 0, 0, start
    sat = lambda v: int(np.clip(v, -ACC_MAX - 1, ACC_MAX))
    return sat(c[idx].sum()), sat(s[idx].sum()), sat(mag[idx].sum()), len(idx), int(idx[0])


def estimate(acc_re, acc_im, count, scale=32767.0):
    """(frequency in Hz, quality, W0 register value) from a window's accumulators. scale: 32767 for the unit-vector version."""
    theta = np.arctan2(acc_im, acc_re)
    f_hz = theta / (8 * np.pi) * SYMBOL_RATE
    q = float(np.hypot(acc_re, acc_im) / (count * scale)) if count else 0.0
    w0 = int(round(theta / (8 * np.pi) * 2 ** 32)) & 0xFFFFFFFF
    return float(f_hz), q, w0
