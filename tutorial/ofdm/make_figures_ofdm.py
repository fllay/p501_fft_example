#!/usr/bin/env python3
"""Figures of PLAN_OFDM.md -> tutorial/img/ofdm_fig_*.png"""
import os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from scipy.special import erfc
import ofdm_model as M
IMG = os.path.join(M.HERE, "..", "img"); Q = lambda x: 0.5 * erfc(x / np.sqrt(2))
BLUE, GREY, ORANGE, GREEN, RED = "#2b6cb0", "#a0aec0", "#dd6b20", "#2f855a", "#c53030"
def save(fig, name): fig.savefig(os.path.join(IMG, name), dpi=120, bbox_inches="tight"); plt.close(fig); print("wrote", name)

# 1. the frame and the subcarrier map ---------------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(2, 1, figsize=(12.5, 5.2), gridspec_kw=dict(height_ratios=[1, 1.15]))
a = ax[0]; a.set_xlim(-60, M.FRAME + 60); a.set_ylim(-0.3, 2.1); a.axis("off")
def box(x, w, c, t="", fs=8): a.add_patch(plt.Rectangle((x, 0), w, 1, fc=c, ec="k", lw=0.8)); a.text(x + w / 2, 0.5, t, ha="center", va="center", fontsize=fs)
box(0, 128, ORANGE, "STS: 8 x 16"); box(128, 32, "#fbd38d", ""); box(160, 64, GREEN, ""); box(224, 64, GREEN, "")
for l in range(M.L_SYM): box(288 + l * 80, 80, BLUE if l % 2 == 0 else "#4299e1", "" if l not in (0, 1, 2) else "data %d" % (l + 1), 7)
box(288 + 44 * 80, 32, "white", "idle", 7)
a.text(64, 1.2, "STS 128", ha="center", fontsize=8); a.text(224, 1.2, "LTS 160: GI2 32, T1 64, T2 64", ha="left", fontsize=8); a.annotate("", (224, 1.05), (224, 1.18)); a.text(2300, 1.2, "44 data symbols x 80 samples (CP 16 + 64): 4224 bits", ha="center", fontsize=9)
a.set_title("One frame = %d samples = 1 ms at 3.84 MS/s: detection and coarse carrier, training (QPSK) for the channel, data" % M.FRAME, fontsize=10)
a = ax[1]; ks = np.arange(-32, 32)
for k in ks:
    c = "white"; h = 0.15
    if k == 0: c, h = GREY, 0.3
    elif k in M.PIL: c, h = RED, 1.0
    elif k in M.DATA: c, h = BLUE, 1.0
    a.bar(k, h, color=c, ec="k", lw=0.4, width=0.9)
for k in M.STS_K: a.plot([k], [1.15], "v", c=ORANGE, ms=6)
a.set(xlim=(-33, 32), ylim=(0, 1.6), xlabel="subcarrier index k (60 kHz each; bin k mod 64)", yticks=[]); a.set_title("Subcarriers: 24 data (blue), 4 QPSK pilots (red), DC unused, 28 used = 1.68 MHz; orange markers: the 6 subcarriers of the STS (period 16 samples); the LTS loads all 28 with QPSK", fontsize=9)
save(fig, "ofdm_fig_frame.png")

# 2. detection metric and the plateau ----------------------------------------------------------------------------------------------------------------
x, d = M.tx_frame(); rng = np.random.default_rng(4); y = M.channel(x, 20, cfo_hz=9700, tau=3.4, rng=rng)
mm, S = M.timing_metric(y); s0, f, _ = M.detect(y)
fig, ax = plt.subplots(1, 3, figsize=(16, 4.3))
ax[0].plot(np.abs(y[:900]), lw=0.5); ax[0].axvline(300 + 3.4, c=RED, ls="--"); ax[0].set(title="received magnitude (Es/N0 20 dB, carrier 9.7 kHz, delay 3.4)", xlabel="sample"); ax[0].text(305, 0.2, "STS start", color=RED, fontsize=8)
ax[1].plot(mm[:700]); ax[1].axhline(0.5, c=RED, ls="--"); ax[1].axvline(s0 + 32, c=GREEN, ls=":"); ax[1].set(title="metric |S|^2 / E^2 of 48 products at lag 16", xlabel="start of the window"); ax[1].text(s0 + 36, 0.55, "plateau centre = STS start + 32", fontsize=8, color=GREEN); ax[1].text(10, 0.52, "threshold 0.5", color=RED, fontsize=8)
est = M.receive(y, return_all=True)
ax[2].plot(np.angle(S[s0 + 20:s0 + 45]) / (2 * np.pi * 16 / M.FS) / 1e3, ".-"); ax[2].axhline(9.7, c=RED, ls="--"); ax[2].set(title="coarse carrier from the plateau: angle(S) / (2 pi 16 / fs)", xlabel="start of the window (inside the plateau)", ylabel="kHz"); ax[2].text(0, 9.9, "true 9.7 kHz", color=RED, fontsize=8)
fig.tight_layout(); save(fig, "ofdm_fig_detect.png")

