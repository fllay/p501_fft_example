#!/usr/bin/env python3
"""Receiver model on an ADC capture of a transmission at a lower symbol rate: python3 analyse_rate.py sim/adc_<tag>.npy <decimation> [seconds]
The P501 samples at 3.84 MS/s; a 480 ksym/s transmission has 8 samples per symbol, so the capture is low-pass filtered and decimated by 2 to the 4 samples per symbol the receiver (and its model) is built for.
decimation 1 = the 960 ksym/s captures. Prints EVM / SER of the model, the in-band signal and noise levels and the same split into a fixed floor and a signal-proportional part as LINK_REPORT_QAM16.md section 5."""
import sys
import numpy as np
from scipy.signal import decimate
import qam16_rx_fixed as X, frame16 as F
from study_pll_lowsnr import GI_ACQ
GI_TRK = X.FL.gains(0.0001)[0]
f, dec = sys.argv[1], int(sys.argv[2]); secs = float(sys.argv[3]) if len(sys.argv) > 3 else 0.42
x = np.load(f).astype(complex); x = x - x.mean()
rms0 = np.sqrt(np.mean(np.abs(x) ** 2))
if dec > 1: x = decimate(x, dec, n=60, ftype="fir", zero_phase=True)
x = x[:int(secs * 3.84e6 / dec)]
rms = np.sqrt(np.mean(np.abs(x) ** 2)); y = x / rms * 100.0
xi, xq = np.clip(np.round(y.real), -2047, 2047).astype(np.int64), np.clip(np.round(y.imag), -2047, 2047).astype(np.int64)
fe, sy, r = X.receive16(xi, xq, X.regs16(), fll=(GI_ACQ, 0, 0), fll_sched={19200: (GI_TRK, 0)})
fe_ = np.array(r.frame_errs); k = min(30, len(fe_) // 3)
print("%s decimation %d: rms %.1f counts (%.1f before filtering), frames %d, EVM %.1f dB, SER %.2e, bad frames %d, locks %d" %
      (f.split("/")[-1], dec, rms, rms0, len(fe_), float(np.mean(r.evm[k:])), fe_[k:].sum() / max((len(fe_) - k) * F.N_PAY, 1), int(np.sum(fe_[k:] * 5 > F.N_PAY)), r.locks))
