#!/usr/bin/env python3
"""Whole-frame vectors for ofdm_rx.v (python3 gen_frame_vectors.py [sts]: the 128-sample STS frame, files frame_sts_<n>): frame_<n>.hex (ADC samples {xq[15:0], xi[15:0]}: noise, the frame, noise: 300 + 3840 + 300 samples, and a second frame after it for the continuous mode) and the model's results (frame_<n>.txt).   python3 gen_frame_vectors.py"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ofdm_model as Fm, ofdm_fixed as X
STS = len(sys.argv) > 1 and sys.argv[1] == "sts"; V = X.STS if STS else X.SC; PRE = V["preamble"]; PFX = "frame_sts_" if STS else "frame_"
def echo(amp, delay, ph): t = np.zeros(delay + 1, complex); t[0] = 1.0; t[delay] = amp * np.exp(1j * ph); return t
cases = {"1": dict(snr=26, rms=200, cfo=9700.0, tau=4.3, taps=None, ppm=10.0), "2": dict(snr=20, rms=60, cfo=-15200.0, tau=9.6, taps=echo(0.5, 5, 1.0), ppm=-30.0),
         "3": dict(snr=30, rms=800, cfo=31000.0, tau=0.2, taps=None, ppm=0.0), "4": dict(snr=16, rms=300, cfo=2500.0, tau=11.0, taps=echo(0.8, 8, 0.7), ppm=40.0)}
for name, c in cases.items():
    rng = np.random.default_rng(300 + int(name)); x, d = Fm.tx_frame(preamble=PRE)
    xx = np.concatenate([x, x]); y = Fm.channel(xx, c["snr"], cfo_hz=c["cfo"], tau=c["tau"], ppm=c["ppm"], taps=c["taps"], rng=rng, lead=300, trail=300)
    xi, xq = X.to_adc(y, c["rms"]); n = len(xi)
    open(PFX + "%s.hex" % name, "w").write("\n".join("%08x" % (((int(b) & 0xFFFF) << 16) | (int(a) & 0xFFFF)) for a, b in zip(xi, xq)) + "\n")
    r = X.receive_fixed(xi[:300 + 3840 + 300], xq[:300 + 3840 + 300], var=V)                                                        # the model on the first frame (the samples of the second frame are outside the record)
    B2 = 4100; r2 = X.receive_fixed(xi[B2:], xq[B2:], var=V)
    lines = []
    for tag, rr, base in (("1", r, 0), ("2", r2, B2)):
        si, sq = X.LEVEL(rr["Zr"]), X.LEVEL(rr["Zi"])
        bits = Fm.payload_bits().reshape(44, 24, 4).astype(int); ridx = bits[..., 0] * 8 + bits[..., 1] * 4 + bits[..., 2] * 2 + bits[..., 3]
        gi = np.vectorize(X.GRAY_IDX.get)(si) * 4 + np.vectorize(X.GRAY_IDX.get)(sq)
        sym_err = int(np.sum(gi != ridx)); bit_err = int(sum(bin(int(a) ^ int(b)).count("1") for a, b in zip(gi.ravel(), ridx.ravel())))
        err = int((((rr["Zr"] - si * X.LV) ** 2 + (rr["Zi"] - sq * X.LV) ** 2)).sum()); ref = int(((si ** 2 + sq ** 2) * X.LV * X.LV).sum()); Hr, Hi = rr["H"]
        lines += ["F%s s0 %d" % (tag, base + rr["s0"]), "F%s w_c %d" % (tag, rr["w_c"]), "F%s w_f %d" % (tag, rr["w_f"]), "F%s gain %d" % (tag, rr["G"]), "F%s noise %d" % (tag, rr["noise"]), "F%s sym_cnt %d" % (tag, 44 * 24),
                  "F%s sym_err %d" % (tag, sym_err), "F%s bit_err %d" % (tag, bit_err), "F%s evm_err %d" % (tag, err), "F%s evm_ref %d" % (tag, ref), "F%s H %s" % (tag, " ".join("%d %d" % (a, b) for a, b in zip(Hr, Hi))),
                  "F%s Z %s" % (tag, " ".join("%d %d" % (a, b) for a, b in zip(rr["Zr"].ravel(), rr["Zi"].ravel())))]
    open(PFX + "%s.txt" % name, "w").write("\n".join(lines) + "\n")
    print(name, "samples", n, "frame 1 s0", r["s0"], "frame 2 s0 (abs)", B2 + r2["s0"] if r2 else None)