# 3. channel estimate and the equalised constellation -------------------------------------------------------------------------------------------------
taps = np.zeros(9, complex); taps[0] = 1.0; taps[8] = 0.5 * np.exp(1j * 1.0)
rng = np.random.default_rng(6); y = M.channel(x, 26, cfo_hz=9700, tau=3.4, taps=taps, rng=rng); r = M.receive(y, return_all=True)
fig, ax = plt.subplots(1, 3, figsize=(16, 4.4))
Htrue = np.array([np.sum(taps * np.exp(-2j * np.pi * k * np.arange(9) / M.N)) for k in M.USED])
ax[0].plot(M.USED, 20 * np.log10(np.abs(Htrue)), "k-", label="true"); ax[0].plot(M.USED, 20 * np.log10(np.abs(r["H"])), "o", c=BLUE, ms=4, label="estimated from T1, T2 (QPSK)")
ax[0].set(title="|H|: two taps, 8 samples apart, -6 dB", xlabel="subcarrier k", ylabel="dB"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
ph_t = np.unwrap(np.angle(Htrue)); ph_e = np.unwrap(np.angle(r["H"]))
ax[1].plot(M.USED, ph_e, "o", c=BLUE, ms=4); ax[1].set(title="phase of H: the slope is the window offset", xlabel="subcarrier k", ylabel="rad"); ax[1].grid(alpha=0.3)
Z = r["Z"].reshape(-1); ax[2].scatter(Z.real, Z.imag, s=2, alpha=0.5); lv = np.array([-3, -1, 1, 3]) / np.sqrt(10)
ax[2].scatter(np.repeat(lv, 4), np.tile(lv, 4), c=RED, marker="+", s=60); ax[2].set(title="equalised data (EVM %.1f dB)" % M.metrics(r["Z"], d)[0], aspect="equal", xlabel="I", ylabel="Q")
fig.tight_layout(); save(fig, "ofdm_fig_channel.png")

# 4. error rate and PAPR ----------------------------------------------------------------------------------------------------------------------------------
snr = np.arange(12, 27, 2); gl = 10 ** (snr / 10); th = 3 * Q(np.sqrt(gl / 5)) - 2.25 * Q(np.sqrt(gl / 5)) ** 2
ev, se = [], []
for s in snr:
    e, ss = [], []
    for i in range(120):
        rng = np.random.default_rng(1000 + i); yy = M.channel(x, s, cfo_hz=rng.uniform(-15e3, 15e3), tau=rng.uniform(0, 12), ppm=10.0, rng=rng); rr = M.receive(yy, return_all=True, gsmooth=5)
        if rr: a_, b_ = M.metrics(rr["Z"], d); e.append(a_); ss.append(b_)
    ev.append(np.mean(e)); se.append(np.mean(ss))
fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
ax[0].semilogy(snr, th, "k--", label="16-QAM in white noise (theory, ideal channel knowledge)"); ax[0].semilogy(snr, np.where(np.array(se) > 0, se, np.nan), "o-", c=BLUE, label="this receiver (detection, carrier, 2 QPSK training symbols, pilots)")
ax[0].set(xlabel="Es/N0 per subcarrier (dB)", ylabel="symbol error rate", ylim=(1e-6, 1), title="loss of the estimation: about 2 to 2.5 dB (no error counted below 3e-6)"); ax[0].grid(alpha=0.3, which="both"); ax[0].legend(fontsize=8)
po = np.concatenate([np.abs(M.tx_frame(np.random.default_rng(i).integers(0, 2, M.L_SYM * M.BITS_SYM).astype(np.uint8))[0][288:M.FRAME - M.GAP]) ** 2 for i in range(200)]); po /= po.mean(); ps = M.sc_papr_db()
for p, lab, c in ((po, "OFDM, 28 subcarriers", BLUE), (ps, "single-carrier 16-QAM, RRC 0.35", ORANGE)):
    q = np.sort(10 * np.log10(p)); ccdf = 1 - np.arange(len(q)) / len(q); ax[1].semilogy(q[::50], ccdf[::50], c=c, label=lab)
ax[1].set(xlabel="instantaneous power above the mean (dB)", ylabel="probability of exceeding", ylim=(1e-6, 1), xlim=(0, 12), title="peak-to-average power: OFDM needs about 4 dB more headroom"); ax[1].grid(alpha=0.3, which="both"); ax[1].legend(fontsize=8)
fig.tight_layout(); save(fig, "ofdm_fig_ser_papr.png")

# 5. block diagram of the receiver ---------------------------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(14, 6.6)); ax.set_xlim(0, 14); ax.set_ylim(0, 6.6); ax.axis("off")
def blk(x, y, w, h, t, col, fs=8.5): ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04", fc=col, ec="k")); ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs)
def arr(x0, y0, x1, y1, c="k", ls="-"): ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=12, color=c, ls=ls))
OLD, NEW, FFTC = "#e2e8f0", "#bee3f8", "#feebc8"
blk(0.2, 4.6, 1.7, 1.3, "ADC 3.84 MS/s\nsample RAM\n(as in QPSK)", OLD); blk(2.4, 4.6, 2.5, 1.3, "detector: lag-16 delay-and-\ncorrelate, 48 products,\nenergy-normalised metric", NEW); blk(5.4, 4.6, 2.2, 1.3, "coarse carrier\nangle(S) -> CORDIC", NEW)
blk(8.1, 4.6, 2.2, 1.3, "NCO + derotation\n(complex multiply)", OLD); blk(10.8, 4.6, 1.5, 1.3, "frame\ncounter\n(window starts)", NEW); blk(12.6, 4.6, 1.2, 1.3, "AGC:\nblock gain\nfrom the STS", NEW)
for a_, b_ in ((1.9, 2.4), (4.9, 5.4), (7.6, 8.1), (10.3, 10.8), (12.3, 12.6)): arr(a_, 5.25, b_, 5.25)
blk(0.2, 2.6, 2.4, 1.3, "FFT 64 (Xilinx FFT 9.1,\npipelined, one per symbol,\nscaling schedule)", FFTC); blk(3.1, 2.6, 2.8, 1.3, "training T1, T2:\nH = (A + B) conj(T) / 2,\nnoise from A - B,\nreciprocal -> W = 1 / H", NEW, 8)
blk(6.4, 2.6, 2.5, 1.3, "equaliser: one complex\nmultiply per subcarrier\n(28 per symbol)", NEW); blk(9.4, 2.6, 2.4, 1.3, "pilots: 4 QPSK, known\ncommon gain g, slope\n(average of 5 symbols)", NEW); blk(12.2, 2.6, 1.6, 1.3, "divide by g\nand the slope\n(derotation)", NEW)
arr(1.4, 4.6, 1.4, 3.9); arr(2.6, 3.25, 3.1, 3.25); arr(5.9, 3.25, 6.4, 3.25); arr(8.9, 3.25, 9.4, 3.25); arr(11.8, 3.25, 12.2, 3.25)
blk(1.0, 0.5, 3.4, 1.2, "16-QAM slicer (24 per symbol),\nGray bits, PRBS-15 checker,\nEVM, symbol and bit errors", NEW); blk(5.0, 0.5, 3.4, 1.2, "soft output for the FEC stage:\nz / |H|^2 weights per subcarrier\n(the common soft interface)", NEW); blk(9.0, 0.5, 4.8, 1.2, "capture RAM (soft symbols), AXI-Lite registers,\nlock / frame counters, SNR estimate", OLD)
arr(13.0, 2.6, 4.4, 1.7); arr(13.0, 2.6, 6.7, 1.7); arr(13.0, 2.6, 11.4, 1.7); arr(11.6, 4.6, 7.0, 3.9, c=ORANGE, ls="--"); ax.text(8.6, 4.05, "window start and symbol type for every FFT", fontsize=7.5, color=ORANGE)
ax.add_patch(plt.Rectangle((0.2, 6.2), 0.3, 0.2, fc=OLD, ec="k")); ax.text(0.6, 6.3, "reused", va="center", fontsize=9); ax.add_patch(plt.Rectangle((1.8, 6.2), 0.3, 0.2, fc=NEW, ec="k")); ax.text(2.2, 6.3, "new", va="center", fontsize=9); ax.add_patch(plt.Rectangle((3.0, 6.2), 0.3, 0.2, fc=FFTC, ec="k")); ax.text(3.4, 6.3, "Xilinx IP", va="center", fontsize=9)
ax.set_title("OFDM receiver sketch for the FPGA (nothing is built yet): open-loop block processing, no timing or phase loop", fontsize=10); save(fig, "ofdm_fig_block_rx.png")

