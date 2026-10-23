#!/usr/bin/env python3
"""How much of the EVM is noise and how much is the same in every frame? The B210 repeats one frame, so the soft symbols of N consecutive frames can be averaged: random noise falls by 3 dB per doubling, a
distortion that is identical in every frame (TX non-linearity, static ISI) does not. python3 analyse_avg.py sim/adc_c1.c64 [sim/adc_c2.c64]"""
import sys
import numpy as np
import qam16_rx_fixed as X
import frame16 as F
from study_pll_lowsnr import GI_ACQ
GI_TRK = X.FL.gains(0.0001)[0]
LV = 4096
inv = {v: k for k, v in F.LEVEL_IDX.items()}
ref = F.prbs15_indices()
ideal = np.array([(inv[i // 4] + 1j * inv[i % 4]) * LV for i in ref], dtype=complex)
for f in sys.argv[1:]:
    x = np.fromfile(f, dtype=np.complex64).astype(complex)
    y = x / np.sqrt(np.mean(np.abs(x) ** 2)) * 100.0
    xi, xq = np.clip(np.round(y.real), -2047, 2047).astype(np.int64), np.clip(np.round(y.imag), -2047, 2047).astype(np.int64)
    fe, sy, r = X.receive16(xi, xq, X.regs16(), fll=(GI_ACQ, 0, 0), fll_sched={19200: (GI_TRK, 0)})
    z = np.array([a + 1j * b for a, b in r.out], dtype=complex)
    n = len(z) // F.N_PAY; z = z[:n * F.N_PAY].reshape(n, F.N_PAY)[30:]
    # a phase slip or a lost frame would poison the average: keep the frames whose symbol decisions are mostly right
    err = np.array([np.mean(np.abs(zz - ideal) > 1.5 * LV) for zz in z]); ok = z[err < 0.3]
    p = np.mean(np.abs(ideal) ** 2)
    print("%s: %d frames used of %d" % (f.split("/")[-1], len(ok), len(z)))
    for N in (1, 2, 4, 8, 16, 32):
        m = len(ok) // N
        if m < 2: break
        a = ok[:m * N].reshape(m, N, -1).mean(axis=1)
        print("   average of %2d frames: EVM %.1f dB  (symbol errors %.1e)" % (N, 10 * np.log10(np.mean(np.abs(a - ideal) ** 2) / p), np.mean(np.abs(a - ideal) > 1.0 * LV)))
