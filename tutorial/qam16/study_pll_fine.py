#!/usr/bin/env python3
"""PLL variants at 10 to 14 dB with the quiet FLL (tracking gain 0.0001): the float PLL on the integer front end's symbols.   python3 study_pll_fine.py"""
import numpy as np
import qam16_rx_fixed as X0
FL = X0.FL
from study_pll_lowsnr import ser_ideal
from study_pll_variants import measure
from study_pll_fll import front

if __name__ == "__main__":
    snrs = (10, 11, 12, 13, 14)
    gi = FL.gains(0.0001)[0]
    streams = {snr: [front(snr, seed, gi) for seed in (1, 2, 3, 4)] for snr in snrs}
    base = dict(word_mode="aided", anchor="first")
    variants = [("baseline bw 0.02", dict()), ("bw 0.015", dict(loop_bw=0.015)), ("bw 0.025", dict(loop_bw=0.025)), ("freeze word", dict(word_mode="freeze")),
                ("pilot weight 1", dict(pilot_weight=1)), ("pilot weight 6", dict(pilot_weight=6)), ("ring PD", dict(pd="ring")), ("gated 0.7", dict(dd_gate=0.7)), ("gated 0.9", dict(dd_gate=0.9)),
                ("data weight 0.5, bw 0.03", dict(data_weight=0.5, loop_bw=0.03)), ("data weight 0.5, pw 6, bw 0.03", dict(data_weight=0.5, loop_bw=0.03, pilot_weight=6))]
    print("%-34s" % "(SER / bad frames of 160)" + "".join("%20s" % ("%d dB (%.0e)" % (s, ser_ideal(s))) for s in snrs))
    for name, kw in variants:
        line = "%-34s" % name
        for snr in snrs:
            ser, bad, nb = measure(streams[snr], dict(base, **kw))
            line += "%11.1e / %3d    " % (ser, bad)
        print(line)