# 6. multiplicative modulation -----------------------------------------------------------------------------------------------------------------------------------
names = ["none", "slow 137 Hz", "slow 5 kHz", "slow 30 kHz", "white"]; vals = {"no correction": [-22.6, -21.3, -1.3, 2.5, -9.0], "phase only": [-30.9, -27.0, -18.8, -16.4, -19.9], "complex gain": [-30.7, -30.7, -28.2, -16.5, -19.5]}
fig, ax = plt.subplots(figsize=(9.5, 4.4)); w = 0.27
for i, (k, v) in enumerate(vals.items()): ax.bar(np.arange(5) + (i - 1) * w, v, w, label=k)
ax.set_xticks(range(5)); ax.set_xticklabels(names); ax.set(ylabel="EVM (dB)", title="Multiplicative modulation of variance 0.013 (-18.9 dB): the pilots remove the slow part"); ax.legend(fontsize=8); ax.grid(alpha=0.3, axis="y"); save(fig, "ofdm_fig_modulation.png")

# 7. detection compared: our STS with lag 16 against Schmidl and Cox -----------------------------------------------------------------------------------------
import ofdm_sync_compare as C
fig, ax = plt.subplots(1, 3, figsize=(16.5, 4.4))
for snr, ls in ((20, "-"), (12, ":")):
    for (name, pre, sync), col in zip(C.METHODS[:2], (BLUE, ORANGE)):
        xx, _ = M.tx_frame(preamble=pre); y = M.channel(xx, snr, cfo_hz=9700, tau=0.0, rng=np.random.default_rng(3), lead=300)
        m, _ = M.timing_metric(y, 16, 48) if sync == "sts16" else M.timing_metric(y, 32, 32); ax[0].plot(np.arange(len(m))[200:480] - 300, m[200:480], ls, c=col, lw=1, label="%s, %d dB" % (name, snr))
