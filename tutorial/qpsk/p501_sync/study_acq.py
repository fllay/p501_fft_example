#!/usr/bin/env python3
"""Offline study of the HARDWARE ACQUISITION: the Costas frequency loaded from the preamble, the loop gains switched from the acquisition gains to the tracking gains by the tracker.
    python3 study_acq.py        (W0 = 0, no frequency hint; compares: Costas only / load at the first 8 hits, gains switched)"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "p501_rx"))
import qpsk_rx_fixed as F, qpsk_sync_fixed as S
from make_frame_signal import synth_frames
PL = 192; FL = 256


def run(f_off, snr=20, load=1, nload=8, nsw=4, caw_div=100, trk_div=400, seed=1):
    xi, xq = synth_frames(60000, pl=PL, f_off_hz=f_off, snr_db=snr, seed=seed)
    R = F.regs_from_bw(timing_bw=2 * np.pi / trk_div, phase_bw=2 * np.pi / trk_div); W = F.regs_from_bw(phase_bw=2 * np.pi / caw_div)
    r0 = F.receive_fixed(xi, xq, regs=R)                                   # mi2, mq2 do not depend on the Costas loop
    s = S.run_sync(r0["mi2"], r0["mq2"], FL, PL, load=load, nload=nload, nsw=nsw)
    ca = np.where(s["narrow"], R["CA"], W["CA"]); cb = np.where(s["narrow"], R["CB"], W["CB"])
    r = F.receive_fixed(xi, xq, regs=R, omega_loads=s["loads"], gains=(ca, cb))
    nb, nm = S.gated_checker(r["bits"], s["gate"])
    return r, s, nb, nm


if __name__ == "__main__":
    print("%9s | %-34s | %-34s" % ("offset", "Costas only (tracking gains, no load)", "preamble load + gain switch"))
    for f in (0, 5000, 9700, 20000, -30000, 40000, -60000, 80000, -90000, 110000):
        a = run(f, load=0, nsw=0)[2:]; r, s, nb, nm = run(f)
        om = np.median(r["omega"][-2000:]) / 2 ** 32 * 960e3
        print("%+9d | bits %6d mism %6d              | bits %6d mism %6d  omega %+8.0f Hz  lock %s" % (f, a[0], a[1], nb, nm, om, [e[0] for e in s["events"] if e[1] == "lock"][:1]))
