#!/usr/bin/env python3
"""Offline study of the synchroniser: synthetic frames through the integer receiver model and the sync model: detections, false alarms, frequency estimate, payload BER.
    python3 study_sync.py"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "p501_rx"))
import qpsk_rx_fixed as F, qpsk_sync_fixed as S
from make_frame_signal import synth_frames
PL = 192; FL = 64 + PL


def run(n_samples=60000, **kw):
    xi, xq = synth_frames(n_samples, pl=PL, **kw); r = F.receive_fixed(xi, xq)
    s = S.run_sync(r["mi2"], r["mq2"], FL, PL); bits = r["bits"]
    nb, nm = S.gated_checker(bits, s["gate"])
    return r, s, nb, nm

if __name__ == "__main__":
    r, s, nb, nm = run()
    st = s["stats"]; pk = np.array(s["peaks"])
    print("frames in %d symbols: %.1f;  peaks %d, hits %d, miss %d, false %d, lock %d, lost %d" % (len(r["mi2"]), len(r["mi2"]) / FL, st["n_det"], st["n_hit"], st["n_miss"], st["n_false"], st["n_lock"], st["n_lost"]))
    print("peak spacing (symbols):", sorted(set(np.diff(pk).tolist())))
    print("payload gate open for %d symbols; checked bits %d, mismatches %d" % (int(s["gate"].sum()), nb, nm))
    print("frequency from the correlation at the peaks: %+.0f Hz (true +9700)" % np.mean([S.freq_hz(s["cre"][p], s["cim"][p]) for p in pk[1:]]))
    for snr in (20, 12, 9, 6, 3, 0):
        out = []
        for seed in (1, 2, 3):
            r, s, nb, nm = run(snr_db=snr, seed=seed); st = s["stats"]
            out.append((st["n_det"], st["n_hit"], st["n_miss"], st["n_false"], st["n_lost"], nb, nm))
        print("SNR %3d dB: " % snr + "  |  ".join("det %2d hit %2d miss %2d false %2d lost %d bits %5d mism %4d" % o for o in out))
