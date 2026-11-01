#!/usr/bin/env python3
"""E3 to E6 of PLAN_OFDM_SYNC.md (E1, E2: study_cfo.py).
E3  what does the SHORT field buy: detection, timing (plateau against cross-correlation), coarse carrier, against its length and kind
E4  what does the LONG field buy: the channel estimate (EVM) and the carrier against L
E5  the whole link, frames A to F and the pilots: found, bad frames, EVM, symbol error rate, overhead, goodput
E6  robustness: a 2-tap echo, a large carrier offset
    python3 study_frames.py [frames per point, default 150] | tee results_frames.txt"""
import sys
import numpy as np
from ofdm_sync_lab import Cfg, run, summary, PILOT_SETS, FS

NFR = int(sys.argv[1]) if len(sys.argv) > 1 else 150
FINE = ["lag1"]                                     # the best long-field estimate of E1


def goodput(cfg, S):
    """payload Mbit/s that arrive: bits per frame x (frames that decode) x (1 - symbol error rate) / frame time"""
    if S.get("found", 0) == 0 or np.isnan(S["ser"]): return 0.0
    return cfg.bits_per_frame * (1 - S["bad"]) * (1 - S["ser"]) / cfg.frame_len * FS / 1e6


print("Conditions: carrier offset uniform in +-30 kHz (+-20 kHz for the frames with a long field only), random fractional delay and carrier phase, AWGN at the SNR per subcarrier, %d frames per point, floating point" % NFR)
print("Fine carrier: 'lag1' (lag 64 over the whole long field, the guard interval included). Data: 44 symbols, per-symbol pilot gain. 'start OK' = the window of every symbol stays inside its prefix.")
print()

print("E3: detection and timing against the short field (long field L = 2 behind it)")
shorts = [("STS 64 (4 x 16)", Cfg("sts", 64, 2)), ("STS 128 (8 x 16)", Cfg("sts", 128, 2)), ("STS 160 (802.11a)", Cfg("sts", 160, 2)), ("STS 192", Cfg("sts", 192, 2)),
          ("S&C 80 (period 32)", Cfg("sc", L=2)), ("none: long field, lag 64", Cfg("none", L=2)), ("none: L = 4", Cfg("none", L=4))]
SN3 = (14, 8, 4, 0)
for tm in ("plateau", "xcorr"):
    print(" timing: %s" % ("plateau centre (tutorial 6)" if tm == "plateau" else "cross-correlation with the known long symbol"))
    print("   %-28s %s" % ("short field", "".join("%25s" % ("%d dB: found / start OK" % s) for s in SN3)))
    for name, cfg in shorts:
        row = []
        for s in SN3:
            S = summary(run(cfg, s, NFR, cfo_range=20e3, fine=FINE, timing=tm, rng=np.random.default_rng(300 + s)))
            row.append("%25s" % ("%.2f / %.2f" % (S["found"], S["timing_ok"])))
        print("   %-28s %s" % (name, "".join(row)))
print()

print("E4: what the long field buys: the channel estimate and the carrier against L (STS 128 in front); EVM in dB (lower is better), carrier error rms in Hz")
print("   %-6s %9s %26s %26s %26s" % ("L", "overhead", "23 dB: EVM / carrier Hz", "18 dB: EVM / carrier Hz", "14 dB: EVM / carrier Hz"))
base = {}
for L in (1, 2, 4, 8):
    cfg = Cfg("sts", 128, L); row = []
    for s in (23, 18, 14):
        S = summary(run(cfg, s, NFR, fine=FINE, timing="xcorr", rng=np.random.default_rng(400 + s))); base[(L, s)] = S["evm"]
        row.append("%26s" % ("%.2f dB / %.0f" % (S["evm"], S["f_rms"])))
    print("   %-6d %8.1f%% %s" % (L, 100 * cfg.overhead, "".join(row)))
print("   (EVM gain of L = 4 over L = 2: %.2f, %.2f, %.2f dB at 23, 18, 14 dB; of L = 8 over L = 2: %.2f, %.2f, %.2f dB; the theory for averaging noise in the channel estimate is 10 log10(L / 2) at most)" %
      tuple([base[(2, s)] - base[(4, s)] for s in (23, 18, 14)] + [base[(2, s)] - base[(8, s)] for s in (23, 18, 14)]))
