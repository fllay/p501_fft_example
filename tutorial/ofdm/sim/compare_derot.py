#!/usr/bin/env python3
import sys
rtl = [tuple(int(t) for t in l.split()) for l in open("rtl_ofdm_derot.txt")]; exp = [tuple(int(t) for t in l.split()) for l in open("derot_exp.txt")]
n = min(len(rtl), len(exp)); bad = [(i, rtl[i], exp[i]) for i in range(n) if rtl[i] != exp[i]]
print("derot: %d vectors (RTL %d, model %d), %d mismatches" % (n, len(rtl), len(exp), len(bad)), bad[:4]); sys.exit(1 if bad or len(rtl) != len(exp) else 0)
