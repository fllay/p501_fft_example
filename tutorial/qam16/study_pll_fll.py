#!/usr/bin/env python3
"""FLL tracking gain (or hold) against the PLL loop bandwidth at low SNR: the integer front end after the FLL cold-started on +9.7 kHz, then the float PLL model.
    source tools/gnuradio_env.sh; python3 study_pll_fll.py"""
import numpy as np
import frame16 as F
import qam16_rx_fixed as X
import qpsk_fll_fixed as FL
from framerx_hw import FrameRxHW
from study_pll_lowsnr import ser_ideal, GI_ACQ
from study_pll_variants import measure
from make_signal16 import synth16


def front(snr, seed, gi_trk, nfr=70, cfo=9700, ppm=10.4, acq_blocks=19200):
    xi, xq, _ = synth16(nfr, snr_db=snr, cfo_hz=cfo, ppm=ppm, seed=seed)
    fe, sy, r = X.receive16(xi, xq, X.regs16(), fll=(GI_ACQ, 0, 0), fll_sched={acq_blocks: (gi_trk, 0)})
    return (fe["mi2"] + 1j * fe["mq2"]) / X.R_UNIT


if __name__ == "__main__":
    snrs = (12, 13, 14, 16)
    flls = [("FLL tracking 0.0003", FL.gains(0.0003)[0]), ("FLL tracking 0.0001", FL.gains(0.0001)[0]), ("FLL tracking 0.00003", FL.gains(0.00003)[0]), ("FLL held (gain 0)", 0)]
    bws = (0.015, 0.02, 0.03, 0.04, 0.06)
    print("(SER / bad frames of 120; ideal SER:" + ", ".join("%d dB %.1e" % (s, ser_ideal(s)) for s in snrs) + ")")
    for name, gi in flls:
        streams = {snr: [front(snr, seed, gi) for seed in (1, 2, 3)] for snr in snrs}
        print("\n== " + name)
        print("%-12s" % "PLL bw" + "".join("%20s" % ("%d dB" % s) for s in snrs))
        for bw in bws:
            line = "%-12.3f" % bw
            for snr in snrs:
                ser, bad, nb = measure(streams[snr], dict(word_mode="aided", anchor="first", loop_bw=bw))
                line += "%11.1e / %3d    " % (ser, bad)
            print(line)
