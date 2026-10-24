#!/usr/bin/env python3
"""Studies of the OFDM design (PLAN_OFDM.md): python3 ofdm_study.py -> results_ofdm.txt"""
import sys, time
import numpy as np
from multiprocessing import Pool
from scipy.special import erfc
import ofdm_model as M
Q = lambda x: 0.5 * erfc(x / np.sqrt(2))
ser_theory = lambda g: 3 * Q(np.sqrt(g / 5)) - 2.25 * Q(np.sqrt(g / 5)) ** 2
LEAD = 300
out = []
def P(s=""): out.append(s); print(s, flush=True)


def trial(a):
    kind, snr, seed, kw = a; rng = np.random.default_rng(seed)
    x, d = M.tx_frame()
    if kind == "genie":
        y = M.channel(x, snr, rng=rng, lead=LEAD); r = M.receive(y, genie=(LEAD, 0.0), return_all=True, track=kw.get("track", "complex"), gsmooth=kw.get("gs", 1))
    else:
        cfo = kw.get("cfo", rng.uniform(-15e3, 15e3)); tau = kw.get("tau", rng.uniform(0, 12))
        y = M.channel(x, snr, cfo_hz=cfo, tau=tau, ppm=kw.get("ppm", 10.0), taps=kw.get("taps"), slow=kw.get("slow", 0.0), slow_hz=kw.get("slow_hz", 137.0), white=kw.get("white", 0.0), rng=rng, lead=LEAD)
        r = M.receive(y, return_all=True, track=kw.get("track", "complex"), gsmooth=kw.get("gs", 1))
        if r is None: return None
        r["tau_err"] = r["s0"] - (LEAD + tau + (len(kw.get("taps", [0])) and 0)); r["cfo_err"] = r["f"] - cfo
    evm, ser = M.metrics(r["Z"], d)
    return evm, ser, r.get("tau_err", 0.0), r.get("cfo_err", 0.0), r["sig2"]


def run(jobs, pool): return pool.map(trial, jobs, chunksize=4)


