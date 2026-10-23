#!/usr/bin/env python3
"""Structure of the error of a capture (soft symbols of the receiver model), to compare sessions: python3 analyse_struct.py sim/adc_x.npy ...  -> EVM; EVM after averaging 2/4/8 frames; error vs |s|; frame-to-frame correlation;
and the out-of-band level of the capture's spectrum."""
import sys
import numpy as np
from multiprocessing import Pool
def one(f):
    import qam16_rx_fixed as X, frame16 as F
    from study_pll_lowsnr import GI_ACQ
    gi_trk = X.FL.gains(0.0001)[0]; LV = 4096
    x = np.load(f).astype(complex); x = x - x.mean()
    # spectrum: in band (|f| < 600 kHz) against the shoulder (700 to 1500 kHz) and the floor of the capture
    N = 4096; b = x[:len(x) // N * N].reshape(-1, N) * np.hanning(N); p = np.fft.fftshift((np.abs(np.fft.fft(b, axis=1)) ** 2).mean(axis=0)); fr = np.fft.fftshift(np.fft.fftfreq(N, 1 / 3.84e6))
    inb = 10 * np.log10(np.mean(p[np.abs(fr) < 5e5])); sh = 10 * np.log10(np.mean(p[(np.abs(fr) > 8e5) & (np.abs(fr) < 1.5e6)]))
    rms = np.sqrt(np.mean(np.abs(x) ** 2)); y = x / rms * 100.0
    xi, xq = np.clip(np.round(y.real), -2047, 2047).astype(np.int64), np.clip(np.round(y.imag), -2047, 2047).astype(np.int64)
    fe, sy, r = X.receive16(xi, xq, X.regs16(), fll=(GI_ACQ, 0, 0), fll_sched={19200: (gi_trk, 0)})
    inv = {v: k for k, v in F.LEVEL_IDX.items()}; ideal = np.array([(inv[i // 4] + 1j * inv[i % 4]) * LV for i in F.prbs15_indices()], dtype=complex)
    z = np.array([a + 1j * c for a, c in r.out], dtype=complex); n = len(z) // F.N_PAY; z = z[:n * F.N_PAY].reshape(n, F.N_PAY)[30:]; e = z - ideal; pw = np.mean(np.abs(ideal) ** 2)
    ev = lambda a: 10 * np.log10(np.mean(np.abs(a) ** 2) / pw)
    avg = {N_: ev(z[:len(z) // N_ * N_].reshape(-1, N_, F.N_PAY).mean(axis=1) - ideal) for N_ in (2, 4, 8)}
    mag = np.abs(ideal); rel = [np.sqrt(np.mean(np.abs(e[:, (mag >= lo) & (mag < hi)]) ** 2)) / np.mean(mag[(mag >= lo) & (mag < hi)]) for lo, hi in ((0, 1.5 * LV), (1.5 * LV, 3.5 * LV), (3.5 * LV, 1e9))]
    lag = [np.mean(np.real(e[l:] * np.conj(e[:-l]))) / np.mean(np.abs(e) ** 2) for l in (1, 2, 4, 8)]
    return f.split("/")[-1], rms, ev(e), avg, rel, lag, inb - sh
if __name__ == "__main__":
    with Pool(min(14, len(sys.argv) - 1)) as p: res = p.map(one, sys.argv[1:], chunksize=1)
    print("%-16s level   EVM    avg2   avg4   avg8   | rms error / mean |s| (inner mid outer) | frame lag 1 2 4 8 correlation | in-band over shoulder" % "file")
    for f, rms, e, a, rel, lag, sh in res: print("%-16s %5.0f  %5.1f  %5.1f  %5.1f  %5.1f   | %.3f %.3f %.3f | %+.2f %+.2f %+.2f %+.2f | %.1f dB" % (f, rms, e, a[2], a[4], a[8], *rel, *lag, sh))
