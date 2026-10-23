#!/usr/bin/env python3
"""The carrier PLL at low SNR (12 to 14 dB): the whole integer receiver (qam16_rx_fixed) with the FLL cold-starting on the natural +9.7 kHz offset like the board (acquiring gain 0.002 for 20 ms, then 0.0003),
SER after the start against Es/N0.   source tools/gnuradio_env.sh; python3 study_pll_lowsnr.py"""
import sys
import numpy as np
from math import erfc, sqrt
import frame16 as F
import qam16_rx_fixed as X
import qpsk_fll_fixed as FL
from make_signal16 import synth16


def q(x): return 0.5 * erfc(x / sqrt(2))
def ser_ideal(snr_db):
    s = 10 ** (snr_db / 10); pa = 1.5 * q(sqrt(s / 5)); return 1 - (1 - pa) ** 2


GI_ACQ, GI_TRK = FL.gains(0.002)[0], FL.gains(0.0003)[0]


def run(snr, nfr=70, cfo=9700, ppm=10.4, regs=None, rx_kw=None, skip=30, seed=1, gi_trk=None):
    xi, xq, ids = synth16(nfr, snr_db=snr, cfo_hz=cfo, ppm=ppm, seed=seed)
    fe, sy, r = X.receive16(xi, xq, regs or X.regs16(), fll=(GI_ACQ, 0, 0), fll_sched={19200: (GI_TRK if gi_trk is None else gi_trk, 0)}, **(rx_kw or {}))
    fe_ = np.array(r.frame_errs)
    n = max(len(fe_) - skip, 1)
    return dict(ser=fe_[skip:].sum() / (n * F.N_PAY) if len(fe_) > skip else float("nan"), bad=int(np.sum(fe_[skip:] * 5 > F.N_PAY)) if len(fe_) > skip else -1, nfr=len(fe_) - skip,
                evm=float(np.mean(r.evm[skip:])) if len(r.evm) > skip else float("nan"), locks=r.locks, r=r)


if __name__ == "__main__":
    print("integer receiver, cold FLL on +9.7 kHz; SER after the start (bad frames of N, EVM) for the FLL tracking gain 0.0003 (what the board used) and 0.0001; ideal 16-QAM SER")
    print("%-8s | %-26s | %-26s | %s" % ("SNR dB", "FLL 0.0003", "FLL 0.0001", "ideal SER"))
    for snr in (10, 11, 12, 13, 14, 16, 18, 20):
        c = run(snr); d = run(snr, gi_trk=FL.gains(0.0001)[0])
        print("%-8d | %.1e (%2d of %2d) %6.1f dB | %.1e (%2d of %2d) %6.1f dB | %.1e" % (snr, c["ser"], c["bad"], c["nfr"], c["evm"], d["ser"], d["bad"], d["nfr"], d["evm"], ser_ideal(snr)))
