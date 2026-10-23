#!/usr/bin/env python3
"""Power budget of 16-QAM against QPSK on the B210 -> P501 link: theory (AWGN) and the measured link. python3 link_budget_qam16.py > results_link_budget.txt
Measured link model (two captures of the P501 ADC, B210 gain 76 dB, distance of the live notebook; PLAN_QAM16.md section 16): the error power of the soft symbols, relative to the signal power, is
    EVM(S) = A * (S1 / S)^2 + B        S = received RMS in ADC counts (RX gain 76),  S1 = 137 counts
with A = 0.0115 (fixed floor: about 15 counts rms in the signal band, 8 counts of it is the receiver's thermal noise) and B = 0.013 (-18.9 dB, scales with the signal), fitted to EVM -16.1 dB at 137 counts and -13.5 dB at 84 counts
(prediction for the live notebook at 55 counts: -10.7 dB, measured -10.1 dB). It does NOT reproduce the close-range point (500 counts, -22.7 dB measured, -18.6 dB predicted): the model is indicative."""
import numpy as np
from scipy.special import erfc
Q = lambda x: 0.5 * erfc(x / np.sqrt(2))
db = lambda p: 10 * np.log10(p)
def ser_qpsk(g): return 2 * Q(np.sqrt(g)) - Q(np.sqrt(g)) ** 2                    # g = Es/N0
def ser_16(g): return 3 * Q(np.sqrt(g / 5)) - 2.25 * Q(np.sqrt(g / 5)) ** 2
def need(f, target):
    lo, hi = 0.0, 40.0
    for _ in range(80):
        m = 0.5 * (lo + hi); lo, hi = (m, hi) if f(10 ** (m / 10)) > target else (lo, m)
    return 0.5 * (lo + hi)
A, B, S1 = 0.0115, 0.013, 137.0
evm = lambda S: A * (S1 / S) ** 2 + B
print("1. Theory (AWGN, ideal receiver): Es/N0 needed for a symbol error rate")
print("   SER      QPSK     16-QAM   difference")
for t in (1e-2, 1e-3, 1e-4, 1e-5, 1e-6):
    a, b = need(ser_qpsk, t), need(ser_16, t); print("   %.0e   %5.1f dB  %5.1f dB  %5.1f dB" % (t, a, b, b - a))
print("\n2. The measured link: EVM as a function of the received level (counts rms in the ADC at RX gain 76; 137 counts = the RMS 0.5 capture)")
print("   level   rel. to 137   EVM (model)   QPSK SER (white-noise theory at that SNR)   16-QAM SER: theory / measured")
meas = {137: "1.2e-3", 84: "4.9e-2", 55: "0.18 (live notebook, EVM -10.1)"}
for S in (30, 40, 55, 84, 137, 200, 280, 400):
    g = 1 / evm(S); print("   %4d    %+5.1f dB      %5.1f dB      %.1e                                     %.1e / %s" % (S, db((S / S1) ** 2), db(evm(S)), ser_qpsk(g), ser_16(g), meas.get(S, "-")))
print("\n3. Received level needed (counts rms), model of section 2")
def level(target_evm_db):
    t = 10 ** (target_evm_db / 10)
    return np.sqrt(A * S1 ** 2 / (t - B)) if t > B else float('inf')
rows = [("QPSK  SER 1e-3 (needs EVM -10.3 dB)", -10.3), ("QPSK  SER 1e-5 (EVM -12.9 dB)", -12.9), ("16-QAM SER 1e-3 as measured (EVM -16.1 dB)", -16.1), ("16-QAM EVM -17 dB", -17.0), ("16-QAM EVM -18 dB", -18.0), ("16-QAM EVM -18.8 dB", -18.8), ("16-QAM EVM -20 dB", -20.0)]
ref = level(-10.3)
for n, e in rows:
    L = level(e); print("   %-46s %s   %s" % (n, ("%6.0f counts" % L) if np.isfinite(L) else "   not reachable (floor B = -18.9 dB)", ("%+5.1f dB over QPSK 1e-3" % db((L / ref) ** 2)) if np.isfinite(L) else ""))
print("\n4. What the extra dB mean in range (free space, same antennas): range ratio = 10^(-dB/20)")
for d in (3, 6, 7.8, 9, 12, 15, 20): print("   %4.1f dB more power needed -> range x %.2f" % (d, 10 ** (-d / 20)))
