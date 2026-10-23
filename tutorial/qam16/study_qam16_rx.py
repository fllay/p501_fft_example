#!/usr/bin/env python3
"""Measurements with FrameRxHW (the items the handoff lists as NOT validated), PRBS-15 payload, 960 ksym/s.   source tools/gnuradio_env.sh; python3 study_qam16_rx.py [detect|false|pd|gain|all]
  detect: probability to lock, lock time (frames), frequency estimate error, against SNR and CFO
  false : false peaks / locks per million symbols on noise and on random 16-QAM data (no word), against the threshold
  pd    : SER against SNR for the phase detectors, pilot weights and word modes, with the ideal coherent 16-QAM SER
  gain  : SER against a gain error of the AGC (the slicer thresholds are fixed)"""
import sys
import numpy as np
from math import erfc, sqrt
import frame16 as F
from framerx_hw import FrameRxHW

RS = F.RS
REF = F.prbs15_indices()


def q(x): return 0.5 * erfc(x / sqrt(2))


def ser_ideal(snr_db):
    s = 10 ** (snr_db / 10); pa = 1.5 * q(sqrt(s / 5)); return 1 - (1 - pa) ** 2


def detect(trials=60, nfr=5):
    print("== detection: %d trials of %d frames, lead-in random 0..966 symbols, thresholds 0.6 / 0.45" % (trials, nfr))
    print("%6s %8s | %-8s %-9s %-14s %-24s %s" % ("SNR", "CFO Hz", "locked", "good lock", "lock (frames)", "frequency error mean / std", "payload SER (good locks)"))
    s, ids = F.make_frames(nfr, "prbs15")
    for snr in (8, 10, 12, 15, 20):
        for cfo in (0, 2000, 4000, 6000, 7600, 9700):
            ok, good, lt, er, sers = 0, 0, [], [], []
            for t in range(trials):
                lead = int(np.random.default_rng(100 + t).integers(0, F.FRAME))
                x = F.channel(s, snr, cfo_hz=cfo, lead=lead, seed=1000 + t, phase=0.3 * t)
                r = FrameRxHW().run(x, ref_idx=REF)
                if r.locks and r.lock_om:
                    ok += 1; lt.append((r.lock_starts[0] + F.FRAME) / F.FRAME); er.append(r.lock_om[0] / (2 * np.pi) * RS - cfo)
                    ser = r.sym_err / max(r.sym_cnt, 1)
                    if (r.lock_starts[0] - lead - F.N_CP) % F.FRAME == 0 and abs(er[-1]) < 2000: good += 1; sers.append(ser)   # "good lock": on the true word start and a sane frequency (a lock one symbol off, from a CFO beyond the limit, is wrong in both)
            print("%4d dB %8d | %3d/%-3d  %3d/%-3d   %-14s %-26s %s" % (snr, cfo, ok, trials, good, trials, ("%.2f" % np.mean(lt)) if lt else "-",
                  ("%+7.0f / %5.0f Hz" % (np.mean(er), np.std(er))) if er else "-", ("%.1e" % np.mean(sers)) if sers else "-"))


def false(n=2_000_000):
    print("== false peaks per million symbols (local maxima of rho above the threshold) and locks (two peaks one frame apart), %d symbols" % n)
    rng = np.random.default_rng(7)
    sig = {"noise": (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2),
           "random 16-QAM": F.qam(rng.integers(0, 16, n)) + 0j,
           "16-QAM, 15 dB noise": F.qam(rng.integers(0, 16, n)) + 10 ** (-15 / 20) * (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)}
    for norm in ("mag", "pow"):
        for name, x in sig.items():
            m = FrameRxHW(norm=norm); rho, mm = m.metric(x)
            line = "norm %-3s %-20s:" % (norm, name)
            for thr in (0.45, 0.5, 0.55, 0.6, 0.65):
                line += "  thr %.2f: %6.1f peaks" % (thr, len(m.peaks(rho, mm, thr)) / n * 1e6)
            r = FrameRxHW(norm=norm).run(x)
            print(line + "   | locks at 0.6/0.45: %d" % r.locks)


