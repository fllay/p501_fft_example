#!/usr/bin/env python3
"""Bit-exact integer model of the FLL stage of rtl/qpsk_fll.v: the band-edge FLL of GNU Radio (digital.fll_band_edge_cc), built for the FPGA.

    ADC samples x (3.84 MSPS) -> [ FLL: y = x e^{j phi} ] -> polyphase matched filter + timing loop + AGC -> Costas loop -> decisions        (the second part is qpsk_rx_fixed.receive_fixed)

The FLL derotates every sample by an NCO (phi, advanced by fr per sample), and once per block of 4 samples (a symbol) it measures the power in the two band-edge filters
(the 55 complex taps of GNU Radio's block, quantised to Q17; the lower filter is the complex conjugate of the upper), forms the normalised power difference and updates the loop:

    U = sum tap_i y_i,  L = sum conj(tap_i) y_i      over the last 55 derotated samples  (4 multiplies per tap give both: A = sum c_r y_r, B = sum c_i y_i, C = sum c_r y_i, D = sum c_i y_r;
                                                     U = (A - B) + j (C + D),  L = (A + B) + j (C - D))
    PU = |U>>6|^2, PL = |L>>6|^2;  e = (PL - PU) / 2^(msb(PL + PU) + 1)   in Q15  (a shift instead of a divider: the gain varies by at most 2 with the level)
    fr += (GI e + 2^14) >> 15;  phi += (GP e + 2^14) >> 15        (turns x 2^32 per sample / per update)
and the update of block k takes effect at the first sample of block k + 2 (so that the hardware has the time for the multiply-accumulate; the model and the RTL agree on this rule).

Units: phi and fr in turns x 2^32 (fr per sample): f_hz = fr / 2^32 x 3.84e6.  GI = round(gi_rad / (2 pi) x 2^32) where gi_rad is the frequency step in rad/sample per unit of e.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "p501_rx"))
from qpsk_rx_fixed import cos_sin_lut, receive_fixed, regs_from_bw

FS, SPS, NTAPS = 3.84e6, 4, 55
TAP_Q, SH_U = 17, 6
FIRST_BLOCK = 13                       # the first block whose window (55 samples) is complete: 4 x 13 + 4 >= 55
LATENCY = 2                            # blocks between a measurement and its effect
COS_L, SIN_L = cos_sin_lut()
_t = np.load(os.path.join(HERE, "fll_taps.npz"))
TAP_R = np.round(_t["upper"].real * 2 ** TAP_Q).astype(np.int64)
TAP_I = np.round(_t["upper"].imag * 2 ** TAP_Q).astype(np.int64)
CLIP_V = 2 ** 23 - 1


def gains(gi_rad, gp_rad=0.0):
    """Register values GI, GP from the loop gains in rad (per unit of the normalised error)."""
    return int(round(gi_rad / (2 * np.pi) * 2 ** 32)), int(round(gp_rad / (2 * np.pi) * 2 ** 32))


def _rnd(v, s):
    return (v + (1 << (s - 1))) >> s


def block_error(yi, yq):
    """e in Q15 for a window of 55 derotated samples (oldest first), plus (PU, PL)."""
    A = int(np.dot(TAP_R, yi)); B = int(np.dot(TAP_I, yq)); C = int(np.dot(TAP_R, yq)); D = int(np.dot(TAP_I, yi))
    ur, ui, lr, li = A - B, C + D, A + B, C - D
    cl = lambda v: max(-CLIP_V, min(CLIP_V, _rnd(v, SH_U)))
    ur, ui, lr, li = cl(ur), cl(ui), cl(lr), cl(li)
    pu = ur * ur + ui * ui; pl = lr * lr + li * li
    s = pu + pl
    if s == 0: return 0, pu, pl
    msb = s.bit_length() - 1
    d = pl - pu
    sh = msb - 14
    e = _rnd(d, sh) if sh > 0 else (d << -sh)
    return max(-32767, min(32767, e)), pu, pl


def fll_stage(xi, xq, GI, GP, F0=0, enable=True, n_blocks=None, sched=None):
    """The FLL on integer samples. sched: {block: (GI, GP)}, new gains from that block on (what the driver does with register writes). Returns dict: yi, yq (int16 range), fr (per block, after the block's samples), e (per block, 0 where no measurement), fr_at (per sample used)."""
    xi = np.asarray(xi, dtype=np.int64); xq = np.asarray(xq, dtype=np.int64)
    nb = len(xi) // SPS if n_blocks is None else n_blocks
    yi = np.zeros(nb * SPS, dtype=np.int64); yq = np.zeros(nb * SPS, dtype=np.int64)
    fr = F0 & 0xFFFFFFFF; phi = 0
    pend = {}                                               # block -> (dfr, dphi) to apply at the start of that block
    fr_h = np.zeros(nb, dtype=np.int64); e_h = np.zeros(nb, dtype=np.int64)
    for k in range(nb):
        if sched and k in sched: GI, GP = sched[k]
        if k in pend:
            dfr, dphi = pend.pop(k); fr = (fr + dfr) & 0xFFFFFFFF; phi = (phi + dphi) & 0xFFFFFFFF
        for j in range(SPS):
            n = k * SPS + j
            idx = ((phi + (1 << 21)) >> 22) & 1023
            c, s = int(COS_L[idx]), int(SIN_L[idx])
            yi[n] = max(-32767, min(32767, _rnd(int(xi[n]) * c - int(xq[n]) * s, 15)))
            yq[n] = max(-32767, min(32767, _rnd(int(xi[n]) * s + int(xq[n]) * c, 15)))
            phi = (phi + fr) & 0xFFFFFFFF
        if k >= FIRST_BLOCK:
            e, _, _ = block_error(yi[k * SPS + SPS - NTAPS:(k + 1) * SPS], yq[k * SPS + SPS - NTAPS:(k + 1) * SPS])
            e_h[k] = e
            if enable:
                dfr = _rnd(GI * e, 15); dphi = _rnd(GP * e, 15)
                pend[k + LATENCY] = (dfr, dphi)
        fr_h[k] = fr - (1 << 32) if fr >= 1 << 31 else fr
    return dict(yi=yi, yq=yq, fr=fr_h, e=e_h)


def receive_fll_fixed(xi, xq, fll_regs, rx_regs=None, max_symbols=None):
    """The whole chain FLL -> polyphase -> Costas: the FLL's dict merged with the receiver's (qpsk_rx_fixed.receive_fixed on the derotated samples)."""
    f = fll_stage(xi, xq, **fll_regs)
    r = receive_fixed(f["yi"], f["yq"], rx_regs, max_symbols)
    r.update(fll_yi=f["yi"], fll_yq=f["yq"], fll_fr=f["fr"], fll_e=f["e"])
    return r


def fr_hz(fr):
    return fr / 2 ** 32 * FS
