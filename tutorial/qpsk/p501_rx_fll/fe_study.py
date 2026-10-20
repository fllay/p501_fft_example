#!/usr/bin/env python3
"""The offline study of the frequency estimator (integer model): the real B210 recordings, synthetic offsets, noise, window length.

    source tools/gnuradio_env.sh
    python3 fe_study.py [/tmp/fe_cap80 /tmp/fe_cap70]        # directories with p501_cap.c64 from run_capture_4b.py (optional)
Prints the tables and writes qpsk_fe_study.png (next to the other figures in tutorial/img/)."""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "p501_rx")); sys.path.insert(0, HERE)
import qpsk_rx_fixed as F, qpsk_fe_fixed as E
from make_signal import synth

OUT = os.path.join(HERE, "..", "..", "img", "qpsk_fe_study.png")


def estimates(r, n, start=30000, step=None):
    c, s, mag, v = E.fe_symbols(r["mi2"], r["mq2"]); f, q = [], []
    for st in range(start, len(c) - n, step or n):
        a = E.window(c, s, mag, v, st, n); fh, qq, _ = E.estimate(a[0], a[1], a[3]); f.append(fh); q.append(qq)
    return np.array(f), np.array(q)


def spread_deg(r, skip=3000):
    z = r["zi"] + 1j * r["zq"]; a = (np.angle(z * np.exp(-1j * np.pi / 4)) + np.pi / 4) % (np.pi / 2) - np.pi / 4
    return float(np.degrees(np.std(a[skip:])))


