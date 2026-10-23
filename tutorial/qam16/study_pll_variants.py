#!/usr/bin/env python3
"""PLL variants on the symbols of the integer front end (FLL cold start on +9.7 kHz, timing loop, AGC): the float PLL model FrameRxHW (framerx_hw.py) with the front end's mi2, mq2.
    source tools/gnuradio_env.sh; python3 study_pll_variants.py"""
import sys
import numpy as np
import frame16 as F
import qam16_rx_fixed as X
from framerx_hw import FrameRxHW
from study_pll_lowsnr import ser_ideal, GI_ACQ, GI_TRK
from make_signal16 import synth16

REF = F.prbs15_indices()


def front(snr, seed, nfr=70, cfo=9700, ppm=10.4):
    xi, xq, _ = synth16(nfr, snr_db=snr, cfo_hz=cfo, ppm=ppm, seed=seed)
    fe, sy, r = X.receive16(xi, xq, X.regs16(), fll=(GI_ACQ, 0, 0), fll_sched={19200: (GI_TRK, 0)})
    return (fe["mi2"] + 1j * fe["mq2"]) / X.R_UNIT


def measure(streams, kw, skip=30):
    se = sc = bad = nb = 0
    for m in streams:
        r = FrameRxHW(**kw).run(m, ref_idx=REF)
        fe = np.array(r.frame_errs)
        if len(fe) <= skip: continue
        se += fe[skip:].sum(); sc += (len(fe) - skip) * F.N_PAY; bad += int(np.sum(fe[skip:] * 5 > F.N_PAY)); nb += len(fe) - skip
    return se / max(sc, 1), bad, nb


if __name__ == "__main__":
    snrs = (12, 13, 14, 16)
    streams = {snr: [front(snr, seed) for seed in (1, 2, 3)] for snr in snrs}
    base = dict(word_mode="aided", anchor="first")
    variants = [("baseline DD bw 0.02", dict()),
                ("DD bw 0.01", dict(loop_bw=0.01)), ("DD bw 0.03", dict(loop_bw=0.03)), ("DD bw 0.04", dict(loop_bw=0.04)),
                ("data weight 0.5, bw 0.02", dict(data_weight=0.5)), ("data weight 0.25, bw 0.03", dict(data_weight=0.25, loop_bw=0.03)),
                ("known only (dw 0), bw 0.02", dict(data_weight=0.0)), ("known only (dw 0), bw 0.05", dict(data_weight=0.0, loop_bw=0.05)), ("known only (dw 0), bw 0.10", dict(data_weight=0.0, loop_bw=0.10)),
                ("known only, bw 0.05, pilot weight 6", dict(data_weight=0.0, loop_bw=0.05, pilot_weight=6)),
                ("DD gated 0.5, bw 0.02", dict(dd_gate=0.5)), ("DD gated 0.7, bw 0.03", dict(dd_gate=0.7, loop_bw=0.03)),
                ("DD gated 0.7 + known, bw 0.04, pw 4", dict(dd_gate=0.7, loop_bw=0.04, pilot_weight=4))]
    print("%-38s" % "variant (SER / bad frames of N)" + "".join("%22s" % ("%d dB (ideal %.0e)" % (s, ser_ideal(s))) for s in snrs))
    for name, kw in variants:
        line = "%-38s" % name
        for snr in snrs:
            ser, bad, nb = measure(streams[snr], dict(base, **kw))
            line += "%12.1e /%3d of%3d" % (ser, bad, nb)
        print(line)