def pd_study(nfr=300):
    print("== SER against SNR, CFO 3 kHz, %d frames (%d symbols) per point; ideal coherent 16-QAM SER in the last column; bad = frames with > 20 %% symbol errors" % (nfr, nfr * F.N_PAY))
    s, ids = F.make_frames(nfr, "prbs15")
    variants = [
        ("plain pw3 freeze/every", dict(pd="plain", pilot_weight=3, word_mode="freeze", anchor="every")),
        ("plain pw3 aided/first", dict(pd="plain", pilot_weight=3, word_mode="aided", anchor="first")),
        ("plain pw3 aided/every", dict(pd="plain", pilot_weight=3, word_mode="aided", anchor="every")),
        ("plain pw1 aided/first", dict(pd="plain", pilot_weight=1, word_mode="aided", anchor="first")),
        ("plain pw5 aided/first", dict(pd="plain", pilot_weight=5, word_mode="aided", anchor="first")),
        ("ring  pw3 aided/first", dict(pd="ring", pilot_weight=3, word_mode="aided", anchor="first")),
        ("corner pw3 aided/first", dict(pd="corner", pilot_weight=3, word_mode="aided", anchor="first")),
        ("plain pw3 aided/first bw.01", dict(pd="plain", pilot_weight=3, word_mode="aided", anchor="first", loop_bw=0.01)),
        ("plain pw3 aided/first bw.04", dict(pd="plain", pilot_weight=3, word_mode="aided", anchor="first", loop_bw=0.04)),
    ]
    snrs = (14, 16, 18, 20, 22, 25)
    print("%-30s" % "variant (SER / bad frames)" + "".join("%15s" % ("%d dB" % v) for v in snrs))
    for name, kw in variants:
        line = "%-30s" % name
        for snr in snrs:
            x = F.channel(s, snr, cfo_hz=3000)
            r = FrameRxHW(**kw).run(x, ref_idx=REF)
            line += "%9.1e /%3d  " % (r.sym_err / max(r.sym_cnt, 1), r.bad_frames)
        print(line)
    print("%-30s" % "ideal (no sync loss)" + "".join("%15.1e" % ser_ideal(v) for v in snrs))


def gain_study(nfr=200):
    print("== gain error of the AGC (thresholds fixed at the nominal levels), SNR 22 dB, CFO 3 kHz, plain PD, aided/first")
    s, ids = F.make_frames(nfr, "prbs15")
    for g in (0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2):
        x = F.channel(s, 22, cfo_hz=3000, gain=g)
        r = FrameRxHW(word_mode="aided", anchor="first").run(x, ref_idx=REF)
        print("  gain x%.2f (%+.1f dB): SER %.1e, bad frames %d of %d" % (g, 20 * np.log10(g), r.sym_err / max(r.sym_cnt, 1), r.bad_frames, r.frames))


def stress(nfr=300):
    print("== phase noise (Wiener, rad per symbol; 0.0256 = 100 Hz linewidth at 960 ksym/s) and a frequency ramp (1 ppm/s of 915 MHz is 0.9 kHz/s; the 300 frames last 0.3 s), SNR 22 dB, CFO 3 kHz: SER / bad frames")
    s, ids = F.make_frames(nfr, "prbs15")
    variants = [
        ("freeze/every pw3 (FrameRx style)", dict(word_mode="freeze", anchor="every")),
        ("aided/first  pw3", dict(word_mode="aided", anchor="first")),
        ("aided/every  pw3", dict(word_mode="aided", anchor="every")),
        ("aided/first  pw5", dict(word_mode="aided", anchor="first", pilot_weight=5)),
        ("aided/first  ring", dict(word_mode="aided", anchor="first", pd="ring")),
        ("aided/first  bw 0.01", dict(word_mode="aided", anchor="first", loop_bw=0.01)),
        ("aided/first  bw 0.04", dict(word_mode="aided", anchor="first", loop_bw=0.04)),
        ("aided/every  bw 0.04", dict(word_mode="aided", anchor="every", loop_bw=0.04)),
    ]
    cases = [("pn 0", dict()), ("pn .005", dict(pn_std=0.005)), ("pn .01", dict(pn_std=0.01)), ("pn .02", dict(pn_std=0.02)), ("pn .03", dict(pn_std=0.03)), ("ramp 1 kHz/s", dict(drift_hz_s=1e3)), ("ramp 10 kHz/s", dict(drift_hz_s=10e3))]
    print("%-34s" % "variant" + "".join("%16s" % c[0] for c in cases))
    for name, kw in variants:
        line = "%-34s" % name
        for cname, ckw in cases:
            x = F.channel(s, 22, cfo_hz=3000, **ckw)
            r = FrameRxHW(**kw).run(x, ref_idx=REF)
            line += "%10.1e /%3d " % (r.sym_err / max(r.sym_cnt, 1), r.bad_frames)
        print(line)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("detect", detect), ("false", false), ("pd", pd_study), ("gain", gain_study), ("stress", stress)):
        if what in (name, "all"): fn(); print()
