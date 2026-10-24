#!/usr/bin/env python3
"""Compare the log of tb_ofdm_sync.v with the integer model (ofdm_fixed.detect_info / metric).   python3 compare_sync.py a"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ofdm_fixed as X
name = sys.argv[1]
hx = [int(l, 16) for l in open("sc_%s.hex" % name).read().split()]
xi = np.array([((v & 0xFFF) ^ 0x800) - 0x800 for v in hx], dtype=np.int64); xq = np.array([(((v >> 16) & 0xFFF) ^ 0x800) - 0x800 for v in hx], dtype=np.int64)
cond, mq, Sr, Si, E = X.metric(xi, xq)
win = [tuple(int(t) for t in l.split()) for l in open("rtl_ofdm_win.txt")]
bad = 0
for n, c, sr, si, e in win:
    if (int(cond[n]) != c) or Sr[n] != sr or Si[n] != si or E[n] != e:
        bad += 1
        if bad < 5: print("window mismatch n=%d rtl (%d %d %d %d) model (%d %d %d %d)" % (n, c, sr, si, e, cond[n], Sr[n], Si[n], E[n]))
print("%s: %d windows compared, %d mismatches" % (name, len(win), bad))
res = [tuple(int(t) for t in l.split()) for l in open("rtl_ofdm_res.txt")]
d = X.detect_info(xi, xq)
if d is None:
    print("model: nothing found; RTL results: %d" % len(res)); sys.exit(0 if not res and not bad else 1)
if not res: print("RTL found nothing, model n0 %d" % d["n0"]); sys.exit(1)
exp = (d["n0"], d["first"], d["last"], d["first"], d["s0"], d["w_c"], d["G"], d["Epk"], d["sr"], d["si"], d["pk"])
r = res[0]; names = ["n0", "first", "last", "pkidx", "s0", "w_c", "G", "Epk", "sr", "si", "pk"]
seg = d["mq"][d["n0"]:d["n0"] + 72]; exp = (d["n0"], d["first"], d["last"], int(np.argmax(seg)), d["s0"], d["w_c"], d["G"], d["Epk"], d["sr"], d["si"], d["pk"])
mism = [(nm, a, b) for nm, a, b in zip(names, r, exp) if a != b]
print("result  RTL:", dict(zip(names, r))); print("        model:", dict(zip(names, exp))); print("RESULT MISMATCHES:", mism if mism else "none")
sys.exit(1 if (bad or mism) else 0)
