#!/usr/bin/env python3
rtl = [tuple(int(t) for t in l.split()) for l in open("rtl_ofdm_fft.txt")]; exp = [tuple(int(t) for t in l.split()) for l in open("fft_exp.txt")]
n = min(len(rtl), len(exp)); bad = [i for i in range(n) if rtl[i] != exp[i]]
print("fft: %d bins in %d transforms (RTL %d, model %d), %d mismatches" % (n, n // 64, len(rtl), len(exp), len(bad)), [(i // 64, i % 64, rtl[i], exp[i]) for i in bad[:3]])
import sys; sys.exit(1 if bad or len(rtl) != len(exp) else 0)
