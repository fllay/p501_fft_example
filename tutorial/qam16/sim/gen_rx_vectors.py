#!/usr/bin/env python3
"""Test vectors for tb_qam16_rx.v: ADC samples (hex {q, i}), the register values and the symbol counts.   python3 gen_rx_vectors.py
   a: 16 frames, 22 dB, CFO +3 kHz, 10.4 ppm;  b: 12 frames, a gap of 5 silent frames after frame 5 (misses, lost lock, new lock), 22 dB, CFO -2 kHz, 30 ppm, 700 idle symbols in front;
   c: 26 frames, a gap of 4 frames after frame 12 (the acquisition mode ends after 4 hits and starts again at the lost lock), 21 dB, +5.5 kHz, -25 ppm;  d: 18 frames at 15 dB, -6 kHz, 50 ppm (symbol errors, PLL at its limits)"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import qam16_rx_fixed as X
from make_signal16 import synth16

SCEN = dict(a=dict(nfr=16, snr_db=22, cfo_hz=3000, ppm=10.4, lead=0),
            b=dict(nfr=12, snr_db=22, cfo_hz=-2000, ppm=30, lead=700, gap=(5, 5)),
            c=dict(nfr=26, snr_db=21, cfo_hz=5500, ppm=-25, lead=300, gap=(12, 4)),
            d=dict(nfr=18, snr_db=15, cfo_hz=-6000, ppm=50, lead=1200))


def regs_lines(R):
    m = [(0x08, R["TA"]), (0x0C, R["TB"]), (0x10, R["CA"]), (0x14, R["CB"]), (0x18, R["MU"]), (0x1C, R["PREF"]), (0x20, R["G0"]), (0x28, R["MAXR"]),
         (0x2C, R["TAA"]), (0x30, R["TBA"]), (0x34, R["MUA"]), (0x38, R["ACQ"]), (0x3C, 0x901), (0x40, 0x739A), (0x44, 3), (0x48, 4), (0x4C, 3), (0xB8, R["NSW"])]
    return ["%02x %08x" % (a, v & 0xFFFFFFFF) for a, v in m]


if __name__ == "__main__":
    R = X.regs16()
    for name, kw in SCEN.items():
        xi, xq, ids = synth16(**kw)
        with open(os.path.join(HERE, "rx_%s.hex" % name), "w") as f:
            for a, b in zip(xi, xq): f.write("%08x\n" % ((int(b) & 0xFFFF) << 16 | (int(a) & 0xFFFF)))
        open(os.path.join(HERE, "rx_regs.txt"), "w").write("\n".join(regs_lines(R)) + "\n")
        np.save(os.path.join(HERE, "rx_xi_%s.npy" % name), xi); np.save(os.path.join(HERE, "rx_xq_%s.npy" % name), xq)
        print(name, len(xi), "samples")
