#!/usr/bin/env python3
import sys
rtl = open("rtl_ofdm_chan.txt").read().split("\n"); exp = open("chan_exp.txt").read().split("\n")
rtl = [l for l in rtl if l.strip()]; exp = [l for l in exp if l.strip()]
n = min(len(rtl), len(exp)); bad = [i for i in range(n) if rtl[i].split() != exp[i].split()]
print("chan: %d lines = %d cases (RTL %d, model %d), %d mismatches" % (n, n // 29, len(rtl), len(exp), len(bad)), [(i // 29, i % 29, rtl[i], exp[i]) for i in bad[:3]])
sys.exit(1 if bad or len(rtl) != len(exp) else 0)