ax[0].set(xlabel="window start relative to the preamble start (samples)", ylabel="metric |S|^2 / E^2", title="the plateau: 65 positions (STS, lag 16) against 17 (S&C, lag 32)"); ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3)
pool = C.Pool(14); snrs = [8, 10, 12, 14, 16, 18, 20, 22]
for (name, pre, sync), col in zip(C.METHODS, (BLUE, ORANGE, GREY)):
    sd = []
    for s in snrs:
        res = [r for r in pool.map(C.trial, [(pre, sync, s, 100 + i, {}) for i in range(200)], chunksize=4) if r]; sd.append(np.std([r[0] for r in res]))
    ax[1].semilogy(snrs, sd, "o-", c=col, label=name)
ax[1].axhline(6, c=RED, ls="--"); ax[1].text(8.2, 6.5, "tolerance of the FFT window (+6 / -10)", color=RED, fontsize=7)
ax[1].set(xlabel="Es/N0 per subcarrier (dB)", ylabel="start error, standard deviation (samples)", title="timing: S&C needs the plateau rule, argmax is too noisy"); ax[1].legend(fontsize=7); ax[1].grid(alpha=0.3, which="both")
rng = np.random.default_rng(5); thr = [0.3, 0.4, 0.5, 0.6, 0.7]
for (name, pre, sync), col in zip(C.METHODS[:2], (BLUE, ORANGE)):
    fa = []
    for t in thr:
        n_fa = 0
        for i in range(1500):
            y = np.sqrt(0.5 * 10 ** (-20 / 10)) * (rng.standard_normal(3840) + 1j * rng.standard_normal(3840)); n_fa += (M.detect(y, t) if sync == "sts16" else M.detect_sc(y, t, "plateau")) is not None
        fa.append(max(n_fa, 0.3) / 1500)
    ax[2].semilogy(thr, fa, "o-", c=col, label=name)
ax[2].set(xlabel="detection threshold", ylabel="false alarm per 3840-sample frame (noise only)", title="false alarms: S&C needs a threshold of 0.6 or more"); ax[2].legend(fontsize=7); ax[2].grid(alpha=0.3, which="both")
fig.tight_layout(); save(fig, "ofdm_fig_sync_compare.png")
