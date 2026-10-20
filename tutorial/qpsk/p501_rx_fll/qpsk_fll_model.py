#!/usr/bin/env python3
"""Float model of the receiver chain "band-edge FLL -> polyphase matched filter / timing loop -> Costas loop", as in GNU Radio's flowgraph (qpsk_b210_rx.grc):

    ADC samples (3.84 MSPS) -> FLL band-edge (derotate by an NCO, two 55-tap band-edge filters on the derotated signal, error = power difference, loop filter)
    -> polyphase clock sync + AGC (the engine of qpsk_rx.v)  -> Costas loop -> decisions

The FLL is GNU Radio's fll_band_edge_cc (taps from fll_taps.npz, captured from the block itself) with ONE difference chosen for the FPGA: the error and the loop update happen once per
symbol (every 4 samples) instead of once per sample, and the error is normalised, e = (P_lower - P_upper) / (P_lower + P_upper), so that the loop gain does not depend on the amplitude
(GNU Radio puts an AGC in front of the FLL; here the FLL sees the raw ADC samples).   `run_fll` returns the derotated samples and the FLL's frequency history.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
_t = np.load(os.path.join(HERE, "fll_taps.npz"))
TAPS_U, TAPS_L = _t["upper"], _t["lower"]                    # as GNU Radio prints them: dot product with the last 55 samples in time order (oldest first)
SPS, FS = 4, 3.84e6


def run_fll(x, gp=0.1, gi=0.01, norm="exact", n_sym=None, f0=0.0, narrow_after=None, gi_narrow=None, gp_narrow=None):
    """x: complex ADC samples. Loop: y = x e^{j phi};  every symbol: e = normalised (P_L - P_U);  fr += gi e;  phi += gp e   (fr in rad/sample, phi in rad).
    gp, gi: proportional and integral gain of the loop (rad per unit error). Returns (y, fr_hz history per symbol, e history)."""
    n = len(x) // SPS if n_sym is None else n_sym
    y = np.zeros(n * SPS, dtype=complex); phi = 0.0; fr = 2 * np.pi * f0 / FS
    fh = np.zeros(n); eh = np.zeros(n)
    j = np.arange(SPS)
    for k in range(n):
        seg = x[k * SPS:(k + 1) * SPS]
        y[k * SPS:(k + 1) * SPS] = seg * np.exp(1j * (phi + fr * j)); phi += fr * SPS
        if k * SPS + SPS >= 55:
            w = y[k * SPS + SPS - 55:k * SPS + SPS]
            pu = abs(np.dot(TAPS_U, w)) ** 2; pl = abs(np.dot(TAPS_L, w)) ** 2
            if norm == "exact": e = (pl - pu) / (pl + pu + 1e-12)
            elif norm == "shift":                                       # divide by the power of two just below the sum (no divider in hardware)
                s = pl + pu; e = (pl - pu) / (2.0 ** np.floor(np.log2(s + 1e-12))) / 2 if s > 0 else 0.0
            else: e = (pl - pu)
            g_i, g_p = (gi_narrow, gp_narrow) if (narrow_after is not None and k >= narrow_after) else (gi, gp)
            fr += g_i * e; phi += g_p * e
            eh[k] = e
        fh[k] = fr * FS / (2 * np.pi)
        phi = (phi + np.pi) % (2 * np.pi) - np.pi
    return y, fh, eh
