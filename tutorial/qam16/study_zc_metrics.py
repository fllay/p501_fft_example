#!/usr/bin/env python3
"""Numbers behind PLAN_QAM16.md (numpy only, no GNU Radio): the ZC word of the handoff (63 symbols, root 1, CP 8, 14 x (63 16-QAM + 1 pilot)) at 1 sample per symbol.

  E1  detection metric at the true peak and the largest false value in the same frame, for the normalisations rho_pow = |C| / sqrt(63 sum|x|^2) (FrameRx) and rho_mag = |C| / sum|x| (no square root),
      and for an exact, 8-phase and 4-phase quantised reference (multiplier-free correlator), with CFO and noise
  E2  carrier frequency from the word: arg(C2 conj C1) / 32, C1 = taps 0..30, C2 = taps 32..62
  E3  correlation loss from the CFO alone

    python3 study_zc_metrics.py
"""
import numpy as np
N, ROOT, NCP, NBLK, ND = 63, 1, 8, 14, 63
FRAME = NCP + N + NBLK*(ND+1); RS = 960e3
n = np.arange(N); ZC = np.exp(-1j*np.pi*ROOT*n*(n+1)/N)
G = np.array([-3,-1,3,1])/np.sqrt(10); PIL = np.array([1,1,-1,1,-1,-1,1,1,1,-1,-1,1,-1,1.])
rng = np.random.default_rng(5)
def frames(nf):
    out = []
    for _ in range(nf):
        k = rng.integers(0,16,NBLK*ND); d = (G[k>>2] + 1j*G[k&3]).reshape(NBLK, ND)
        pay = np.concatenate([d, PIL[:,None].astype(complex)], 1).reshape(-1)
        out.append(np.concatenate([ZC[-NCP:], ZC, pay]))
    return np.concatenate(out)
def quant(ph_levels):
    a = np.angle(ZC); q = np.round(a/(2*np.pi/ph_levels))*(2*np.pi/ph_levels); return np.exp(1j*q)
refs = {"exact": ZC, "16-phase": quant(16), "8-phase": quant(8), "4-phase": quant(4)}
def metrics(x, ref):
    c = np.abs(np.correlate(x, ref, "valid"))
    e1 = np.concatenate([[0], np.cumsum(np.abs(x))]); s1 = e1[N:] - e1[:-N]
    e2 = np.concatenate([[0], np.cumsum(np.abs(x)**2)]); s2 = e2[N:] - e2[:-N]
    return c/np.sqrt(N*s2 + 1e-20), c/(s1 + 1e-20)      # rho_pow (FrameRx), rho_mag (sum |x|)
nf = 200
print("== E1: detection metrics at the true peak and the largest false value in the same frame (200 frames); CFO in Hz at 960 ksym/s")
print("%-9s %5s %6s | %-24s | %-24s" % ("ref", "SNR", "CFO", "rho_pow: peak mean/min | max other", "rho_mag: peak mean/min | max other"))
for ref_name in ("exact", "8-phase", "4-phase"):
    for snr, cfo in ((20, 0), (20, 3000), (15, 3000), (12, 3000), (15, 6000)):
        x0 = frames(nf); t = np.arange(len(x0))
        x = x0*np.exp(2j*np.pi*cfo/RS*t)*np.exp(1j*0.7)
        x = x + np.sqrt(10**(-snr/10)/2)*(rng.normal(size=len(x)) + 1j*rng.normal(size=len(x)))
        rp, rm = metrics(x, refs[ref_name])
        pk = np.arange(nf)*FRAME + NCP       # word starts after the CP
        res = []
        for r in (rp, rm):
            pv = np.array([r[p-0] for p in pk[:-1]]); oth = []
            for f in range(nf-1):
                seg = r[f*FRAME: (f+1)*FRAME].copy(); seg[NCP-1:NCP+2] = 0; oth.append(seg.max())
            res.append((pv.mean(), pv.min(), np.max(oth), np.mean(oth)))
        print("%-9s %4ddB %6d | %.3f / %.3f | %.3f (mean %.3f) | %.3f / %.3f | %.3f (mean %.3f)" % (ref_name, snr, cfo, res[0][0], res[0][1], res[0][2], res[0][3], res[1][0], res[1][1], res[1][2], res[1][3]))
print("\n== E2: carrier frequency from the word: arg(C2 conj C1)/32, C1 = taps 0..30, C2 = taps 32..62 (exact ref), std over 2000 words")
for snr in (25, 20, 15, 12, 10):
    for cfo in (3000, -6000):
        k = rng.integers(0,16,(2000,)); est = []
        for i in range(2000):
            t = np.arange(N); w = ZC*np.exp(2j*np.pi*cfo/RS*t + 1j*rng.uniform(0,6.28))
            w = w + np.sqrt(10**(-snr/10)/2)*(rng.normal(size=N) + 1j*rng.normal(size=N))
            z = w*np.conj(ZC); c1 = z[:31].sum(); c2 = z[32:].sum()
            est.append(np.angle(c2*np.conj(c1))/32/(2*np.pi)*RS)
        est = np.array(est); print("SNR %2d dB CFO %+6d Hz: mean %+8.1f  std %6.1f Hz" % (snr, cfo, est.mean(), est.std()))
print("\n== E3: correlation loss (exact ref, clean) from CFO alone: |sin(pi f N T)/(N sin(pi f T))|")
for f in (1000, 2000, 3000, 4000, 5000, 7600, 9700):
    print("  %5d Hz: %.3f (%.1f dB)" % (f, abs(np.sin(np.pi*f*N/RS)/(N*np.sin(np.pi*f/RS))), 20*np.log10(abs(np.sin(np.pi*f*N/RS)/(N*np.sin(np.pi*f/RS))))))
