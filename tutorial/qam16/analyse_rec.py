#!/usr/bin/env python3
"""The recordings of test_b210_record.py through the integer model of the FPGA receiver (FLL cold start, front end, ZC sync, PLL): the quality of the B210's own transmission with the best receiver we have.
    source tools/gnuradio_env.sh; python3 analyse_rec.py /tmp/qam16_rec_keep/rec_tx*.c64 [seconds]"""
import sys, glob, re
import numpy as np
import qam16_rx_fixed as X
import frame16 as F
from study_pll_lowsnr import GI_ACQ
GI_TRK = X.FL.gains(0.0001)[0]
secs = float(sys.argv[-1]) if len(sys.argv) > 2 and re.fullmatch(r"[\d.]+", sys.argv[-1]) else 0.5
files = [f for f in sys.argv[1:] if f.endswith(".c64")]
print("%-26s %-9s %-9s | %-7s %-9s %-8s %-7s" % ("recording", "rms", "peak", "frames", "SER", "EVM dB", "bad"))
for f in files:
    x = np.fromfile(f, dtype=np.complex64)[:int(secs * 3.84e6)].astype(complex)
    rms = np.sqrt(np.mean(np.abs(x) ** 2)); peak = np.abs(x).max()
    y = x / rms * 100.0                                                  # ADC counts at an RMS of 100 (what the P501 sees)
    xi, xq = np.clip(np.round(y.real), -2047, 2047).astype(np.int64), np.clip(np.round(y.imag), -2047, 2047).astype(np.int64)
    fe, sy, r = X.receive16(xi, xq, X.regs16(), fll=(GI_ACQ, 0, 0), fll_sched={19200: (GI_TRK, 0)})
    fe_ = np.array(r.frame_errs); k = min(30, len(fe_) // 2)
    print("%-26s %-9.3f %-9.3f | %-7d %-9.2e %-8.1f %-7d" % (f.split("/")[-1], rms, peak, len(fe_), fe_[k:].sum() / max((len(fe_) - k) * F.N_PAY, 1), float(np.mean(r.evm[k:])) if len(r.evm) > k else float("nan"), int(np.sum(fe_[k:] * 5 > F.N_PAY))), flush=True)
