#!/usr/bin/env python3
"""Compares the logs of tb_qam_zc_sync.v (rtl_zc_metric.txt, rtl_zc_events.txt, xsim_zc.log) with qam_zc_fixed.sync().   python3 compare_zc.py [a|b|c|d]"""
import os, re, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import qam_zc_fixed as Z
name = sys.argv[1] if len(sys.argv) > 1 else "a"
mi, mq = np.load(os.path.join(HERE, "zc_mi_%s.npy" % name)), np.load(os.path.join(HERE, "zc_mq_%s.npy" % name))
s = Z.sync(mi, mq)
bad = 0
m = np.loadtxt(os.path.join(HERE, "rtl_zc_metric.txt"), dtype=np.int64).reshape(-1, 7)
k = min(len(m), len(s.M)); assert (m[:k, 0] == np.arange(k)).all()
Cr = np.where(np.arange(len(s.M)) >= 62, 0, 0)
# C of the model: recompute from the sums (the model keeps A and D, not C): C = A + B + D is not stored, so compare M, E, cand and the sums A+D+B via M
for j, nm, arr in ((3, "E", s.E), (4, "M", s.M)):
    lo = 62 if nm == "E" else 0                                                       # before the first complete window the RTL's running sum is partial (the candidate flags ignore it)
    mm = int(np.sum(m[lo:k, j] != arr[lo:k])); bad += mm; print("  metric %-2s mismatches %d of %d symbols" % (nm, mm, k - lo))
for j, nm, arr in ((5, "cand_s", s.cand_s), (6, "cand_l", s.cand_l)):
    mm = int(np.sum(m[:k, j] != arr[:k].astype(int))); bad += mm; print("  %-6s mismatches %d" % (nm, mm))
ev = np.loadtxt(os.path.join(HERE, "rtl_zc_events.txt"), dtype=np.int64).reshape(-1, 6)
kind = {"lock": 1, "frame": 2, "lost": 3}
want = [(kind[e["kind"]], e["e"], e["known"], int(e["miss"]), e.get("w", 0), e.get("th0", 0)) for e in s.events if e["known"] < k]
got = [tuple(int(v) for v in r) if r[0] == 1 else tuple(int(v) for v in r[:4]) + (0, 0) for r in ev]             # w, th0 are only valid in a lock event
ok = got == want; bad += 0 if ok else 1
print("  events: RTL %d, model %d: %s" % (len(got), len(want), "identical" if ok else "MISMATCH"))
if not ok:
    for i, (a, b) in enumerate(zip(got, want)):
        if a != b: print("   first difference at event", i, "RTL", a, "model", b); break
print("  first events:", got[:3])
log = open(os.path.join(HERE, "xsim_zc.log")).read()
vals = {m_.group(1): int(m_.group(2)) for m_ in re.finditer(r"^([A-Za-z ]+) = (-?\d+)$", log, re.M)}
nk = lambda kd: sum(1 for e in want if e[0] == kd)
exp = dict(locks=nk(1), lost=nk(3), late=0, evover=0)
for key, w in exp.items():
    okk = vals.get(key) == w; bad += 0 if okk else 1
    print("  register %-6s RTL %s  model %d  %s" % (key, vals.get(key), w, "ok" if okk else "MISMATCH"))
print("RESULT:", "MATCH (0 mismatches)" if bad == 0 else "MISMATCH (%d)" % bad)