# ---------------------------------------------------------------- 1. the real recordings
rec = {}
for d in sys.argv[1:]:
    p = os.path.join(d, "p501_cap.c64")
    if not os.path.exists(p): continue
    x = np.fromfile(p, dtype=np.complex64) * 2048
    xi, xq = np.round(x.real).astype(np.int64)[:2_000_000], np.round(x.imag).astype(np.int64)[:2_000_000]
    r = F.receive_fixed(xi, xq); om = np.median(r["omega"][len(r["omega"]) // 2:]) / 2 ** 32 * 960e3
    rec[os.path.basename(d)] = (r, om)
    print("== recording %s: ADC rms %.1f counts, constellation spread %.1f deg, Costas OMEGA %+.0f Hz" % (d, np.sqrt(np.mean(xi ** 2 + xq ** 2.0)), spread_deg(r), om))
    Dr, Di, mg, v = E.fe_symbols_d4(r["mi2"], r["mq2"]); a = E.window(Dr, Di, mg, v, 30000, 4096)
    th = np.arctan2(a[1], a[0]); print("   plain d^4 (magnitude weighted), N 4096: %+8.0f Hz   (the unit-magnitude CORDIC version follows)" % (th / (8 * np.pi) * 960e3))
    for n in (128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768):
        f, q = estimates(r, n)
        if len(f) < 3: continue
        print("   N %6d: %3d windows: mean %+8.1f Hz (Costas %+.0f), std %7.1f Hz, quality %.2f" % (n, len(f), f.mean(), om, f.std(), q.mean()))

# ---------------------------------------------------------------- 2. synthetic offsets
print("\n== synthetic offsets, sample SNR 20 dB, N 2048 (the first symbols are skipped: the timing loop has to converge)")
offs = [0, 2500, -2500, 5000, -5000, 10000, -10000, 20000, -20000, 40000, -40000, 80000, -80000, 100000, -100000, 115000, -115000, 125000, -125000]
res_off = []
for f0 in offs:
    xi, xq = synth(60000, f_off_hz=f0, snr_db=20, seed=2); r = F.receive_fixed(xi, xq)
    f, q = estimates(r, 2048, start=4000, step=2048)
    res_off.append((f0, f.mean(), q.mean()))
    print("   true %+8d Hz  estimate %+10.1f Hz  error %+9.1f Hz   quality %.2f   (Costas loop ends at %+9.0f Hz)" % (f0, f.mean(), f.mean() - f0, q.mean(), r["omega"][-1] / 2 ** 32 * 960e3))

# ---------------------------------------------------------------- 3. noise: sample SNR against the estimate
print("\n== synthetic noise sweep, true +9700 Hz: error std (Hz) over windows and 3 seeds")
snrs = [20, 12, 9, 6, 3, 0, -3]
ns = (256, 1024, 4096, 16384)
tab = np.zeros((len(snrs), len(ns))); qual = np.zeros(len(snrs)); spr = np.zeros(len(snrs))
for i, snr in enumerate(snrs):
    errs = {n: [] for n in ns}; qs = []; sp = []
    for seed in (1, 2, 3):
        xi, xq = synth(240000, f_off_hz=9700, snr_db=snr, seed=seed); r = F.receive_fixed(xi, xq); sp.append(spread_deg(r))
        for n in ns:
            f, q = estimates(r, n, start=4000)
            errs[n] += list(f - 9700)
            if n == 4096: qs.append(q.mean())
    qual[i] = np.mean(qs); spr[i] = np.mean(sp)
    for j, n in enumerate(ns): e = np.array(errs[n]); tab[i, j] = np.sqrt(np.mean(e ** 2)) if len(e) else np.nan
    print("   SNR %3d dB (spread %4.1f deg, quality %.2f): " % (snr, spr[i], qual[i]) + "  ".join("N %5d: rms error %7.0f" % (n, tab[i, j]) for j, n in enumerate(ns)))

# ---------------------------------------------------------------- figure
fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
a = np.array(res_off); ax[0].plot(a[:, 0] / 1e3, a[:, 1] / 1e3, "o", color="#33475b", label="estimate"); ax[0].plot([-130, 130], [-130, 130], "--", color="#2a9d4f", lw=1, label="true")
ax[0].axvspan(-130, -120, color="#f3d0d0"); ax[0].axvspan(120, 130, color="#f3d0d0"); ax[0].set_xlabel("true offset (kHz)"); ax[0].set_ylabel("estimate (kHz)"); ax[0].set_title("range: exact up to +-115 kHz, it wraps at +-120 kHz (1/8 of the symbol rate)", fontsize=9); ax[0].legend(); ax[0].grid(alpha=.3)
for j, n in enumerate(ns): ax[1].semilogy(snrs, tab[:, j], "o-", label="N = %d" % n)
ax[1].axhline(500, color="#c0392b", ls=":", lw=1); ax[1].text(19, 620, "500 Hz: enough for the Costas loop", fontsize=8, color="#c0392b", ha="right")
ax[1].set_xlabel("SNR in the 3.84 MHz sample bandwidth (dB)"); ax[1].set_ylabel("rms error (Hz)"); ax[1].set_title("noise: the 4th-power threshold", fontsize=9); ax[1].legend(fontsize=8); ax[1].grid(alpha=.3, which="both")
for name, (r, om) in rec.items():
    ns2 = (128, 256, 512, 1024, 2048, 4096, 8192, 16384); sd = []
    for n in ns2:
        f, q = estimates(r, n); sd.append(f.std() if len(f) > 2 else np.nan)
    ax[2].loglog(ns2, sd, "o-", label="%s (spread %.0f deg)" % (name, spread_deg(r)))
ax[2].loglog([128, 16384], [200, 200 * np.sqrt(128 / 16384)], ":", color="#999", label="1/sqrt(N)")
ax[2].set_xlabel("window length N (symbols)"); ax[2].set_ylabel("std of the estimate (Hz)"); ax[2].set_title("the real B210 recordings: scatter against N", fontsize=9); ax[2].legend(fontsize=8); ax[2].grid(alpha=.3, which="both")
fig.suptitle("Frequency estimator (integer model): range, noise threshold and scatter", fontsize=11, fontweight="bold"); fig.tight_layout(); fig.savefig(OUT, dpi=120)
print("\nfigure:", os.path.normpath(OUT))
