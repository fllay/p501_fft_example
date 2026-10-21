#!/usr/bin/env python3
"""Bit-exact integer model of the AUTONOMOUS estimator of rtl/qpsk_rx_all.v: polyphase matched filter -> 4th-power estimator -> Costas loop, with no software in the loop.

The estimator of qpsk_fe_fixed.py accumulates exp(j 4 arg(m_n conj(m_n-1))) over a window of N symbols. Here the hardware also does what Python did:

    theta = atan2(ACC_IM, ACC_RE)   by a CORDIC (vectoring, 18 iterations), the angle in turns x 2^20 (mod 2^20); the CORDIC magnitude xm = 1.6468 |ACC|
    w     = signed(angle20) << 10   = theta / (8 pi) x 2^32 : the Costas frequency in the units of the OMEGA register (turns per symbol x 2^32); exact up to +-120 kHz
    gate  : the window counts only if xm >= cnt x QMIN   (QMIN = q_min x 32767 x 1.6468: the mean resultant length must be above q_min, e.g. 0.3; a window of noise does not load anything)
    load  : the Costas loop's OMEGA is replaced by w at the S7 state of the first symbol AFTER the window (instead of the integrator update); the phase theta continues.

Modes (register FE_AUTO): bit 0 enable, bit 1 continuous.  Once (bit 1 = 0): windows follow each other until one passes the gate, that one loads OMEGA, then the estimator waits until FE_AUTO is written 0 and 1 again.
Continuous: every window that passes loads OMEGA (the Costas loop's integrator is replaced by the measurement once per window; its proportional path keeps the phase).
Windows are contiguous: the first one starts with the first symbol after the enable, the next with the symbol after the last one of the window.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "p501_rx_fll")); sys.path.insert(0, os.path.join(HERE, "..", "p501_rx"))
import qpsk_fe_fixed as E

K_ITER = 18
ANG20 = [int(round(np.arctan(2.0 ** -i) / (2 * np.pi) * 2 ** 20)) for i in range(K_ITER)]
CORDIC_GAIN = float(np.prod([np.sqrt(1 + 4.0 ** -i) for i in range(K_ITER)]))      # 1.6468
SYMBOL_RATE = 960e3


def atan_cordic(x, y):
    """CORDIC vectoring on (x, y): (angle in turns x 2^20 modulo 2^20, magnitude x CORDIC_GAIN). Adds, subtracts, shifts."""
    ang = 0
    if x < 0:
        x, y, ang = -x, -y, 1 << 19
    for i in range(K_ITER):
        if y >= 0:
            x, y, ang = x + (y >> i), y - (x >> i), ang + ANG20[i]
        else:
            x, y, ang = x - (y >> i), y + (x >> i), ang - ANG20[i]
    return ang & 0xFFFFF, x


def w_from_angle(ang):
    a = ang - (1 << 20) if ang >= (1 << 19) else ang
    return a << 10


def qmin_reg(q):
    return int(round(q * 32767 * CORDIC_GAIN))


def window_estimate(acc_re, acc_im, cnt, qmin):
    """(w, passed, angle, magnitude) of one window."""
    ang, xm = atan_cordic(int(acc_re), int(acc_im))
    return w_from_angle(ang), bool(xm >= cnt * qmin), ang, xm


def auto_sequence(mi2, mq2, first, n, qmin, continuous, n_windows=None):
    """The windows the hardware runs from symbol `first` on: list of dicts (start, cnt, acc_re, acc_im, acc_abs, w, passed, load_at); load_at = the symbol whose S7 loads the frequency.
    Once mode stops after the first window that passes; continuous mode goes on while symbols last (or n_windows)."""
    c, s, mag, valid = E.fe_symbols(mi2, mq2)
    out, start = [], first
    while start + n <= len(c) and (n_windows is None or len(out) < n_windows):
        a = E.window(c, s, mag, valid, start, n)
        w, ok, ang, xm = window_estimate(a[0], a[1], a[3], qmin)
        out.append(dict(start=start, cnt=a[3], acc_re=a[0], acc_im=a[1], acc_abs=a[2], w=w, passed=ok, load_at=start + n, ang=ang))
        if ok and not continuous: break
        start += n
    return out


def loads_of(seq):
    return {q["load_at"]: q["w"] for q in seq if q["passed"]}


def w_hz(w):
    return w / 2 ** 32 * SYMBOL_RATE


if __name__ == "__main__":
    # self-test: the CORDIC against numpy
    rng = np.random.default_rng(1); worst = 0
    for _ in range(2000):
        x, y = int(rng.integers(-2 ** 31, 2 ** 31)), int(rng.integers(-2 ** 31, 2 ** 31))
        ang, xm = atan_cordic(x, y); ref = (np.arctan2(y, x) / (2 * np.pi)) % 1.0 * 2 ** 20
        d = abs(((ang - ref) + 2 ** 19) % 2 ** 20 - 2 ** 19); worst = max(worst, d)
        assert abs(xm / CORDIC_GAIN - np.hypot(x, y)) < 1e-3 * np.hypot(x, y) + 2
    print("CORDIC atan: worst angle error %.2f LSB of 2^-20 turn = %.2f Hz; gain %.5f" % (worst, worst * 2 ** 10 / 2 ** 32 * SYMBOL_RATE, CORDIC_GAIN))
