#!/usr/bin/env python3
"""NumPy reference receiver for the differential QPSK signal of chapters 4a-4c (960 ksym/s, 4 samples per symbol, RRC 0.35): the structure that goes into the FPGA.

    samples (3.84 MSPS) -> AGC -> polyphase matched filter (NF arms) + derivative filter -> timing loop (Gardner-like error from the two filters)
    -> one sample per symbol -> Costas loop (order 4, 2nd order loop, phase + frequency) -> decisions -> differential decoder -> bits

Both loops are second-order with a proportional gain `alpha` and an integral gain `beta`; `loop_gains(bw)` turns a loop bandwidth (rad per symbol) into the pair,
exactly as GNU Radio's blocks do. They are the registers of the FPGA receiver. Float version; qpsk_rx_fixed.py is the integer model."""
import numpy as np

SPS = 4
BETA_RRC = 0.35
PRE_DIFF = [0, 1, 3, 2]


def rrc_proto(nf, beta=BETA_RRC, span=11):
    """RRC sampled at nf*SPS samples per symbol, span symbols (the prototype of the polyphase bank)."""
    n = span * SPS * nf + 1
    t = (np.arange(n) - (n - 1) / 2) / (SPS * nf)
    h = np.zeros(n)
    for i, x in enumerate(t):
        if abs(x) < 1e-12: h[i] = 1 + beta * (4 / np.pi - 1)
        elif abs(abs(x) - 1 / (4 * beta)) < 1e-9: h[i] = beta / np.sqrt(2) * ((1 + 2 / np.pi) * np.sin(np.pi / (4 * beta)) + (1 - 2 / np.pi) * np.cos(np.pi / (4 * beta)))
        else: h[i] = (np.sin(np.pi * x * (1 - beta)) + 4 * beta * x * np.cos(np.pi * x * (1 + beta))) / (np.pi * x * (1 - (4 * beta * x) ** 2))
    return h


def filter_banks(nf):
    """(matched, derivative) banks: arrays (nf, 44). Arm k holds proto[k + i*nf]; the derivative is the central difference of the prototype."""
    p = rrc_proto(nf); p = p / np.sqrt(np.sum(p ** 2) / nf)                       # unit gain per arm (energy)
    d = np.zeros_like(p); d[1:-1] = (p[2:] - p[:-2]) / 2 * nf                      # derivative in units of 1/sample
    ta = (len(p) - 1) // nf                                                        # taps per arm: span * SPS = 44
    mf = np.array([p[k:k + nf * ta:nf] for k in range(nf)]); dmf = np.array([d[k:k + nf * ta:nf] for k in range(nf)])
    return mf, dmf


def loop_gains(bw, damping=np.sqrt(2) / 2):
    den = 1 + 2 * damping * bw + bw * bw
    return 4 * damping * bw / den, 4 * bw * bw / den                              # alpha, beta


def receive(x, nf=16, timing_bw=2 * np.pi / 400, phase_bw=2 * np.pi / 400, agc=True, init_freq=0.0, max_rate=0.05, ted_sign=1.0, verbose=False):
    """Returns (bits, symbols_after_costas, info). bits: uint8, 2 per symbol, MSB first as GNU Radio's unpack."""
    mf, dmf = filter_banks(nf); ntaps = mf.shape[1]
    ta, tb = loop_gains(timing_bw); ca, cb = loop_gains(phase_bw)
    # AGC at the sample rate: gain tracks |x| towards 1
    y = np.zeros(len(x), dtype=np.complex128)
    if agc:
        g = 1.0
        for n in range(len(x)):
            y[n] = x[n] * g
            g += 5e-3 * (1.0 - abs(y[n])) * (1.0 if g < 1e6 else 0.0)
            g = max(g, 1e-6)
    else:
        y = x.astype(np.complex128)
    # timing: position p in units of 1/nf samples; k = arm, t = sample index of the newest sample of the window
    p = float((ntaps) * nf + nf // 2)                                              # start with a full window, arm nf/2
    rate_f = 0.0
    theta, omega = 0.0, init_freq                                                  # Costas: phase, frequency (rad per symbol)
    syms, bits_out, tims, freqs = [], [], [], []
    prev_idx = 0
    n_sym = 0
    while True:
        t = int(p // nf); k = int(p % nf)
        if t >= len(y): break
        win = y[t - ntaps + 1:t + 1][::-1]                                         # win[i] = y[t - i]
        m = np.dot(mf[k], win); d = np.dot(dmf[k], win)
        e_t = ted_sign * (m.real * d.real + m.imag * d.imag)
        e_t = max(-1.0, min(1.0, e_t))
        rate_f += tb * e_t; rate_f = max(-max_rate * nf, min(max_rate * nf, rate_f))
        p += SPS * nf + rate_f + ta * e_t
        # Costas
        z = m * np.exp(-1j * theta)
        e_c = (1.0 if z.real > 0 else -1.0) * z.imag - (1.0 if z.imag > 0 else -1.0) * z.real
        e_c = max(-1.0, min(1.0, e_c))
        omega += cb * e_c; theta += omega + ca * e_c
        theta = (theta + np.pi) % (2 * np.pi) - np.pi
        syms.append(z); tims.append(rate_f); freqs.append(omega)
        # decision, differential decode, inverse pre-differential map
        idx = {(1, 1): 0, (-1, 1): 1, (-1, -1): 2, (1, -1): 3}[(1 if z.real > 0 else -1, 1 if z.imag > 0 else -1)]
        dd = (idx - prev_idx) % 4; prev_idx = idx
        c = PRE_DIFF[dd] if False else [0, 1, 3, 2][dd]                             # the pre-differential map is its own inverse
        bits_out += [(c >> 1) & 1, c & 1]
        n_sym += 1
    return np.array(bits_out, dtype=np.uint8), np.array(syms), {"rate": np.array(tims) / nf, "freq": np.array(freqs) * 960e3 / (2 * np.pi), "n_sym": n_sym}


def prbs15(n, state=0x7FFF):
    out = np.zeros(n, dtype=np.uint8)
    for i in range(n):
        out[i] = (state >> 14) & 1; state = ((state << 1) & 0x7FFF) | (((state >> 14) ^ (state >> 13)) & 1)
    return out


def count_errors(bits, ref, skip=20000):
    """Bit errors of `bits` against the periodic reference (circular alignment by cross-correlation after `skip` bits)."""
    P = len(ref); b = bits[skip:].astype(np.int8); L = (len(b) // P) * P
    if L < 2 * P: return None
    a = 2.0 * b[:L].reshape(-1, P).mean(axis=0) - 1.0
    cc = np.fft.ifft(np.fft.fft(2.0 * ref - 1.0) * np.conj(np.fft.fft(a))).real; sh = int(np.argmax(np.abs(cc))); inv = cc[sh] < 0
    r = np.roll(ref, -sh); r = 1 - r if inv else r
    err = (b[:L] != r[np.arange(L) % P]); return int(err.sum()), L, err
