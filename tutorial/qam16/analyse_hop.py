#!/usr/bin/env python3
"""EVM of every capture of the TX-frequency hop test, grouped by the carrier offset found in the capture: python3 analyse_hop.py sim/hop/adc_hop_*.npy"""
import sys, glob
import numpy as np
from multiprocessing import Pool
def one(f):
    import qam16_rx_fixed as X, frame16 as F
    from study_pll_lowsnr import GI_ACQ
    from qam16_frame_tx import one_period
    gi_trk = X.FL.gains(0.0001)[0]
    x = np.load(f).astype(complex); x = x - x.mean()
    r = one_period(1.0).astype(complex); P = len(r); n = np.arange(P); R = np.conj(np.fft.fft(r)); best = (0, 0)
    for fc in np.arange(-20e3, 20e3, 150.0):
        c = np.abs(np.fft.ifft(np.fft.fft(x[:P] * np.exp(-2j * np.pi * fc * n / 3.84e6)) * R))
        if c.max() > best[0]: best = (c.max(), fc)
    # does the carrier stay the same through the capture? coarse estimate in the first and the last periods
    ends = []
    for k in (0, len(x) - P - 1):
        bb = (0, 0)
        for fc in np.arange(-20e3, 20e3, 150.0):
            c = np.abs(np.fft.ifft(np.fft.fft(x[k:k + P] * np.exp(-2j * np.pi * fc * n / 3.84e6)) * R))
            if c.max() > bb[0]: bb = (c.max(), fc)
        ends.append(bb[1])
    rms = np.sqrt(np.mean(np.abs(x) ** 2)); y = x / rms * 100.0
    xi, xq = np.clip(np.round(y.real), -2047, 2047).astype(np.int64), np.clip(np.round(y.imag), -2047, 2047).astype(np.int64)
    fe, sy, rr = X.receive16(xi, xq, X.regs16(), fll=(GI_ACQ, 0, 0), fll_sched={19200: (gi_trk, 0)}); fe_ = np.array(rr.frame_errs); k = 30
    return f.split("/")[-1], best[1], ends, rms, float(np.mean(rr.evm[k:])), fe_[k:].sum() / max((len(fe_) - k) * F.N_PAY, 1), len(fe_), rr.locks
if __name__ == "__main__":
    files = sorted(sum([glob.glob(a) for a in sys.argv[1:]], []))
    with Pool(14) as p: res = p.map(one, files, chunksize=1)
    print("file              carrier offset (start / end of the capture)   level   EVM      SER       frames locks")
    for r in res: print("%-16s  %+7.0f Hz  (%+7.0f / %+7.0f)           %5.1f  %6.1f dB  %.1e  %4d  %d" % (r[0], r[1], r[2][0], r[2][1], r[3], r[4], r[5], r[6], r[7]))
    print()
    for lo, hi, name in ((-3e3, 7e3, "914.995 MHz (+4.7 kHz)"), (7e3, 12e3, "915.000 MHz (+9.7 kHz)"), (12e3, 20e3, "915.005 MHz (+14.7 kHz)")):
        g = [r for r in res if lo <= r[1] < hi and abs(r[2][0] - r[2][1]) < 400]
        if g: print("%-26s %2d captures: EVM mean %.1f dB (min %.1f, max %.1f), level mean %.0f counts, SER mean %.1e" % (name, len(g), np.mean([r[4] for r in g]), min(r[4] for r in g), max(r[4] for r in g), np.mean([r[3] for r in g]), np.mean([r[5] for r in g])))