if __name__ == "__main__":
    pool = Pool(14); t0 = time.time()
    P("OFDM design studies: N=64, CP=16, 28 used subcarriers (24 16-QAM data, 4 QPSK pilots), 44 data symbols per frame, training QPSK (PAPR %.2f dB)\n" % M.PAPR_T)
    # E1
    P("== E1: symbol error rate and EVM against the SNR per subcarrier (Es/N0), 300 frames per point (genie: perfect timing and carrier; full: random carrier +-15 kHz, delay 0 to 12 samples, 10 ppm, detection and estimation)")
    P("Es/N0   theory SER   genie SER   genie EVM   full SER   full EVM   missed")
    for snr in range(12, 29, 2):
        g = run([("genie", snr, 100 + i, {}) for i in range(300)], pool); f = run([("full", snr, 500 + i, {}) for i in range(300)], pool)
        ok = [r for r in f if r]; P("%5d   %.2e     %.2e    %6.1f dB   %.2e   %6.1f dB   %d" % (snr, ser_theory(10 ** (snr / 10)), np.mean([r[1] for r in g]), np.mean([r[0] for r in g]), np.mean([r[1] for r in ok]), np.mean([r[0] for r in ok]), len(f) - len(ok)))
    P("\n== E1b: the estimation loss and what reduces it (genie, 300 frames; EVM in dB, SNR per subcarrier 20 dB: ideal receiver would give -20.0 dB)")
    P("pilot correction                       EVM        SER")
    for name, kw in (("complex gain, per symbol", dict(track="complex")), ("complex gain, average of 3 symbols", dict(track="complex", gs=3)), ("complex gain, average of 5 symbols", dict(track="complex", gs=5)), ("phase only, per symbol", dict(track="phase")), ("phase only, average of 5", dict(track="phase", gs=5)), ("none", dict(track="none"))):
        g = run([("genie", 20, 300 + i, kw) for i in range(300)], pool); P("%-38s %6.1f dB   %.2e" % (name, np.mean([r[0] for r in g]), np.mean([r[1] for r in g])))
    # E2 detection
    P("\n== E2: detection and estimation against the SNR (500 frames each, carrier +-20 kHz, delay 0 to 12 samples, threshold 0.5)")
    P("Es/N0   detected   STS start error (samples) mean / std   carrier error std (Hz)")
    for snr in (4, 8, 12, 16, 20, 24):
        f = run([("full", snr, 900 + i, dict(cfo=np.random.default_rng(900 + i).uniform(-20e3, 20e3))) for i in range(500)], pool); ok = [r for r in f if r]
        te = np.array([r[2] for r in ok]); ce = np.array([r[3] for r in ok]) if ok else np.array([0.0])
        P("%5d   %5.1f %%    %+5.2f / %4.2f                          %6.0f" % (snr, 100 * len(ok) / len(f), te.mean() if len(te) else 0, te.std() if len(te) else 0, ce.std()))
    rng = np.random.default_rng(5); fa = 0; ntr = 3000
    for i in range(ntr):
        y = np.sqrt(0.5 * 10 ** (-20 / 10)) * (rng.standard_normal(3840) + 1j * rng.standard_normal(3840)); fa += M.detect(y, 0.5) is not None
    P("false alarms on noise only (3840 samples, 3000 trials): %d" % fa)
    # E3 PAPR
    P("\n== E3: peak-to-average power ratio (CCDF): power above the mean at the given probability")
    x, d = M.tx_frame(); xs = []
    rng = np.random.default_rng(2)
    for _ in range(300):
        bits = rng.integers(0, 2, M.L_SYM * M.BITS_SYM).astype(np.uint8); xx, _ = M.tx_frame(bits); xs.append(xx[M.STS_LEN + M.LTS_LEN:M.FRAME - M.GAP])
    po = np.abs(np.concatenate(xs)) ** 2; po = po / po.mean(); ps = M.sc_papr_db()
    for name, p in (("OFDM data symbols (28 used)", po), ("single-carrier 16-QAM, RRC 0.35", ps)):
        P("   %-34s 1e-2: %.1f dB   1e-3: %.1f dB   1e-4: %.1f dB   max: %.1f dB" % (name, *(10 * np.log10(np.quantile(p, 1 - q)) for q in (1e-2, 1e-3, 1e-4)), 10 * np.log10(p.max())))
    # E4 training
    P("\n== E4: the training symbol: QPSK against BPSK")
    rng = np.random.default_rng(3); pq = [M.papr_db(M.to_time((M.USED, M.qpsk(rng, 28)))) for _ in range(4000)]; pb = [M.papr_db(M.to_time((M.USED, 1 - 2 * rng.integers(0, 2, 28).astype(float)))) for _ in range(4000)]
    P("   PAPR of the 64-sample training symbol over 4000 random sequences: QPSK mean %.1f dB, best %.1f dB;  BPSK mean %.1f dB, best %.1f dB;  the chosen QPSK sequence: %.2f dB" % (np.mean(pq), min(pq), np.mean(pb), min(pb), M.PAPR_T))
    mq, mb = [], []
    for i in range(400):
        h = (rng.standard_normal(28) + 1j * rng.standard_normal(28)) / np.sqrt(2)
        for tv, store in ((M.TRAIN, mq), (np.where(rng.integers(0, 2, 28) > 0, 1.0, -1.0), mb)):
            n1, n2 = [(rng.standard_normal(28) + 1j * rng.standard_normal(28)) * np.sqrt(10 ** (-15 / 10) / 2) for _ in range(2)]
            est = 0.5 * ((h * tv + n1) + (h * tv + n2)) * np.conj(tv); store.append(np.mean(np.abs(est - h) ** 2))
    P("   channel estimate error (two training symbols averaged, Es/N0 15 dB): QPSK %.2e, BPSK %.2e (theory sigma^2/2 = %.2e): equal, the same energy per subcarrier" % (np.mean(mq), np.mean(mb), 10 ** (-15 / 10) / 2))
    # E5 multipath / timing
    P("\n== E5: multipath inside and outside the cyclic prefix (Es/N0 24 dB, 150 frames): two taps, the second at the given delay with -6 dB")
    P("delay (samples)   EVM        SER")
    for dl in (0, 2, 5, 8, 10, 12, 16, 24):
        taps = np.zeros(dl + 1, complex); taps[0] = 1.0
        if dl: taps[dl] = 0.5 * np.exp(1j * 1.0)
        f = run([("full", 24, 1300 + i, dict(taps=taps, cfo=9700.0)) for i in range(150)], pool); ok = [r for r in f if r]
        P("%8d          %6.1f dB   %.2e   (%d of %d frames found)" % (dl, np.mean([r[0] for r in ok]) if ok else 0, np.mean([r[1] for r in ok]) if ok else 0, len(ok), len(f)))
    # E6 slow modulation
    P("\n== E6: multiplicative modulation of the signal of variance 0.013 (-18.9 dB, the 'bad state' of the link report), Es/N0 35 dB, carrier 9.7 kHz, 150 frames: EVM by the pilots' correction")
    P("modulation                     none       phase      complex    complex+slope   complex, 5-symbol average")
    for name, kw in (("none (reference)", {}), ("slow, 137 Hz", dict(slow=0.013, slow_hz=137.0)), ("slow, 5 kHz", dict(slow=0.013, slow_hz=5e3)), ("slow, 30 kHz", dict(slow=0.013, slow_hz=30e3)), ("white (every sample)", dict(white=0.013))):
        row = []
        for tr, gs in (("none", 1), ("phase", 1), ("complex", 1), ("complex+slope", 1), ("complex", 5)):
            f = run([("full", 35, 1700 + i, dict(kw, cfo=9700.0, tau=4.3, track=tr, gs=gs)) for i in range(150)], pool); ok = [r for r in f if r]; row.append(np.mean([r[0] for r in ok]))
        P("%-28s %6.1f dB  %6.1f dB  %6.1f dB  %6.1f dB      %6.1f dB" % (name, *row))
    # E7 ppm
    P("\n== E7: sample clock offset (Es/N0 35 dB, 150 frames)")
    P("ppm     EVM, phase    complex    complex+slope")
    for ppm in (0, 30, 100, 300):
        row = []
        for tr in ("phase", "complex", "complex+slope"):
            f = run([("full", 35, 2100 + i, dict(cfo=9700.0, tau=4.3, ppm=ppm, track=tr)) for i in range(150)], pool); ok = [r for r in f if r]; row.append(np.mean([r[0] for r in ok]))
        P("%4d    %6.1f dB    %6.1f dB    %6.1f dB" % (ppm, *row))
    # E8 CFO range
    P("\n== E8: carrier offset range (Es/N0 25 dB, 100 frames each)")
    for cfo in (0, 10e3, 25e3, 50e3, 80e3, 110e3, 130e3):
        f = run([("full", 25, 2500 + i, dict(cfo=float(cfo), tau=4.3)) for i in range(100)], pool); ok = [r for r in f if r]
        P("   %+7.0f Hz: found %3d of 100, EVM %s, SER %s" % (cfo, len(ok), "%.1f dB" % np.mean([r[0] for r in ok]) if ok else "-", "%.2e" % np.mean([r[1] for r in ok]) if ok else "-"))
    P("\n(%.0f s)" % (time.time() - t0))
    open("results_ofdm.txt", "w").write("\n".join(out) + "\n")