print()

print("E5: the whole link (timing: cross-correlation). found / bad frames / EVM / SER / goodput (Mbit/s of payload that arrive, uncoded 16-QAM)")
frames = [("A  STS128 + L2 (tutorial 6)", Cfg("sts", 128, 2)), ("B  S&C80 + L2", Cfg("sc", L=2)), ("C1 STS64 + L2", Cfg("sts", 64, 2)), ("C2 STS192 + L2", Cfg("sts", 192, 2)),
          ("D1 STS128 + L1", Cfg("sts", 128, 1)), ("D2 STS128 + L4", Cfg("sts", 128, 4)), ("D3 STS128 + L8", Cfg("sts", 128, 8)),
          ("E1 no short + L2", Cfg("none", L=2)), ("E2 no short + L4", Cfg("none", L=4))]
SN5 = (23, 18, 14, 10)
print("   %-30s %9s %s" % ("frame", "overhead", "".join("%34s" % ("%d dB" % s) for s in SN5)))
for name, cfg in frames:
    row = []
    for s in SN5:
        S = summary(run(cfg, s, NFR, cfo_range=20e3, fine=FINE, timing="xcorr", rng=np.random.default_rng(500 + s)))
        if S.get("found", 0) < 0.05: row.append("%34s" % "lost"); continue
        row.append("%34s" % ("%.2f/%.2f/%.1fdB/%.0e/%.2f" % (S["found"], S["bad"], S["evm"], S["ser"], goodput(cfg, S))))
    print("   %-30s %8.1f%% %s" % (name, 100 * cfg.overhead, "".join(row)))
print()
print("E5b: the number of pilots (frame A): fewer data subcarriers, a better gain estimate per symbol")
print("   %-10s %6s %s" % ("pilots", "data", "".join("%34s" % ("%d dB" % s) for s in SN5)))
for n in (2, 4, 6, 8):
    cfg = Cfg("sts", 128, 2, pilots=PILOT_SETS[n]); row = []
    for s in SN5:
        S = summary(run(cfg, s, NFR, cfo_range=20e3, fine=FINE, timing="xcorr", rng=np.random.default_rng(600 + s)))
        row.append("%34s" % ("%.2f/%.2f/%.1fdB/%.0e/%.2f" % (S["found"], S["bad"], S["evm"], S["ser"], goodput(cfg, S))) if S.get("found", 0) > 0.05 else "%34s" % "lost")
    print("   %-10d %6d %s" % (n, cfg.n_data, "".join(row)))
print()

print("E6: robustness (SNR 18 dB). found / bad frames / EVM / SER")
echo = np.zeros(10); echo[0] = 1.0; echo[8] = 0.5          # an echo of -6 dB, 8 samples (2.1 us) late: inside the prefix
echo2 = np.zeros(30); echo2[0] = 1.0; echo2[20] = 0.5       # an echo 20 samples late: outside the prefix of 16
E6 = [("A  STS128 + L2", Cfg("sts", 128, 2)), ("B  S&C80 + L2", Cfg("sc", L=2)), ("D2 STS128 + L4", Cfg("sts", 128, 4)), ("E2 no short + L4", Cfg("none", L=4))]
print("   %-20s %26s %26s %26s %26s" % ("frame", "no echo", "echo 8 samples", "echo 20 (> prefix)", "carrier +-50 kHz"))
for name, cfg in E6:
    row = []
    for taps, rng_hz in ((None, 20e3), (echo, 20e3), (echo2, 20e3), (None, 50e3)):
        S = summary(run(cfg, 18, NFR, cfo_range=rng_hz, fine=FINE, timing="xcorr", taps=taps, rng=np.random.default_rng(700)))
        row.append("%26s" % ("lost" if S.get("found", 0) < 0.05 else "%.2f/%.2f/%.1fdB/%.0e" % (S["found"], S["bad"], S["evm"], S["ser"])))
    print("   %-20s %s" % (name, "".join(row)))
