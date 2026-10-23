#!/usr/bin/env python3
"""Compares the logs of tb_qam16_rx.v with qam16_rx_fixed.py (front16, qam_zc_fixed.sync, engine16).   python3 compare_rx.py [a|b]"""
import os, re, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import qam16_rx_fixed as X, qam_zc_fixed as Z
name = sys.argv[1] if len(sys.argv) > 1 else "a"
xi, xq = np.load(os.path.join(HERE, "rx_xi_%s.npy" % name)), np.load(os.path.join(HERE, "rx_xq_%s.npy" % name))
R = X.regs16()
fe, sy, res = X.receive16(xi, xq, R, trace=True)
bad = 0
f = np.loadtxt(os.path.join(HERE, "rtl_rx_front.txt"), dtype=np.int64).reshape(-1, 6)
k = min(len(f), len(fe["mi2"])); assert (f[:k, 0] == np.arange(k)).all()
print("  front end: %d symbols in the RTL log, %d in the model" % (len(f), len(fe["mi2"])))
for j, key in ((1, "mi2"), (2, "mq2"), (3, "g"), (4, "rate"), (5, "e_t")):
    mm = int(np.sum(f[:k, j] != fe[key][:k])); bad += mm; print("  front %-4s mismatches %d" % (key, mm))
e = np.loadtxt(os.path.join(HERE, "rtl_rx_engine.txt"), dtype=np.int64).reshape(-1, 8)
tr = np.array(res.trace, dtype=np.int64).reshape(-1, 8)
jmax = e[:, 0].max()
tr = tr[tr[:, 0] <= jmax]
ok = len(e) == len(tr) and np.array_equal(e[:, 0], tr[:, 0])
print("  engine trace: RTL %d symbols, model %d: %s" % (len(e), len(tr), "same symbols" if ok else "DIFFERENT SYMBOLS"))
if not ok: bad += 1
else:
    for c, nm in enumerate(("j", "pos", "kind", "zi", "zq", "e", "omega", "theta")):
        if c == 0: continue
        mm = int(np.sum(e[:, c] != tr[:, c])); bad += mm; print("  engine %-5s mismatches %d" % (nm, mm))
ev = np.loadtxt(os.path.join(HERE, "rtl_rx_events.txt"), dtype=np.int64).reshape(-1, 4)
kd = {"lock": 1, "frame": 2, "lost": 3}
want = [(x["known"] + 2, kd[x["kind"]], x["e"], x["known"]) for x in sy.events if x["known"] + 2 <= f[-1, 0]]
got = [tuple(int(v) for v in r) for r in ev]
okv = got == want; bad += 0 if okv else 1
print("  events applied: RTL %d, model %d: %s" % (len(got), len(want), "identical" if okv else "MISMATCH"))
log = open(os.path.join(HERE, "xsim_rx.log")).read()
vals = {m.group(1): int(m.group(2)) for m in re.finditer(r"^([A-Za-z ]+) = (-?\d+)$", log, re.M)}
ntr = len(tr)
# counters of the model, restricted to the symbols the RTL processed: rerun the engine on the same number of symbols
res2 = X.engine16(fe["mi2"][:f[-1, 0] + 1], fe["mq2"][:f[-1, 0] + 1], Z.sync(fe["mi2"][:f[-1, 0] + 1], fe["mq2"][:f[-1, 0] + 1]), R)
exp = dict(frames=res2.frames, symerr=res2.sym_err, biterr=res2.bit_err, symcnt=res2.sym_cnt, bad=res2.bad_frames, evlate=0, evover=0, sylate=0, nlock=sum(1 for x in sy.events if x["kind"] == "lock" and x["known"] <= f[-1, 0]))
if res2.evm_sums:
    exp["evmlo"] = res2.evm_sums[-1][0] & 0xFFFFFFFF; exp["evmhi"] = res2.evm_sums[-1][0] >> 32; exp["evmref"] = res2.evm_sums[-1][1] // (X.LV * X.LV); exp["frerr"] = res2.frame_errs[-1]
for key, w in exp.items():
    okk = vals.get(key) == w; bad += 0 if okk else 1
    print("  register %-7s RTL %s  model %s  %s" % (key, vals.get(key), w, "ok" if okk else "MISMATCH"))
print("  (frames %d, symbol errors %d of %d, locks %d, hits %d, misses %d, lost %d)" % (vals.get("frames", -1), vals.get("symerr", -1), vals.get("symcnt", -1), vals.get("nlock", -1), vals.get("nhit", -1), vals.get("nmiss", -1), vals.get("nlost", -1)))
print("RESULT:", "MATCH (0 mismatches)" if bad == 0 else "MISMATCH (%d)" % bad)
