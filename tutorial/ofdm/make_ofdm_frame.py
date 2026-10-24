#!/usr/bin/env python3
"""The OFDM frame for the transmitter DMA (the base design's DAC DMA sends it as a cyclic buffer, 3840 samples = 1 ms at 3.84 MS/s): ofdm_frame.npy, complex samples with the unit-power subcarriers (mean power 28/64).
    python3 make_ofdm_frame.py [out.npy]      then on the board: python3 p501_ofdm_loopback.py ofdm_frame.npy"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ofdm_model as Fm
x, d = Fm.tx_frame(preamble="scu")
np.save(sys.argv[1] if len(sys.argv) > 1 else "ofdm_frame.npy", x.astype(np.complex64)); print("frame of %d samples, power %.4f" % (len(x), np.mean(np.abs(x) ** 2)))
