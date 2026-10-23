"""List size and design point of the polar code (AWGN, FER against Es/N0), appended to results_fec.txt."""
import numpy as np, time
from multiprocessing import Pool
import fec_sim as S
es = np.arange(6.0, 9.01, 0.25); fr = 1500
schemes = ["sc", "scl2", "scl4", "scl8", "scl16", "scl32", "sc@2.0", "sc@4.0", "scl8@2.0", "scl8@4.0", "scl8@5.0"]
jobs = [(s, "awgn", float(e), fr, 77 + i) for s in schemes for i, e in enumerate(es)]
t = time.time()
with Pool(14) as p: res = p.map(S.run_point, jobs, chunksize=1)
tab = {(j[0], j[2]): r[2] for j, r in zip(jobs, res)}
def thr(s, target):
    f = np.array([tab[(s, float(e))] for e in es]); ok = np.where(f <= target)[0]
    if len(ok) == 0: return None
    i = ok[0]
    if i == 0: return es[0]
    f0, f1 = max(f[i - 1], 1e-9), max(f[i], 1e-9)
    return es[i - 1] + (np.log(target) - np.log(f0)) / (np.log(f1) - np.log(f0)) * (es[i] - es[i - 1]) if f0 != f1 else es[i]
out = ["\n== Polar code: list size and design point (AWGN, %d frames per point, %.0f s)" % (fr, time.time() - t), "Es/N0 dB   " + "".join("%-10s" % s for s in schemes)]
for e in es: out.append("%7.2f    " % e + "".join("%-10.1e" % tab[(s, float(e))] for s in schemes))
out.append("Es/N0 for FER 1e-2:  " + "  ".join("%s %s" % (s, ("%.2f" % thr(s, 1e-2)) if thr(s, 1e-2) else ">9") for s in schemes))
txt = "\n".join(out); print(txt); open("results_fec.txt", "a").write(txt + "\n")
