#!/usr/bin/env python3
"""The OFDM frame for the transmitter DMA (the base design's DAC DMA sends it as a cyclic buffer, 3840 samples = 1 ms at 3.84 MS/s): ofdm_frame.npy, complex samples with the unit-power subcarriers (mean power 28/64).
    python3 make_ofdm_frame.py [out.npy] [sts]      then on the board: python3 p501_ofdm_loopback.py ofdm_frame.npy
With sts: the frame of the 128-sample short training field (STS 128, GI2 32, T1, T2, 44 data symbols, 32 idle: overlay p501_ofdm_rx_sts), default file ofdm_frame_sts.npy."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ofdm_model as Fm
STS = "sts" in sys.argv[1:]; args = [a for a in sys.argv[1:] if a != "sts"]
x, d = Fm.tx_frame(preamble="sts16" if STS else "scu")
np.save(args[0] if args else ("ofdm_frame_sts.npy" if STS else "ofdm_frame.npy"), x.astype(np.complex64)); print("frame of %d samples, power %.4f" % (len(x), np.mean(np.abs(x) ** 2)))
