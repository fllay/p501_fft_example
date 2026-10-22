#!/usr/bin/env python3
"""Writes the test signals of the RTL simulation: samples_a.hex / xi_a.npy (frames, PL 192, FL 256, 20 dB, +9.7 kHz) and samples_b.hex / xi_b.npy (the same with a gap of 900 symbols:
the lock is lost and found again), samples_c.hex (noisier: 6 dB).     python3 gen_sim_samples.py"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from make_frame_signal import synth_frames

for name, kw in (("a", dict(snr_db=20)), ("b", dict(snr_db=20, gaps=[(6000, 6900)])), ("c", dict(snr_db=6, seed=3))):
    xi, xq = synth_frames(60000, pl=192, f_off_hz=9700, **kw)
    np.save(os.path.join(HERE, "xi_%s.npy" % name), xi); np.save(os.path.join(HERE, "xq_%s.npy" % name), xq)
    with open(os.path.join(HERE, "samples_%s.hex" % name), "w") as f:
        for i, q in zip(xi, xq): f.write("%04x%04x\n" % (int(q) & 0xFFFF, int(i) & 0xFFFF))
    print("wrote samples_%s.hex" % name)
