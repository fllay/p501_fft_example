#!/usr/bin/env python3
"""The band-edge FLL of the FPGA (qpsk_fll_fixed.py, the integer model of rtl/qpsk_fll.v) in front of the 16-QAM receiver: does it bring the natural +9.7 kHz offset of the P501 / B210 pair
(and larger ones) below the 6.5 kHz the Zadoff-Chu word tolerates?
    source tools/gnuradio_env.sh; python3 study_fll16.py"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "qpsk", "p501_rx_fll"))
import qpsk_fll_fixed as FL
import frame16 as F
import qam16_rx_fixed as X
from make_signal16 import synth16


def run(cfo, nfr=100, snr=22, gi_acq=0.002, gi_trk=0.0003, acq_blocks=3000, acq_symbols=8000, use_fll=True):
    xi, xq, ids = synth16(nfr, snr_db=snr, cfo_hz=cfo)
    if use_fll:
        ga, _ = FL.gains(gi_acq); gt, _ = FL.gains(gi_trk)
        f = FL.fll_stage(xi, xq, ga, 0, sched={acq_blocks: (gt, 0)})
        yi, yq = f["yi"], f["yq"]; fr = f["fr"]
        res = cfo + FL.fr_hz(fr)                                              # the offset left (the FLL derotates by -f)
        st = len(fr) // 2
        resid = (res[st:].mean(), res[st:].std(), np.abs(res[st:]).max())
    else:
        yi, yq, resid = xi, xq, (cfo, 0.0, abs(cfo))
    regs = X.regs16(acq_symbols=acq_symbols)
    fe, sy, r = X.receive16(yi, yq, regs)
    fe_ = np.array(r.frame_errs); skip = 15
    return resid, r, fe_


if __name__ == "__main__":
    print("%-10s %-6s | residual offset after the FLL (mean / std / max |.|) | locks frames  bad  first clean  SER after 15 frames" % ("CFO Hz", "FLL"))
    for cfo in (3000, 9700, -9700, 20000, 40000, -60000):
        for use in ((False, True) if abs(cfo) <= 9700 else (True,)):
            resid, r, fe_ = run(cfo, use_fll=use)
            ser_ss = fe_[15:].sum() / max((len(fe_) - 15) * F.N_PAY, 1) if len(fe_) > 15 else float("nan")
            fc = next((i for i, v in enumerate(r.frame_errs) if v == 0), -1)
            print("%-10d %-6s | %+7.0f / %5.0f / %6.0f Hz                       | %d  %3d  %3d  %3d   %.1e" % (cfo, "on" if use else "off", resid[0], resid[1], resid[2], r.locks, r.frames, r.bad_frames, fc, ser_ss))
