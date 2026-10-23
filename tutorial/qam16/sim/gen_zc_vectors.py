#!/usr/bin/env python3
"""Test vectors for tb_qam_zc_sync.v: symbol streams (mi, mq as int16, unit RMS = 12953) for the synchroniser.
   a: 14 frames, 20 dB, CFO +3 kHz;  b: 10 frames, a gap of 7 frames of noise only, 10 frames (misses, a lost lock, a new lock), 12 dB, CFO -2 kHz;  c: 10 dB, CFO +5 kHz (low SNR);  d: 22 dB, a clock slip of 2 symbols in the middle"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import frame16 as F

R = 12953


def to_int(x):
    return np.clip(np.round(x.real * R), -32768, 32767).astype(np.int64), np.clip(np.round(x.imag * R), -32768, 32767).astype(np.int64)


def make(name):
    if name == "a":
        s, _ = F.make_frames(14, "prbs15"); x = F.channel(s, 20, cfo_hz=3000, lead=137)
    elif name == "b":
        s1, _ = F.make_frames(10, "prbs15"); s2, _ = F.make_frames(10, "prbs15")
        s = np.concatenate([s1, np.zeros(7 * F.FRAME, dtype=complex), s2])
        x = F.channel(s, 12, cfo_hz=-2000, lead=300)
    elif name == "c":
        s, _ = F.make_frames(14, "prbs15"); x = F.channel(s, 10, cfo_hz=5000, lead=500)
    elif name == "d":
        s, _ = F.make_frames(12, "prbs15"); cut = 6 * F.FRAME + 400
        s = np.concatenate([s[:cut], s[cut + 2:]])                                   # two symbols missing (a timing slip)
        x = F.channel(s, 22, cfo_hz=3000, lead=200)
    return to_int(x)


if __name__ == "__main__":
    for name in "abcd":
        mi, mq = make(name)
        with open(os.path.join(HERE, "zc_%s.hex" % name), "w") as f:
            for a, b in zip(mi, mq): f.write("%08x\n" % ((int(b) & 0xFFFF) << 16 | (int(a) & 0xFFFF)))
        np.save(os.path.join(HERE, "zc_mi_%s.npy" % name), mi); np.save(os.path.join(HERE, "zc_mq_%s.npy" % name), mq)
        print(name, len(mi), "symbols")
