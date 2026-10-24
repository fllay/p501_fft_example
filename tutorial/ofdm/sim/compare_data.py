#!/usr/bin/env python3
import sys
rtl = [l.split() for l in open("rtl_ofdm_data.txt") if l.strip()]; exp = [l.split() for l in open("data_exp.txt") if l.strip()]
n = min(len(rtl), len(exp)); bad = [i for i in range(n) if rtl[i] != exp[i]]
print("data: %d lines = %d cases (RTL %d, model %d), %d mismatches" % (n, n // 1057, len(rtl), len(exp), len(bad)), [(i // 1057, i % 1057, rtl[i], exp[i]) for i in bad[:3]])
sys.exit(1 if bad or len(rtl) != len(exp) else 0)
