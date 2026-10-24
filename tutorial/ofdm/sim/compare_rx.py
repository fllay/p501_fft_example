#!/usr/bin/env python3
"""Compare rtl_ofdm_rx.txt with the model (frame_<n>.txt).   python3 compare_rx.py 1"""
import sys
name = sys.argv[1]
exp = {}; 
for l in open("frame_%s.txt" % name):
    t = l.split(); exp[(t[0], t[1])] = t[2:]
rtl = {}; axi = {}
for l in open("rtl_ofdm_rx.txt"):
    t = l.split()
    if t[0] == "AXI": axi[t[1]] = t[2:]
    else: rtl[(t[0], t[1])] = t[2:]
bad = 0
for key, e in exp.items():
    r = rtl.get(key)
    if key[1] == "Z":
        if r is None: print("missing", key); bad += 1; continue
        n = min(len(r), len(e) + 0); mism = sum(1 for a, b in zip(r[:len(e)], e) if a != b)
        print("%s Z: %d values, %d mismatches" % (key[0], len(e), mism)); bad += mism != 0
    elif key[1] == "H": pass
    else:
        ok = r is not None and r == e; print("%s %-8s RTL %s model %s %s" % (key[0], key[1], r, e, "ok" if ok else "MISMATCH")); bad += not ok
# the second frame from the AXI registers (the registers hold the last frame)
fr = int(axi["r9"][0]); print("AXI: frames %s found %s rejected %s bad %s id %s" % (axi["r9"][0], axi["r10"][0], axi["r11"][0], axi["r12"][0], axi["id"][0]))
H2 = exp.get(("F%d" % fr, "H"))
if H2 is not None:
    Hax = axi["H"]; sat = lambda v: max(-32768, min(32767, int(v))); mism = sum(1 for a, b in zip(Hax, H2) if int(a) != sat(b)); print("H over AXI against the model (frame %d): %d mismatches of %d" % (fr, mism, len(H2))); bad += mism != 0
Z2 = exp.get(("F1", "Z")); cap = axi["CAP"]                      # the capture was armed once, before the first frame
if Z2 is not None:
    sat = lambda v: max(-32768, min(32767, int(v))); mism = sum(1 for a, b in zip(cap, Z2[:2048]) if int(a) != sat(b)); print("capture RAM over AXI against the model (frame 1, armed once): %d mismatches of %d" % (mism, len(cap))); bad += mism != 0
for reg, key in (("r24", "s0"), ("r25", "w_c"), ("r26", "w_f"), ("r28", "gain"), ("r16", "sym_cnt"), ("r17", "sym_err"), ("r18", "bit_err")):
    e = exp.get(("F%d" % fr, key)); 
    sg = lambda v: v - (1 << 32) if v >= 1 << 31 else v
    if e is not None and sg(int(axi[reg][0])) != int(e[0]): print("AXI %s = %s, model %s: MISMATCH" % (reg, axi[reg][0], e[0])); bad += 1
print("RESULT:", "all equal" if not bad else "%d problems" % bad); sys.exit(1 if bad else 0)
