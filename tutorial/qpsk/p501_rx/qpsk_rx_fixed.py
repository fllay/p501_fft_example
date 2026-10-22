#!/usr/bin/env python3
"""Bit-exact integer model of the FPGA QPSK receiver (rtl/qpsk_rx.v). Same structure as qpsk_rx_model.py (float), with the numbers of the hardware:

  x: int16 I/Q (ADC counts, +-2047)   NF = 16 arms x 44 taps, coefficients int16 (x 2^15)
  MAC:   m = (sum x*cm) >> 11 (24-bit), d = (sum x*cd) >> 11              (Q4: 16 = one ADC count)
  AGC:   m' = clip16((m*g) >> 10), d' likewise; g (Q10, 17 bit) += (MU*(REF - a)) >> 16, a = max(|m'i|,|m'q|) + min/2; REF = 16384 means |z| = 2.0 (as in GNU Radio)
  timing: e = clip((m'i*d'i + m'q*d'q) >> 13);  rate += (TB*e + 2^20) >> 21;  p += (NF*SPS << 16) + rate + ((TA*e) >> 21)     (p, rate in Q16 arms)
  Costas: z = m' * exp(-j theta), theta/omega in turns x 2^32, 1024-entry LUT (Q15); e = sgn(zi)*zq - sgn(zq)*zi, clip +-8191
          omega += (CB*e) >> 8;  theta += omega + ((CA*e) >> 8)
  decide: signs of z -> DQPSK point -> differential decode -> inverse pre-differential map -> 2 bits (MSB first)
The registers (TB, TA, CB, CA, MU, REF, G0, W0, ...) are 32-bit values written by software: regs_from_bw() computes them from loop bandwidths."""
import numpy as np
from qpsk_rx_model import filter_banks, loop_gains

NF, SPS, NTAPS = 16, 4, 44
F_T = 24                                  # fractional bits of the timing gains
SIN_LUT = None


def coefs():
    mf, dmf = filter_banks(NF)
    return np.round(mf * 2 ** 15).astype(np.int64), np.round(dmf * 2 ** 15).astype(np.int64)


def cos_sin_lut():
    k = np.arange(1024); a = 2 * np.pi * k / 1024
    return np.round(np.cos(a) * 32767).astype(np.int64), np.round(np.sin(a) * 32767).astype(np.int64)


def regs_from_bw(timing_bw=2 * np.pi / 400, phase_bw=2 * np.pi / 400, ref=16384, mu=40, g0=1024, init_freq_hz=0.0, max_rate=0.05):
    ta, tb = loop_gains(timing_bw); ca, cb = loop_gains(phase_bw)
    r = dict(TA=int(round(ta * 2 ** F_T)), TB=int(round(tb * 2 ** F_T)),
             CA=int(round(ca * 2 ** 27 / (2 * np.pi))), CB=int(round(cb * 2 ** 27 / (2 * np.pi))),
             MU=int(mu), REF=int(ref), G0=int(g0), W0=int(round(init_freq_hz / 960e3 * 2 ** 32)),
             MAXR=int(round(max_rate * NF * 2 ** 16)))
    return r


def clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def receive_fixed(xi, xq, regs=None, max_symbols=None, omega_loads=None, gains=None):
    """gains: optional (ca, cb): per-symbol arrays of the Costas loop gains that replace the registers CA, CB (the frame synchroniser switches them from the acquisition to the tracking gains). omega_loads: optional {symbol index: value}: the Costas frequency is LOADED with the value at that symbol instead of the integrator update (the frequency estimator of rtl/qpsk_rx_all.v). xi, xq: int arrays (ADC counts). Returns dict of arrays: bits, zi, zq, omega (turns*2^32), rate (Q16 arms), g, e_t, e_c, and mi2, mq2 (the symbols after the AGC, before the derotation: the input of the frequency estimator)."""
    R = regs_from_bw() if regs is None else regs
    cm, cd = coefs(); cos_l, sin_l = cos_sin_lut()
    xi = np.asarray(xi, dtype=np.int64); xq = np.asarray(xq, dtype=np.int64)
    g = R["G0"]; rate = 0; omega = R["W0"]; theta = 0
    p = (NTAPS * NF + NF // 2) << 16
    prev = 0
    out = {k: [] for k in ("bits", "zi", "zq", "omega", "rate", "g", "e_t", "e_c", "mi2", "mq2")}
    n = 0
    while True:
        t = p >> 20; k = (p >> 16) & (NF - 1)
        if t >= len(xi) or (max_symbols is not None and n >= max_symbols): break
        wi = xi[t - NTAPS + 1:t + 1][::-1]; wq = xq[t - NTAPS + 1:t + 1][::-1]          # w[i] = x[t - i]
        mi = clip(int(np.dot(wi, cm[k])) >> 11, -2 ** 23, 2 ** 23 - 1); mq = clip(int(np.dot(wq, cm[k])) >> 11, -2 ** 23, 2 ** 23 - 1)
        di = clip(int(np.dot(wi, cd[k])) >> 11, -2 ** 23, 2 ** 23 - 1); dq = clip(int(np.dot(wq, cd[k])) >> 11, -2 ** 23, 2 ** 23 - 1)
        # AGC
        mi2 = clip((mi * g) >> 10, -32768, 32767); mq2 = clip((mq * g) >> 10, -32768, 32767)
        di2 = clip((di * g) >> 10, -32768, 32767); dq2 = clip((dq * g) >> 10, -32768, 32767)
        ai, aq = abs(mi2), abs(mq2); a = max(ai, aq) + (min(ai, aq) >> 1)
        g = clip(g + ((R["MU"] * (R["REF"] - a)) >> 16), 16, 2 ** 17 - 1)
        # timing loop
        e_t = clip((mi2 * di2 + mq2 * dq2) >> 13, -8191, 8191)
        rate = clip(rate + ((R["TB"] * e_t + (1 << (F_T - 4))) >> (F_T - 3)), -R["MAXR"], R["MAXR"])      # rounded, not floored: a floor is -0.5 LSB per symbol, which runs a narrow loop into its limit
        p += ((NF * SPS) << 16) + rate + ((R["TA"] * e_t) >> (F_T - 3))
        # Costas
        idx = (theta >> 22) & 1023; c, s = cos_l[idx], sin_l[idx]
        zi = clip((mi2 * c + mq2 * s) >> 15, -32768, 32767); zq = clip((mq2 * c - mi2 * s) >> 15, -32768, 32767)
        si = 1 if zi > 0 else -1; sq = 1 if zq > 0 else -1
        e_c = clip(si * zq - sq * zi, -8191, 8191)
        ca_n, cb_n = (R["CA"], R["CB"]) if gains is None else (int(gains[0][n]), int(gains[1][n]))
        omega = omega_loads[n] if (omega_loads and n in omega_loads) else clip(omega + ((cb_n * e_c) >> 8), -2 ** 31, 2 ** 31 - 1)
        theta = (theta + omega + ((ca_n * e_c) >> 8)) & 0xFFFFFFFF
        # decision and decoding
        pt = {(1, 1): 0, (-1, 1): 1, (-1, -1): 2, (1, -1): 3}[(si, sq)]
        cc = [0, 1, 3, 2][(pt - prev) % 4]; prev = pt
        out["bits"] += [(cc >> 1) & 1, cc & 1]
        for key, val in (("zi", zi), ("zq", zq), ("omega", omega), ("rate", rate), ("g", g), ("e_t", e_t), ("e_c", e_c), ("mi2", mi2), ("mq2", mq2)): out[key].append(val)
        n += 1
    return {k: np.array(v, dtype=(np.uint8 if k == "bits" else np.int64)) for k, v in out.items()}
