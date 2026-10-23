#!/usr/bin/env python3
"""FEC sweeps -> results_fec.txt and fec_curves.png.  python3 fec_run.py [frames]   (needs sim/adc_c1.c64 for the measured error bank)"""
import sys, os, time
import numpy as np
from multiprocessing import Pool
import fec_sim as S
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
frames = int(sys.argv[1]) if len(sys.argv) > 1 else 600
if not os.path.exists(os.path.join(S.HERE, "sim", "eps_c1.npy")): S.make_eps_bank()
schemes = ["uncoded", "conv", "sc", "scl8"]
esn0 = np.arange(2.0, 12.01, 0.5)
levels = np.array([30, 40, 50, 60, 70, 84, 100, 120, 137, 170, 220])
jobs = [(s, "awgn", float(e), frames, 1000 + i) for s in schemes for i, e in enumerate(esn0)] + [(s, "link", float(l), frames, 5000 + i) for s in schemes for i, l in enumerate(levels)]
t = time.time()
with Pool(14) as p: res = p.map(S.run_point, jobs, chunksize=1)
print("sweeps took %.0f s" % (time.time() - t))
tab = {}
for (s, ch, par, _, _), r in zip(jobs, res): tab[(s, ch, par)] = r
def thr(s, ch, params, target, rising=False):
    f = np.array([tab[(s, ch, float(x))][2] for x in params]); x = np.array(params, float)
    ok = np.where(f <= target)[0]
    if len(ok) == 0: return None
    i = ok[0] if not rising else ok[-1]
    if i == 0: return x[0]
    x0, x1, f0, f1 = x[i - 1], x[i], max(f[i - 1], 1e-9), max(f[i], 1e-9)
    return x0 + (np.log(target) - np.log(f0)) / (np.log(f1) - np.log(f0)) * (x1 - x0) if f1 != f0 else x1
out = []
out.append("FEC study: %d frames per point, one codeword per 882-symbol 16-QAM frame (3528 coded bits), K=1758 information bits per frame (rate 0.498), Gray mapping, random bit interleaver\n" % frames)
out.append("== AWGN: frame error rate FER (and uncoded symbol error rate SER) against Es/N0")
out.append("Es/N0 dB   " + "".join("%-10s" % s for s in schemes) + "  SER uncoded")
for e in esn0: out.append("%7.1f    " % e + "".join("%-10.1e" % tab[(s, "awgn", float(e))][2] for s in schemes) + "  %.1e" % tab[("uncoded", "awgn", float(e))][4])
out.append("\nEs/N0 needed for FER 1e-2 / 1e-3 (AWGN):")
for s in schemes:
    out.append("  %-8s  FER 1e-2: %s dB   FER 1e-3: %s dB" % (s, *("%.2f" % v if v is not None else "> %.0f" % esn0[-1] for v in (thr(s, "awgn", esn0, 1e-2), thr(s, "awgn", esn0, 1e-3)))))
out.append("\n== Measured link model (A = 0.0115 fixed floor, B = multiplicative error: the slow part replayed from the ADC capture, the rest of B as white noise): FER against the received level S (ADC counts rms at RX gain 76; 137 = RMS 0.5 capture)")
out.append("level      " + "".join("%-10s" % s for s in schemes) + "  SER uncoded   EVM-ish (dB)")
for l in levels: out.append("%5d      " % l + "".join("%-10.1e" % tab[(s, "link", float(l))][2] for s in schemes) + "  %.1e       %.1f" % (tab[("uncoded", "link", float(l))][4], 10 * np.log10(S.A_FLOOR * (137.0 / l) ** 2 + S.B_MULT)))
out.append("\nReceived level needed (counts rms) for FER 1e-2 / 1e-3 on the link model, and the gain over the uncoded 16-QAM frame (uncoded FER 1e-2 needs SER about 1e-5):")
for s in schemes:
    a, b = thr(s, "link", levels, 1e-2, False) if False else None, None
    fer = np.array([tab[(s, "link", float(l))][2] for l in levels])
    def lv(target):
        ok = np.where(fer <= target)[0]
        if len(ok) == 0: return None
        i = ok[0]
        if i == 0: return float(levels[0])
        l0, l1, f0, f1 = levels[i - 1], levels[i], max(fer[i - 1], 1e-9), max(fer[i], 1e-9)
        return float(l0 + (np.log(target) - np.log(f0)) / (np.log(f1) - np.log(f0)) * (l1 - l0)) if f1 != f0 else float(l1)
    out.append("  %-8s FER 1e-2: %s   FER 1e-3: %s" % (s, *(("%.0f counts (%+.1f dB re 137)" % (v, 20 * np.log10(v / 137)) if v else "not reached to %d counts" % levels[-1]) for v in (lv(1e-2), lv(1e-3)))))
txt = "\n".join(out); print(txt); open(os.path.join(S.HERE, "results_fec.txt"), "w").write(txt + "\n")
fig, ax = plt.subplots(1, 2, figsize=(13, 5))
for s in schemes:
    ax[0].semilogy(esn0, [max(tab[(s, "awgn", float(e))][2], 0.3 / frames) for e in esn0], "o-", label=s)
    ax[1].semilogy(levels, [max(tab[(s, "link", float(l))][2], 0.3 / frames) for l in levels], "o-", label=s)
ax[0].set(xlabel="Es/N0 (dB)", ylabel="frame error rate", title="AWGN, 16-QAM, rate 0.5", ylim=(1e-3, 1.2)); ax[1].set(xlabel="received level (ADC counts rms)", title="measured link model", ylim=(1e-3, 1.2))
for a in ax: a.grid(alpha=0.3, which="both"); a.legend()
fig.savefig(os.path.join(S.HERE, "fec_curves.png"), dpi=110, bbox_inches="tight")
