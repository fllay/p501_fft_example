#!/usr/bin/env python3
"""Figures of tutorial/TUTORIAL_QAM16.md -> tutorial/img/qam16_fig_*.png.   python3 make_figures_qam16.py"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from scipy.special import erfc
HERE = os.path.dirname(os.path.abspath(__file__)); IMG = os.path.join(HERE, "..", "img"); sys.path.insert(0, HERE)
import frame16 as F
Q = lambda x: 0.5 * erfc(x / np.sqrt(2))
BLUE, GREY, ORANGE, GREEN, RED = "#2b6cb0", "#a0aec0", "#dd6b20", "#2f855a", "#c53030"
def save(fig, name): fig.savefig(os.path.join(IMG, name), dpi=120, bbox_inches="tight"); plt.close(fig); print("wrote", name)

# 1. constellations ----------------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(1, 2, figsize=(11, 5))
q = np.array([1 + 1j, -1 + 1j, -1 - 1j, 1 - 1j]) / np.sqrt(2)
ax[0].scatter(q.real, q.imag, s=120, c=BLUE); ax[0].axhline(0, c=GREY, ls="--"); ax[0].axvline(0, c=GREY, ls="--")
for p, b in zip(q, ("00", "10", "11", "01")): ax[0].annotate(b, (p.real, p.imag), xytext=(8, 8), textcoords="offset points")
ax[0].annotate("", (q[0].real, q[0].imag), (q[1].real, q[1].imag), arrowprops=dict(arrowstyle="<->", color=RED)); ax[0].text(0, 0.78, "d = 1.41", color=RED, ha="center")
ax[0].set(title="QPSK: 2 bits per symbol, unit average power", xlim=(-1.6, 1.6), ylim=(-1.6, 1.6), aspect="equal")
lv = np.array([-3, -1, 1, 3]) / np.sqrt(10); code = {-3: "00", -1: "01", 1: "11", 3: "10"}
for i in (-3, -1, 1, 3):
    for qq in (-3, -1, 1, 3):
        ax[1].scatter(i / np.sqrt(10), qq / np.sqrt(10), s=80, c=BLUE); ax[1].annotate(code[i] + code[qq], (i / np.sqrt(10), qq / np.sqrt(10)), xytext=(6, 6), textcoords="offset points", fontsize=7)
for t in (-2, 0, 2): ax[1].axhline(t / np.sqrt(10), c=GREY, ls="--"); ax[1].axvline(t / np.sqrt(10), c=GREY, ls="--")
ax[1].annotate("", (1 / np.sqrt(10), -1 / np.sqrt(10)), (-1 / np.sqrt(10), -1 / np.sqrt(10)), arrowprops=dict(arrowstyle="<->", color=RED)); ax[1].text(0, -0.52, "d = 0.63", color=RED, ha="center")
ax[1].set(title="16-QAM: 4 bits per symbol (Gray: I bits, Q bits), thresholds 0 and +-2 units", xlim=(-1.6, 1.6), ylim=(-1.6, 1.6), aspect="equal")
for a in ax: a.set_xlabel("I"); a.set_ylabel("Q"); a.grid(alpha=0.2)
fig.suptitle("Same average power: the nearest neighbours of 16-QAM are 2.2 times (7 dB) closer than QPSK's", y=1.0); save(fig, "qam16_fig_constellations.png")

# 2. SER theory ----------------------------------------------------------------------------------------------------------------------
g = np.linspace(0, 26, 400); gl = 10 ** (g / 10)
sq = 2 * Q(np.sqrt(gl)) - Q(np.sqrt(gl)) ** 2; s16 = 3 * Q(np.sqrt(gl / 5)) - 2.25 * Q(np.sqrt(gl / 5)) ** 2
fig, ax = plt.subplots(figsize=(7.5, 4.6)); ax.semilogy(g, sq, c=BLUE, label="QPSK"); ax.semilogy(g, s16, c=ORANGE, label="16-QAM")
ax.axhline(1e-3, c=GREY, ls="--"); ax.annotate("", (17.6, 1e-3), (10.3, 1e-3), arrowprops=dict(arrowstyle="<->", color=RED)); ax.text(14, 1.5e-3, "7.3 dB", color=RED, ha="center")
ax.set(xlabel="Es/N0 (dB)", ylabel="symbol error rate", ylim=(1e-7, 1), title="Symbol error rate in white noise (theory)"); ax.grid(alpha=0.3, which="both"); ax.legend(); save(fig, "qam16_fig_ser_theory.png")

# 3. the frame -------------------------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(2, 1, figsize=(12, 4.3), gridspec_kw=dict(height_ratios=[1, 1.2]))
def box(a, x, w, txt, col, y=0, h=1, fs=9): a.add_patch(plt.Rectangle((x, y), w, h, fc=col, ec="k")); a.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs)
a = ax[0]; box(a, 0, 8, "", GREEN); box(a, 8, 63, "", ORANGE)
for b in range(14): box(a, 71 + 64 * b, 63, "63 data" if b in (0, 1, 2, 13) else ("..." if b == 3 else ""), BLUE if b != 3 else "white", fs=7)
for b in range(14): a.add_patch(plt.Rectangle((71 + 64 * b + 62, -0.12), 3.2, 1.24, fc=RED, ec="k", lw=0.6, zorder=5))
a.set(xlim=(-5, 972), ylim=(-0.2, 2.0)); a.axis("off"); a.set_title("One frame = 967 symbols = 1.007 ms at 960 ksym/s (4 samples per symbol at 3.84 MS/s)", fontsize=10)
a.annotate("CP: 8", (4, 1.1), (-3, 1.6), fontsize=8, arrowprops=dict(arrowstyle="-")); a.annotate("ZC word: 63", (40, 1.1), (30, 1.6), fontsize=8, arrowprops=dict(arrowstyle="-")); a.text(560, 1.55, "14 blocks of 64 symbols: 63 data symbols, then one BPSK pilot (red, +-1)", ha="center", fontsize=8)
a = ax[1]; a.axis("off"); a.set_xlim(0, 10); a.set_ylim(0, 3.2)
rows = [("CP: the last 8 symbols of the word", GREEN, "known symbols: the PLL can use them (aided mode)"), ("ZC word: 63 symbols of a Zadoff-Chu sequence (root 1)", ORANGE, "frame start, gain, carrier frequency and phase"),
        ("Data: 882 symbols = 3528 bits, PRBS-15 restarted in every frame", BLUE, "the checker counts symbol and bit errors against it"), ("Pilots: 14 BPSK symbols", RED, "known phase reference every 64 symbols (PLL weight 3)")]
for i, (t, c, d) in enumerate(rows): a.add_patch(plt.Rectangle((0.1, 2.5 - i * 0.8), 0.4, 0.45, fc=c, ec="k")); a.text(0.7, 2.72 - i * 0.8, t, va="center", fontsize=9, fontweight="bold"); a.text(6.4, 2.72 - i * 0.8, d, va="center", fontsize=9)
save(fig, "qam16_fig_frame.png")

# 4. the Zadoff-Chu word -------------------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(1, 3, figsize=(17, 4.6))
rng = np.random.default_rng(2); sym, _ = F.make_frames(3, "prbs15"); snr = 12.0
x = sym + (rng.standard_normal(len(sym)) + 1j * rng.standard_normal(len(sym))) * 10 ** (-snr / 20) / np.sqrt(2)
c = np.correlate(x, F.ZC, "valid"); e = np.convolve(np.abs(x), np.ones(63), "valid"); rho = np.abs(c) / e
ax[0].plot(rho[:2200], lw=0.7); ax[0].axhline(0.6, c=RED, ls="--"); ax[0].text(1500, 0.63, "search threshold 0.6", color=RED, fontsize=8); ax[0].axhline(0.45, c=GREEN, ls="--"); ax[0].text(1500, 0.40, "lock threshold 0.45", color=GREEN, fontsize=8)
ax[0].annotate("word of frame 1", (8, 0.95), (200, 0.9), arrowprops=dict(arrowstyle="->")); ax[0].annotate("frame 2: 967 symbols later", (975, 0.95), (1150, 0.88), arrowprops=dict(arrowstyle="->"))
ax[0].set(xlabel="symbol position of the correlation window", ylabel="rho = |sum x conj(ZC)| / sum |x|", ylim=(0, 1.1)); ax[0].set_title("ZC word in 16-QAM data (Es/N0 12 dB)", fontsize=10); ax[0].grid(alpha=0.3)
f = np.linspace(1, 16e3, 500); rho_f = np.abs(np.sin(np.pi * f * 63 / 960e3) / (63 * np.sin(np.pi * f / 960e3)))
ax[1].plot(f / 1e3, rho_f); ax[1].axhline(0.6, c=RED, ls="--"); ax[1].axvline(7.6, c=GREY, ls=":"); ax[1].text(7.7, 0.9, "Rs/(2N) = 7.6 kHz", fontsize=8); ax[1].axvline(9.7, c=ORANGE, ls=":"); ax[1].text(9.8, 0.75, "natural P501-B210\noffset 9.7 kHz", fontsize=8, color=ORANGE)
ax[1].set(xlabel="carrier offset (kHz)", ylabel="peak of rho", ylim=(0, 1.05)); ax[1].set_title("the peak falls with the carrier offset", fontsize=10); ax[1].grid(alpha=0.3)
n = np.arange(63); w = F.ZC; fcfo = 0.012; xx = w * np.exp(2j * np.pi * fcfo * n)
c1, c2 = np.sum((xx * np.conj(w))[:31]), np.sum((xx * np.conj(w))[32:]); om = np.angle(c2 * np.conj(c1)) / 32
ax[2].scatter((xx * np.conj(w)).real, (xx * np.conj(w)).imag, c=np.arange(63), cmap="viridis", s=18); ax[2].plot([0, c1.real / 31], [0, c1.imag / 31], c=RED); ax[2].plot([0, c2.real / 31], [0, c2.imag / 31], c=GREEN)
ax[2].text(-1.05, -1.45, "red: C1 (first 31 products), green: C2 (last 31)\nw = arg(C2 conj C1) / 32 = %.4f rad/symbol (true %.4f)" % (om, 2 * np.pi * fcfo), fontsize=8)
ax[2].set(xlabel="Re(x conj ZC)", ylabel="Im", ylim=(-1.6, 1.1), aspect="equal"); ax[2].set_title("x conj(ZC) with a 11.5 kHz offset: a phasor", fontsize=10); ax[2].grid(alpha=0.3)
fig.tight_layout(); save(fig, "qam16_fig_zc.png")

# 5. receiver block diagram ---------------------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(14, 7.2)); ax.set_xlim(0, 14); ax.set_ylim(0, 7.2); ax.axis("off")
def blk(x, y, w, h, t, col, fs=9): ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04", fc=col, ec="k")); ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs)
def arr(x0, y0, x1, y1, c="k", st="-|>", ls="-"): ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=st, mutation_scale=12, color=c, ls=ls))
NEW, OLD = "#bee3f8", "#e2e8f0"
blk(0.2, 5.3, 1.6, 1.2, "ADC\n3.84 MS/s\nsample RAM", OLD); blk(2.3, 5.3, 1.9, 1.2, "band-edge FLL\n(derotation)\nqpsk_fll.v", OLD); blk(4.7, 5.3, 2.3, 1.2, "polyphase matched +\nderivative filter\n(44 taps, 4 sps)", OLD)
blk(7.5, 5.3, 1.8, 1.2, "power AGC\n(rounded)", NEW); blk(9.8, 5.3, 1.9, 1.2, "timing error\nand loop\n(acq. gains)", OLD); blk(12.2, 5.3, 1.6, 1.2, "symbols\nmi2, mq2\n(1 per symbol)", OLD)
for a, b in ((1.8, 2.3), (4.2, 4.7), (7.0, 7.5), (9.3, 9.8), (11.7, 12.2)): arr(a, 5.9, b, 5.9)
arr(10.75, 5.3, 10.75, 4.9, st="-"); ax.annotate("", (5.85, 5.25), (10.75, 4.9), arrowprops=dict(arrowstyle="-|>", color=ORANGE, connectionstyle="angle,angleA=0,angleB=90,rad=0")); ax.text(8.5, 4.7, "timing: polyphase phase and rate", fontsize=8, color=ORANGE)
blk(11.0, 3.2, 2.8, 1.2, "qam_zc_sync.v\ncorrelator, rho = |C|/sum|x|,\nSEARCH-VERIFY-LOCKED,\ncarrier from the two half words", NEW, 8)
blk(7.4, 3.2, 3.0, 1.2, "16-symbol delay line\n(D = 8 to 10)\nthe answer of the synchroniser\nis ready before symbol 1", NEW, 8)
arr(13.0, 5.3, 13.0, 4.4); arr(12.6, 5.3, 9.9, 4.4)
blk(3.6, 1.7, 3.0, 1.2, "derotation by the NCO\n(1024-entry sin / cos table)", OLD); blk(0.2, 1.7, 2.7, 1.2, "16-QAM slicer\nlevels +-1, +-3 (x 4096),\nthresholds 0, +-8192", NEW, 8)
arr(8.9, 3.2, 6.6, 2.5); arr(3.6, 2.3, 2.9, 2.3); ax.text(5.0, 3.05, "z", fontsize=9)
blk(0.2, 0.1, 3.4, 1.1, "phase detector (shift-add)\ndata: Im(z conj s); pilot x3;\nknown CP / word symbols (aided)", NEW, 8); blk(4.0, 0.1, 2.2, 1.1, "loop filter\nCA, CB -> omega, theta", OLD)
arr(1.5, 1.7, 1.5, 1.2); arr(3.6, 0.65, 4.0, 0.65); arr(5.1, 1.2, 5.1, 1.7, c=ORANGE); ax.text(5.2, 1.45, "theta", fontsize=8, color=ORANGE)
arr(12.4, 3.2, 12.4, 2.6, c=ORANGE); blk(10.6, 1.5, 3.2, 1.1, "events: position counter\n(CP 0-7, word 8-70, data 71-966),\ntheta0 and w at every lock", NEW, 8); arr(10.6, 2.05, 6.6, 2.1, c=ORANGE); arr(10.6, 1.7, 4.4, 1.2, c=ORANGE, ls="--")
blk(7.0, 0.1, 3.2, 1.1, "Gray decision; PRBS-15 checker\n(symbol and bit errors, frames)\nEVM sums, capture RAM (1024)", NEW, 8); arr(2.9, 2.0, 7.0, 0.9)
blk(10.8, 0.1, 3.0, 1.1, "AXI-Lite registers 0x00-0xD8\ncapture RAM at 0x1000", OLD, 8); arr(10.2, 0.65, 10.8, 0.65)
ax.add_patch(plt.Rectangle((0.2, 6.85), 0.3, 0.2, fc=OLD, ec="k")); ax.text(0.6, 6.95, "as in the QPSK receiver", va="center", fontsize=9); ax.add_patch(plt.Rectangle((3.2, 6.85), 0.3, 0.2, fc=NEW, ec="k")); ax.text(3.6, 6.95, "new or changed for 16-QAM", va="center", fontsize=9)
ax.set_title("The 16-QAM receiver (rtl/qam16_rx.v, ID 0xDD520006): the engine runs once per symbol, about 70 of the 104 clocks at 100 MHz", fontsize=10); save(fig, "qam16_fig_block_rx.png")

# 6. the phase detector --------------------------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
rng = np.random.default_rng(5); s = (rng.choice([-3, -1, 1, 3], 400) + 1j * rng.choice([-3, -1, 1, 3], 400)) / np.sqrt(10); th = 0.2; z = s * np.exp(1j * th) + 0.05 * (rng.standard_normal(400) + 1j * rng.standard_normal(400))
ax[0].scatter(z.real, z.imag, s=5, c=GREY); ax[0].scatter(s.real[:16], s.imag[:16], s=0)
zi = z[np.argmax(np.abs(z))]; ds = np.round(((zi * np.exp(-1j * 0)) * np.sqrt(10) + 3) / 2) * 2 - 3; sh = (np.round((zi.real * np.sqrt(10) + 3) / 2) * 2 - 3 + 1j * (np.round((zi.imag * np.sqrt(10) + 3) / 2) * 2 - 3)) / np.sqrt(10)
ax[0].scatter([zi.real], [zi.imag], c=RED, s=40); ax[0].scatter([sh.real], [sh.imag], c=BLUE, s=60, marker="x"); ax[0].plot([0, zi.real], [0, zi.imag], c=RED, lw=0.8); ax[0].plot([0, sh.real], [0, sh.imag], c=BLUE, lw=0.8)
ax[0].text(0.02, 0.02, "z (red) against the sliced symbol s (blue):\ne = Im(z conj s) = zq*si - zi*sq\nsi, sq in {+-1, +-3}: shift-add only (3x = 2x + x)", transform=ax[0].transAxes, fontsize=8, va="bottom")
ax[0].set(title="Decision-directed phase error, rotation 0.2 rad", aspect="equal", xlabel="I", ylabel="Q"); ax[0].grid(alpha=0.3)
ax[1].axis("off"); ax[1].set_xlim(0, 10); ax[1].set_ylim(0, 6)
rows = [("data symbols (882)", "e = Im(z conj s), s = the slicer decision", BLUE, "weight 1"), ("pilots (14)", "e = 3 zq p, p = +-1 known: no decision error", RED, "weight 3 (register PCFG)"),
        ("word and CP (71)", "e = Im(z conj ZC_n): known symbols, aided mode", ORANGE, "register: aided or frozen"), ("at every lock", "theta0 and w from the word set the phase and frequency of the loop", GREEN, "removes the 4-fold ambiguity")]
for i, (a, b, c, d) in enumerate(rows): y = 5.0 - i * 1.3; ax[1].add_patch(plt.Rectangle((0.1, y - 0.3), 0.35, 0.6, fc=c, ec="k")); ax[1].text(0.7, y + 0.18, a, fontsize=10, fontweight="bold", va="center"); ax[1].text(0.7, y - 0.2, b + "   (" + d + ")", fontsize=8.5, va="center")
ax[1].set_title("What drives the loop, symbol by symbol", fontsize=10); fig.tight_layout(); save(fig, "qam16_fig_pll.png")

# 7. EVM against the received level -------------------------------------------------------------------------------------------------------------
S = np.linspace(25, 520, 400); thermal = (8.1 / S) ** 2; bad = 0.0115 * (137 / S) ** 2 + 0.013
fig, ax = plt.subplots(figsize=(9.5, 5.2))
ax.semilogx(S, 10 * np.log10(thermal), c=GREEN, label="good state: thermal noise only (8.1 counts in 1.3 MHz)"); ax.semilogx(S, 10 * np.log10(bad), c=RED, label="bad state, model of the link report (fixed floor + -19 dB multiplicative part)")
ax.axhline(-10.3, c=BLUE, ls="--"); ax.text(26, -10.9, "QPSK: SER 1e-3 needs EVM -10.3 dB", color=BLUE, fontsize=8); ax.axhline(-17.6, c=ORANGE, ls="--"); ax.text(26, -18.2, "16-QAM: SER 1e-3 needs EVM -17.6 dB (white-noise theory)", color=ORANGE, fontsize=8)
pts = [(137, -16.3, RED, "o"), (83, -14.1, RED, "o"), (55, -10.1, RED, "o"), (96, -17.5, RED, "o"), (80, -17.3, RED, "s"), (115, -22.4, GREEN, "o"), (110, -22.0, GREEN, "o"), (500, -22.7, GREEN, "^")]
for x_, y_, c_, m_ in pts: ax.scatter([x_], [y_], c=c_, marker=m_, s=45, zorder=5)
ax.text(300, -22.0, "close range, live notebook", fontsize=8); ax.text(62, -9.4, "live notebook, weak link", fontsize=8)
ax.set(xlabel="received level (ADC counts rms at RX gain 76)", ylabel="EVM (dB)", ylim=(-28, -4), title="Measured EVM against the received level, B210 -> P501 (squares: 480 ksym/s)"); ax.legend(loc="lower left", fontsize=8); ax.grid(alpha=0.3, which="both"); save(fig, "qam16_fig_evm_level.png")

# 8. the method ------------------------------------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(13, 2.9)); ax.set_xlim(0, 13); ax.set_ylim(0, 3); ax.axis("off")
steps = [("float model", "FrameRxHW: ZC sync + PLL\n1 sample per symbol\nstudies, thresholds, gains"), ("integer model", "qam16_rx_fixed.py\n4 sps, front end, FLL\nbit-exact numbers"), ("RTL + xsim", "qam_zc_sync.v, qam16_rx.v\nsame results to the last bit\n(0 mismatches)"), ("overlay", "p501_qam16_trx\nVivado 12 min, WNS +0.4 ns\ndriver and notebook"), ("board", "digital loopback: EVM -30 dB\nair: P501 -> P501, B210 -> P501\nADC capture + the model")]
for i, (t, d) in enumerate(steps):
    x = 0.2 + i * 2.6; ax.add_patch(FancyBboxPatch((x, 0.5), 2.2, 2.0, boxstyle="round,pad=0.05", fc=["#e2e8f0", "#bee3f8", "#c6f6d5", "#feebc8", "#fed7d7"][i], ec="k")); ax.text(x + 1.1, 2.15, t, ha="center", fontweight="bold", fontsize=10); ax.text(x + 1.1, 1.3, d, ha="center", va="center", fontsize=8)
    if i < 4: ax.annotate("", (x + 2.6, 1.5), (x + 2.25, 1.5), arrowprops=dict(arrowstyle="-|>"))
ax.set_title("Reference first, then one stage at a time: every stage must reproduce the previous one", fontsize=10); save(fig, "qam16_fig_method.png")
