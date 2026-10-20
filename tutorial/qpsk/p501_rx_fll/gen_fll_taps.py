#!/usr/bin/env python3
"""Captures the band-edge filter taps that GNU Radio's digital.fll_band_edge_cc designs (samples per symbol 4, roll-off 0.35, 55 taps) into fll_taps.npz.
The block only prints them (print_taps), so the program runs itself once more with the output captured."""
import os, re, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) > 1 and sys.argv[1] == "--print":
    from gnuradio import digital
    digital.fll_band_edge_cc(4, 0.35, 55, 2 * np.pi / 400).print_taps()
else:
    out = subprocess.run([sys.executable, __file__, "--print"], capture_output=True, text=True)
    txt = out.stdout + out.stderr
    up = txt.split("Upper Band-edge:")[1].split("Lower Band-edge:")[0]; lo = txt.split("Lower Band-edge:")[1]
    num = lambda s: np.array([complex(float(a), float(b)) for a, b in re.findall(r"([-+]?\d\.\d+e[-+]\d+) \+ ([-+]?\d\.\d+e[-+]\d+)j", s)])
    u, l = num(up), num(lo)
    assert len(u) == len(l) == 55, (len(u), len(l))
    np.savez(os.path.join(HERE, "fll_taps.npz"), upper=u, lower=l)
    print("55 taps each saved to fll_taps.npz;  sum of the upper taps (DC gain) %.4f, centre tap %s" % (abs(u.sum()), np.round(u[27], 5)))
