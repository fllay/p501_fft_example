#!/usr/bin/env python3
"""Regression of FrameRxHW against the handoff's FrameRx on the handoff's own test matrix (ref/gnuradio/test_blocks.py: 60 frames, fixed numpy payload, 250 ksym/s so that the CFO / Rs is the same),
for several configurations of the hardware model.   source tools/gnuradio_env.sh; python3 test_regression.py"""
import numpy as np
import frame16 as F
from framerx_ref import R
from framerx_hw import FrameRxHW

MATRIX = [(40, 0), (30, 1500), (25, -1500), (20, 1900), (18, 800), (15, -800), (12, 0), (30, 2400)]
CONFIGS = {
    "HW-A like FrameRx (pow, exact, freeze, anchor every, amp word)": dict(norm="pow", approx=False, word_mode="freeze", anchor="every", amp_mode="word"),
    "HW-B mag+approx, freeze, every, agc": dict(norm="mag", approx=True, word_mode="freeze", anchor="every", amp_mode="agc"),
    "HW-C mag+approx, aided, first, agc": dict(norm="mag", approx=True, word_mode="aided", anchor="first", amp_mode="agc"),
    "HW-D mag+approx, aided, every, agc": dict(norm="mag", approx=True, word_mode="aided", anchor="every", amp_mode="agc"),
}


def main(nfr=60):
    s, ids = F.make_frames(nfr, "numpy", seed=1)
    ref = ids[0]
    print("%-14s | %-30s | %s" % ("SNR dB / CFO", "FrameRx: frames locks SER evm", " | ".join(k.split(" ")[0] for k in CONFIGS)))
    for snr, df in MATRIX:
        x = F.channel(s, snr, cfo_hz=df, rs=250e3)
        rx = R.FrameRx(check_payload=True, seed=1)
        for i in range(0, len(x), 1000): rx.push(x[i:i + 1000])
        line = "%3d / %+6d Hz | %3d %2d %.1e %6.1f dB    " % (snr, df, rx.frames, rx.lock_count, rx.sym_err / max(rx.sym_cnt, 1), rx.evm_db)
        for name, kw in CONFIGS.items():
            r = FrameRxHW(**kw).run(x, ref_idx=ref)
            line += "| %3d %d %.1e %5.1f " % (r.frames, r.locks, r.sym_err / max(r.sym_cnt, 1), np.mean(r.evm) if r.evm else float("nan"))
        print(line)


if __name__ == "__main__":
    main()
