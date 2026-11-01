#!/usr/bin/env python3
"""Block diagrams of tutorial 6, A.4b and A.6, each block with a small plot of the signal at that point.
The signals come from the model: an STS frame (ofdm_model.tx_frame, 'sts16') through a channel with a carrier offset of 9 kHz, a fractional delay and noise at 22 dB per subcarrier, 100 samples of noise in front of the frame.
    python3 make_figures_ofdm_diagrams.py        writes ofdm_t_detector_textbook.png, ofdm_t_detector.png, ofdm_t_fine_cfo_textbook.png, ofdm_t_fine_cfo.png, ofdm_t_rx_textbook.png, ofdm_t_rx_ours.png in ../img"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ofdm_model as Fm
IMG = os.path.join(HERE, "..", "img")
FS = Fm.FS
C = dict(sc="#e07020", tr="#2e8b57", data="#2b6cb0", grey="#a0aec0", fpga="#bee3f8", old="#e2e8f0", re="#2b6cb0", im="#c53030", ref="#888888")
LEAD, CFO, SNR = 100, 9e3, 22
N0, N1 = 70, 350                                              # the samples plotted in every inset


# ---------------------------------------------------------------- the signals
def make_signals():
    x, _ = Fm.tx_frame(preamble="sts16"); rng = np.random.default_rng(4)
    y = Fm.channel(x, SNR, cfo_hz=CFO, tau=0.0, lead=LEAD, trail=60, rng=rng)
    L, W = 16, 48; n = np.arange(len(y))
    d = np.zeros(len(y), complex); d[L:] = y[:-L]                       # delayed
    p = y * np.conj(d); p[:L] = 0                                       # the product
    cs = np.cumsum(p); S = np.zeros(len(y), complex); S[W:] = cs[W:] - cs[:-W]
    e = np.abs(y) ** 2; es = np.cumsum(e); E = np.zeros(len(y)); E[W:] = es[W:] - es[:-W]
    R = S / np.maximum(E, 1e-9)                                          # the divider of the textbook
    M = np.abs(R)
    ea = np.zeros(len(y)); ea[W:] = E[:-W]
    return dict(y=y, d=d, p=p, S=S, E=E, EA=ea, R=R, M=M, n=n, L=L, W=W)


SIG = make_signals()


# ---------------------------------------------------------------- drawing helpers
class Canvas:
    def __init__(self, W, H, figsize, y0=0.0):
        self.fig = plt.figure(figsize=figsize); self.W, self.H, self.y0 = W, H, y0
        self.ax = self.fig.add_axes([0, 0, 1, 1]); self.ax.set_xlim(0, W); self.ax.set_ylim(y0, H); self.ax.axis("off")

    def box(self, x, y, w, h, text, fc="white", fs=8.5, ec="k", ls="-", tc="k"):
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1, ls=ls)); self.ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc)

    def circle(self, x, y, sym, r=0.3):
        self.ax.add_patch(Circle((x, y), r, fc="white", ec="k", lw=1.2)); self.ax.text(x, y, sym, ha="center", va="center", fontsize=14)

    def arrow(self, x0, y0, x1, y1, color="k", ls="-"):
        self.ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.2, ls=ls))

    def line(self, xs, ys, color="k", lw=1.2, ls="-"):
        self.ax.plot(xs, ys, color=color, lw=lw, ls=ls)

    def text(self, x, y, s, **kw):
        self.ax.text(x, y, s, **kw)

    def inset(self, x, y, w, h, title):
        a = self.fig.add_axes([x / self.W, (y - self.y0) / (self.H - self.y0), w / self.W, h / (self.H - self.y0)])
        a.set_title(title, fontsize=6.5, pad=1.5); a.tick_params(labelsize=5, length=2, pad=1); a.set_facecolor("#fafafa")
        for s in a.spines.values(): s.set_linewidth(0.6)
        return a

    def save(self, name):
        self.fig.savefig(os.path.join(IMG, name), dpi=140); plt.close(self.fig)


def scope(a, series, vlines=(), hlines=(), shade=None, marks=(), ylim=None, xlabel=False):
    """series: list of (values over n, color, linewidth); drawn for N0 .. N1"""
    n = SIG["n"]; sl = slice(N0, N1)
    for v, col, lw in series: a.plot(n[sl], v[sl], color=col, lw=lw)
    for v in vlines: a.axvline(v, color=C["ref"], lw=0.7, ls="--")
    for v in hlines: a.axhline(v, color=C["sc"], lw=0.7, ls="--")
    if shade: a.axvspan(shade[0], shade[1], color=C["sc"], alpha=0.18, lw=0)
    for (mx, my, txt) in marks: a.plot([mx], [my], "o", color=C["im"], ms=3); a.annotate(txt, (mx, my), xytext=(3, -8), textcoords="offset points", fontsize=5.5, color=C["im"])
    a.set_xlim(N0, N1)
    if ylim: a.set_ylim(*ylim)
    a.set_yticks([]) if ylim is None else None
    a.set_xticks([LEAD, LEAD + 128, LEAD + 288]) if xlabel else a.set_xticks([])


STS_END = LEAD + 128                                                    # the plateau of the metric ends where the STS ends
PLAT = (LEAD + 16 + 48 - 1, STS_END - 1)                                # window ends inside the STS: 163 .. 227
peak = int(np.argmax(np.where((SIG["n"] > N0) & (SIG["n"] < N1), SIG["M"], 0)))


def conj_pairs():                                                         # the 64-sample windows for the fine carrier: T1 and T2 (after the 100 + 128 + 32 samples)
    t1 = LEAD + 160; y = SIG["y"]
    return y[t1:t1 + 64], y[t1 + 64:t1 + 128]


# ---------------------------------------------------------------- 1. the textbook detector
def fig_detector_textbook():
    cv = Canvas(14.6, 8.3, (14.6, 8.3)); y = SIG["y"]
    cv.text(0.1, 4.55, "x[n]", fontsize=10, va="center", ha="left")
    cv.line([0.8, 6.2], [4.6, 4.6]); cv.line([2.5, 2.5], [1.8, 6.6]); cv.line([2.5, 2.8], [6.6, 6.6]); cv.arrow(2.65, 6.6, 2.9, 6.6)
    cv.box(2.9, 6.3, 1.3, 0.6, "delay  z$^{-L}$"); cv.arrow(4.2, 6.6, 4.6, 6.6); cv.box(4.6, 6.3, 0.9, 0.6, "( · )*", fs=10)
    cv.line([5.5, 6.5], [6.6, 6.6]); cv.arrow(6.5, 6.6, 6.5, 4.95); cv.circle(6.5, 4.6, "×"); cv.arrow(6.2, 4.6, 6.2, 4.6)
    cv.arrow(5.9, 4.6, 6.2, 4.6); cv.arrow(6.8, 4.6, 7.4, 4.6); cv.box(7.4, 4.2, 1.5, 0.8, "moving\naverage (S)")
    cv.line([2.5, 2.8], [1.8, 1.8]); cv.arrow(2.65, 1.8, 2.9, 1.8); cv.box(2.9, 1.5, 1.2, 0.6, "| · |$^2$", fs=10); cv.arrow(4.1, 1.8, 7.4, 1.8); cv.box(7.4, 1.4, 1.5, 0.8, "moving\naverage (E)")
    cv.arrow(8.9, 4.6, 9.8, 4.6); cv.circle(10.1, 4.6, "÷"); cv.line([8.9, 10.1], [1.8, 1.8]); cv.arrow(10.1, 1.8, 10.1, 4.3)
    cv.arrow(10.4, 4.6, 10.8, 4.6); cv.box(10.8, 4.3, 1.1, 0.6, "| · |", fs=10); cv.arrow(11.9, 4.6, 12.5, 4.6); cv.box(12.5, 4.3, 1.5, 0.6, "max ( · )", fs=10)
    # the signals
    a = cv.inset(0.15, 4.95, 2.1, 1.05, "x[n]  (Re): noise, then the frame"); scope(a, [(y.real, C["re"], 0.5)], vlines=(LEAD,), ylim=None)
    a = cv.inset(2.75, 7.1, 1.9, 1.05, "x[n] and x[n−16]  (Re): the STS repeats (with noise and 13° of rotation)"); scope(a, [(SIG["d"].real, C["im"], 0.6), (y.real, C["re"], 0.5)], vlines=(LEAD,))
    a = cv.inset(5.0, 2.55, 1.9, 1.05, "product x[n] conj x[n−16]"); scope(a, [(SIG["p"].real, C["re"], 0.6), (SIG["p"].imag, C["im"], 0.6)], vlines=(LEAD,))
    a = cv.inset(7.3, 5.25, 1.8, 1.05, "S[n] = moving average:  |S|"); scope(a, [(np.abs(SIG["S"]), C["re"], 0.8)], shade=PLAT)
    a = cv.inset(2.8, 2.35, 1.7, 1.0, "|x|$^2$"); scope(a, [(np.abs(y) ** 2, C["re"], 0.5)], vlines=(LEAD,))
    a = cv.inset(7.3, 2.45, 1.8, 1.0, "E[n] = moving average:  E"); scope(a, [(SIG["E"], C["re"], 0.8)], shade=PLAT)
    a = cv.inset(9.35, 5.25, 1.8, 1.05, "S / E  (Re, Im): constant in the plateau"); scope(a, [(SIG["R"].real, C["re"], 0.7), (SIG["R"].imag, C["im"], 0.7)], shade=PLAT, ylim=(-1.2, 1.2))
    a = cv.inset(10.6, 2.75, 1.8, 1.0, "|S / E|: the plateau, 1 inside the STS"); scope(a, [(SIG["M"], C["re"], 0.9)], shade=PLAT, ylim=(0, 1.15))
    a = cv.inset(12.3, 5.25, 2.0, 1.05, "max: the largest value"); scope(a, [(SIG["M"], C["re"], 0.9)], shade=PLAT, marks=[(peak, SIG["M"][peak], " max")], ylim=(0, 1.15))
    cv.text(13.25, 3.95, "→ frame start", ha="center", fontsize=8.5, color="#444")
    cv.text(0.1, 0.9, "L = the period of the repeat (16 for the STS, 32 for Schmidl and Cox). The signals are the model's STS frame: 100 samples of noise, then the STS (the shaded plateau: the windows that lie inside it), the guard interval, T1, T2;"
            "\nthe carrier offset is 9 kHz and the SNR 22 dB. The divider makes the metric independent of the level of the signal; max( · ) takes the sample where the two windows match best, which on a flat plateau is a noisy choice.", fontsize=8.2, color="#444", va="center")
    cv.text(10.2, 8.05, "The textbook delay-and-correlate detector (Schmidl and Cox), with the signal at every block", fontsize=11, ha="center", va="center")
    cv.save("ofdm_t_detector_textbook.png")


# ---------------------------------------------------------------- 2. our detector
def fig_detector():
    cv = Canvas(17.0, 7.1, (17.0, 7.9), y0=-0.8); y = SIG["y"]; OR = C["sc"]
    cv.text(0.1, 4.55, "x[n]", fontsize=9, va="center")
    cv.line([0.8, 5.0], [4.6, 4.6]); cv.line([1.2, 1.2], [2.0, 6.0]); cv.line([1.2, 1.4], [6.0, 6.0]); cv.arrow(1.3, 6.0, 1.5, 6.0)
    cv.box(1.5, 5.7, 1.3, 0.6, "delay\nz$^{-16}$  (S&C: 32)", C["fpga"], 8); cv.arrow(2.8, 6.0, 3.3, 6.0); cv.box(3.3, 5.7, 1.0, 0.6, "conj\n( · )*", C["fpga"], 8)
    cv.line([4.3, 5.0], [6.0, 6.0]); cv.arrow(5.0, 6.0, 5.0, 4.95); cv.circle(5.0, 4.6, "×"); cv.arrow(4.7, 4.6, 4.7, 4.6); cv.arrow(4.4, 4.6, 4.7, 4.6)
    cv.arrow(5.3, 4.6, 5.9, 4.6); cv.box(5.9, 4.15, 1.6, 0.9, "moving sum\nof 48 products\n= S  (complex)", C["fpga"], 8)
    cv.line([1.2, 1.4], [2.0, 2.0]); cv.arrow(1.3, 2.0, 1.5, 2.0); cv.box(1.5, 1.7, 1.3, 0.6, "| · |$^2$", C["fpga"], 8); cv.arrow(2.8, 2.0, 5.9, 2.0)
    cv.box(5.9, 1.55, 1.6, 0.9, "moving sum\nof 48 samples\n= E  (newer 48)", C["fpga"], 8)
    cv.box(5.9, 0.25, 1.6, 0.9, "the same sum,\n48 samples earlier\n= EA", C["fpga"], 8, ec=OR); cv.arrow(6.7, 1.55, 6.7, 1.15)
    cv.box(8.2, 1.1, 3.1, 3.6, "", C["fpga"]); cv.text(9.75, 4.45, "decision  (once per ADC sample)", ha="center", fontsize=8.5, weight="bold")
    cv.text(9.75, 3.7, "|S'|$^2$ = S'$_r^2$ + S'$_i^2$,   E'$^2$\n(S' = S >> 8, E' = E >> 8)\n\n256 |S'|$^2$  ≥  THR · E'$^2$\nTHR = 166 → M = |S|$^2$/E$^2$ ≥ 0.65\n(no division: a compare)", ha="center", va="center", fontsize=8.2)
    cv.text(9.75, 2.35, "and   EA ≤ 2 E   (guard)", ha="center", fontsize=8.5, color=OR, weight="bold"); cv.text(9.75, 1.95, "a strong frame followed by a quiet slot\nmust not fire it", ha="center", va="center", fontsize=7.6, color=OR)
    cv.text(9.75, 1.45, "and   E'  ≥  EMIN   (not noise only)", ha="center", fontsize=8.2)
    cv.arrow(7.5, 4.6, 8.2, 4.1); cv.arrow(7.5, 2.0, 8.2, 2.0); cv.arrow(7.5, 0.7, 8.2, 1.4)
    cv.box(11.9, 4.1, 2.5, 0.9, "first window above: n0\nstore 144 windows\nof M, S and E", C["fpga"], 8); cv.arrow(11.3, 4.5, 11.9, 4.5)
    cv.box(11.9, 2.55, 2.5, 1.0, "plateau, not max(·):\nwindows with M ≥ 24/32 of the\npeak: first .. last", C["fpga"], 8, ec=OR); cv.arrow(13.15, 4.1, 13.15, 3.55)
    cv.box(11.9, 0.3, 2.5, 1.7, "s0 = n0 + (first+last+1)/2 − 32\n\ncoarse carrier:\nCORDIC of Σ S over the plateau\n\ngain G from E at the peak", C["fpga"], 8); cv.arrow(13.15, 2.55, 13.15, 2.0)
    # the signals
    a = cv.inset(0.08, 2.9, 1.05, 0.95, "x[n]  (Re)"); scope(a, [(y.real, C["re"], 0.5)], vlines=(LEAD,))
    a = cv.inset(5.0, 2.85, 1.7, 0.95, "x conj x$_{n-16}$  (Re, Im)"); scope(a, [(SIG["p"].real, C["re"], 0.5), (SIG["p"].imag, C["im"], 0.5)], vlines=(LEAD,))
    a = cv.inset(5.9, 5.3, 1.8, 0.95, "|S|"); scope(a, [(np.abs(SIG["S"]), C["re"], 0.8)], shade=PLAT)
    a = cv.inset(3.0, 2.55, 1.9, 0.95, "|x|$^2$"); scope(a, [(np.abs(y) ** 2, C["re"], 0.5)], vlines=(LEAD,))
    a = cv.inset(7.7, 2.55, 0.001, 0.001, "")                                                                  # (placeholder, removed below)
    a.remove()
    M = SIG["M"]; n0 = int(np.nonzero((SIG["n"] > N0) & (M > 0.65))[0][0]); pk = M[n0:n0 + 144].max(); sel = np.nonzero(M[n0:n0 + 144] >= pk * 24 / 32)[0]
    first, last = n0 + sel[0], n0 + sel[-1]
    a = cv.inset(14.7, 3.95, 2.15, 1.05, "M ≥ 0.65: the first window, n0"); scope(a, [(M, C["re"], 0.9)], hlines=(0.65,), marks=[(n0, M[n0], " n0")], ylim=(0, 1.15))
    a = cv.inset(14.7, 2.45, 2.15, 1.05, "M ≥ 24/32 of the peak: first .. last"); scope(a, [(M, C["re"], 0.9)], hlines=(pk * 24 / 32,), shade=(first, last), ylim=(0, 1.15)); a.axvline(0.5 * (first + last), color=C["im"], lw=0.8)
    a = cv.inset(14.7, 0.4, 2.15, 1.5, "arg S over the plateau: the coarse carrier"); scope(a, [(np.angle(SIG["S"]), C["re"], 0.8)], shade=(first, last), ylim=(-3.3, 3.3))
    a.axhline(2 * np.pi * CFO * 16 / FS, color=C["im"], lw=0.8, ls="--"); a.set_yticks([2 * np.pi * CFO * 16 / FS]); a.set_yticklabels(["2π f 16/fs"], fontsize=5)
    cv.text(0.1, -0.4, "The signals are the model's STS frame (carrier offset 9 kHz, SNR 22 dB). Orange = what the textbook diagram does not have; shaded: the windows inside the STS.\n"
            "STS receiver; for S&C: lag 32, 32 products, 72 windows, 29/32 of the peak, s0 = n0 + centre − 8. Textbook: ... → divide S by E → | · | → max( · ).", fontsize=8, color="#444", va="center")
    cv.text(8.5, 6.8, "The frame detector of tutorial 6 (ofdm_detect.v) with the signal at every block", fontsize=11, ha="center", va="center")
    cv.save("ofdm_t_detector.png")


# ---------------------------------------------------------------- 3. the textbook fine carrier estimator
def fig_fine_cfo_textbook():
    cv = Canvas(13.8, 7.0, (13.8, 7.0)); a1, a2 = conj_pairs(); t = np.arange(64)
    cv.text(0.1, 4.35, "r[n]", fontsize=10, va="center"); cv.line([0.8, 4.8], [4.4, 4.4]); cv.line([1.2, 1.2], [4.4, 5.8]); cv.line([1.2, 1.4], [5.8, 5.8]); cv.arrow(1.3, 5.8, 1.5, 5.8)
    cv.box(1.5, 5.5, 1.5, 0.6, "delay  z$^{-N}$\n(one symbol)", "white", 9); cv.arrow(3.0, 5.8, 3.4, 5.8); cv.box(3.4, 5.5, 0.9, 0.6, "( · )*", fs=10)
    cv.line([4.3, 5.1], [5.8, 5.8]); cv.arrow(5.1, 5.8, 5.1, 4.7); cv.circle(5.1, 4.4, "×"); cv.arrow(4.65, 4.4, 4.8, 4.4); cv.arrow(5.4, 4.4, 6.0, 4.4)
    cv.box(6.0, 4.0, 2.0, 0.8, "sum over the N samples\nof the second symbol\nP = Σ r[n+N] conj r[n]", "white", 8.5); cv.arrow(8.0, 4.4, 8.7, 4.4)
    cv.box(8.7, 4.0, 1.3, 0.8, "arg ( · )\n(atan2)", "white", 9); cv.arrow(10.0, 4.4, 10.6, 4.4); cv.box(10.6, 4.0, 2.3, 0.8, "÷ (2π N T$_s$)\n= f$_{fine}$", "white", 9)
    # signals
    a = cv.inset(0.2, 2.15, 2.3, 1.35, "r[n] (Re): T1, then T2"); a.plot(t, a1.real, color=C["re"], lw=0.7, label="T1"); a.plot(t + 64, a2.real, color=C["im"], lw=0.7, label="T2"); a.set_xticks([0, 64, 128]); a.set_yticks([])
    a = cv.inset(2.9, 2.15, 2.0, 1.35, "T2 and T1 overlaid: a rotation"); a.plot(t, a1.real, color=C["re"], lw=0.7); a.plot(t, a2.real, color=C["im"], lw=0.7); a.set_xticks([0, 64]); a.set_yticks([])
    prod = a2 * np.conj(a1); P = prod.sum()
    a = cv.inset(5.2, 2.15, 1.55, 1.35, "r[n+N] conj r[n]: 64 products"); a.scatter(prod.real, prod.imag, s=3, color=C["re"]); a.axhline(0, color=C["ref"], lw=0.5); a.axvline(0, color=C["ref"], lw=0.5); a.set_aspect("equal"); a.set_xticks([]); a.set_yticks([])
    a = cv.inset(7.3, 2.15, 1.5, 1.35, "the sum P"); a.annotate("", xy=(P.real, P.imag), xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color=C["im"], lw=1.5)); r = abs(P) * 1.2; a.set_xlim(-r, r); a.set_ylim(-r, r)
    a.axhline(0, color=C["ref"], lw=0.5); a.axvline(0, color=C["ref"], lw=0.5); a.set_aspect("equal"); a.set_xticks([]); a.set_yticks([])
    th = np.angle(P); a = cv.inset(9.0, 2.15, 1.4, 1.35, "arg P"); tt = np.linspace(0, 2 * np.pi, 100); a.plot(np.cos(tt), np.sin(tt), color=C["ref"], lw=0.5); a.plot([0, np.cos(th)], [0, np.sin(th)], color=C["im"], lw=1.5)
    a.plot(np.cos(np.linspace(0, th, 20)) * 0.4, np.sin(np.linspace(0, th, 20)) * 0.4, color=C["re"], lw=1); a.text(0.5, -0.1, "%.2f rad" % th, fontsize=6, ha="center"); a.set_aspect("equal"); a.set_xticks([]); a.set_yticks([])
    f = th / (2 * np.pi * 64 / FS); cv.text(11.75, 3.55, "f = %.0f Hz\n(true: 9000 Hz)" % f, ha="center", va="center", fontsize=8.5, color=C["im"])
    cv.text(0.1, 1.2, "r[n+N] = r[n] e$^{j 2π f N T_s}$ + noise   →   arg P = 2π f N T$_s$   (Moose, 1994: the maximum-likelihood estimate).   Range: |f| < 1 / (2 N T$_s$) = half a subcarrier spacing (30 kHz here).   Error: variance of the phase 1 / (N · SNR).", fontsize=8.8, va="center")
    cv.text(0.1, 0.7, "The signals are the model's T1 and T2 (64 samples each, 64 apart), 9 kHz offset, SNR 22 dB: the products all point the same way, so their sum does too. The plain estimator has no check that the two symbols really repeat.", fontsize=8.2, color="#444", va="center")
    cv.text(6.9, 6.75, "The textbook estimator of the fine carrier offset from two identical training symbols, with the signal at every block", fontsize=11, ha="center", va="center")
    cv.save("ofdm_t_fine_cfo_textbook.png")


# ---------------------------------------------------------------- 4. the fine carrier of the FPGA
def fig_fine_cfo():
    cv = Canvas(14.6, 9.0, (14.6, 9.0)); OR = C["sc"]; a1, a2 = conj_pairs(); t = np.arange(64)
    k = 13.0 / 480.0; x0 = 0.6; y0 = 7.75
    for a, b, tx, fc in ((0, 128, "STS 128", C["sc"]), (128, 160, "GI2", C["grey"]), (160, 224, "T1  (64)", C["tr"]), (224, 288, "T2  (64)", C["tr"]), (288, 480, "data symbols ...", C["data"])):
        cv.ax.add_patch(plt.Rectangle((x0 + a * k, y0), (b - a) * k, 0.6, fc=fc, ec="k", lw=1, alpha=0.75)); cv.text(x0 + (a + b) / 2 * k, y0 + 0.3, tx, ha="center", va="center", fontsize=8.5)
    cv.ax.annotate("", xy=(x0 + 224 * k, y0 - 0.15), xytext=(x0 + 160 * k, y0 - 0.15), arrowprops=dict(arrowstyle="<|-|>", color="k", lw=1.2)); cv.text(x0 + 192 * k, y0 - 0.35, "lag 64", ha="center", va="center", fontsize=8.5, bbox=dict(fc="white", ec="none", pad=1))
    cv.text(x0 + 235 * k, y0 - 0.35, "windows: T1 at s0 + 154, T2 at s0 + 218 (6 samples early, inside the prefix)", fontsize=8, color="#444", va="center")
    cv.text(0.6, 8.75, "The fine carrier from the two long training symbols (STS frame; S&C: T1 at s0 + 90, T2 at s0 + 170, lag 80), with the signal at every block", fontsize=10.5, weight="bold")
    cv.box(0.2, 4.4, 1.9, 1.0, "samples from the\nsample RAM\n× gain G\nNCO: coarse w$_c$", C["fpga"], 8)
    cv.box(2.6, 5.1, 1.7, 0.7, "T1 window\n64 samples  a[n]", C["tr"], 8); cv.box(2.6, 3.95, 1.7, 0.7, "T2 window\n64 samples  b[n]", C["tr"], 8)
    cv.arrow(2.1, 5.1, 2.6, 5.45); cv.arrow(2.1, 4.8, 2.6, 4.3)
    cv.box(4.8, 4.1, 2.0, 1.4, "complex MAC\nP = Σ b[n] conj(a[n])\n64 products\nP$_r$ = Σ(b$_r$a$_r$ + b$_i$a$_i$)\nP$_i$ = Σ(b$_i$a$_r$ − b$_r$a$_i$)", C["fpga"], 8)
    cv.arrow(4.3, 5.45, 4.8, 5.1); cv.arrow(4.3, 4.3, 4.8, 4.5)
    cv.box(7.3, 4.4, 1.5, 0.9, "CORDIC\nturns(P) = arg P\n/ 2π  (20 bit)", C["fpga"], 8); cv.arrow(6.8, 4.85, 7.3, 4.85)
    cv.box(9.2, 4.4, 1.9, 0.9, "× K / 1024\nK = 65536 (lag 64)\nK = 52429 (lag 80)", C["fpga"], 8); cv.arrow(8.8, 4.85, 9.2, 4.85)
    cv.circle(11.7, 4.85, "+"); cv.arrow(11.1, 4.85, 11.4, 4.85); cv.text(10.15, 4.1, "w$_f$  (turns × 2$^{32}$ per sample)", ha="center", fontsize=8); cv.text(11.7, 5.5, "w$_c$ (coarse)", ha="center", fontsize=8.5); cv.arrow(11.7, 5.4, 11.7, 5.17)
    cv.arrow(12.0, 4.85, 12.5, 4.85); cv.box(12.5, 4.4, 1.9, 0.9, "w = w$_c$ + w$_f$\nNCO for all the\nsymbols that follow", C["fpga"], 8)
    cv.box(2.6, 2.0, 5.2, 1.3, "repeat check:  E1 = Σ|a|$^2$,  E2 = Σ|b|$^2$   (both >> 10)\n2 (P$_r^2$ + P$_i^2$)  ≥  E1 · E2 ?\nif not, the two symbols do not repeat:\na false detection, the frame is rejected", C["fpga"], 8, ec=OR)
    cv.arrow(5.8, 4.1, 5.2, 3.3, OR); cv.text(8.1, 2.65, "(counted as 'rejected' in the registers)", fontsize=8, color=OR)
    # the signals
    prod = a2 * np.conj(a1); P = prod.sum(); th = np.angle(P)
    a = cv.inset(2.45, 5.95, 1.9, 0.85, "a[n] (Re), T1"); a.plot(t, a1.real, color=C["re"], lw=0.7); a.set_xticks([]); a.set_yticks([])
    a = cv.inset(0.2, 2.9, 2.0, 0.9, "b[n] (Re), T2: T1 turned by 54°"); a.plot(t, a2.real, color=C["im"], lw=0.7); a.plot(t, a1.real, color=C["re"], lw=0.5, alpha=0.5); a.set_xticks([]); a.set_yticks([])
    a = cv.inset(4.95, 5.75, 1.7, 1.15, "64 products b conj a"); a.scatter(prod.real, prod.imag, s=3, color=C["re"]); a.axhline(0, color=C["ref"], lw=0.5); a.axvline(0, color=C["ref"], lw=0.5); a.set_aspect("equal"); a.set_xticks([]); a.set_yticks([])
    a = cv.inset(7.3, 5.75, 1.5, 1.15, "arg P = %.2f rad" % th); tt = np.linspace(0, 2 * np.pi, 100); a.plot(np.cos(tt), np.sin(tt), color=C["ref"], lw=0.5); a.plot([0, np.cos(th)], [0, np.sin(th)], color=C["im"], lw=1.5)
    a.set_aspect("equal"); a.set_xticks([]); a.set_yticks([])
    f = th / (2 * np.pi * 64 / FS); cv.text(10.15, 3.4, "here, without the coarse correction first: arg P gives %.0f Hz (true 9000 Hz);\nin the receiver the coarse part is removed first and w$_f$ is only the small rest" % f, ha="center", va="center", fontsize=8.2, color=C["im"])
    cv.text(0.2, 1.45, "arg P = 2π f lag / fs   →   f$_{fine}$ = arg P / (2π lag / fs).   Unambiguous for |f| < fs / (2 lag) = 30 kHz (STS), 24 kHz (S&C): the coarse estimate (±120 / ±60 kHz) is good enough to stay inside.", fontsize=8.8, va="center")
    cv.text(0.2, 0.95, "Accuracy: the phase error has variance 1 / (64 · SNR) per sample SNR: 130 to 190 Hz rms at a link SNR of 20 to 23 dB (the B210 link: 130 to 290 Hz). A carrier error of 300 Hz costs 0.09 dB of EVM (sync study, E2).", fontsize=8.8, va="center")
    cv.text(0.2, 0.45, "Orange: the check. A free improvement found in the sync study: the same correlation over the guard interval GI2 and T1 as well (96 products instead of 64) is about 40 % more accurate.", fontsize=8.8, color=OR, va="center")
    cv.save("ofdm_t_fine_cfo.png")


# ---------------------------------------------------------------- 5. and 6. the whole receiver: the textbook block diagram and ours
def make_rx_signals():
    rng = np.random.default_rng(6)
    x, d = Fm.tx_frame(preamble="sts16"); y = Fm.channel(x, SNR, cfo_hz=CFO, tau=0.3, lead=LEAD, trail=60, rng=rng)
    R = Fm.receive(y, track="complex", return_all=True); Z0 = Fm.receive(y, track="none", return_all=True)["Z"]
    s0, f = R["s0"], R["f"]; n = np.arange(len(y)); xr = y * np.exp(-2j * np.pi * f / FS * (n - s0))
    t1 = s0 + 128 + 2 * Fm.CP - Fm.BACK
    pb = y[t1 + 64:t1 + 128] * np.conj(y[t1:t1 + 64]); pa = xr[t1 + 64:t1 + 128] * np.conj(xr[t1:t1 + 64])
    base = s0 + 128 + Fm.LTS_LEN; st = base + 10 * Fm.SYM
    Y = np.fft.fftshift(np.fft.fft(xr[st + Fm.CP - Fm.BACK:st + Fm.CP - Fm.BACK + 64]) / 8)
    w = y[LEAD:LEAD + 3840]; P = np.mean(np.abs(np.fft.fft(w.reshape(-1, 64), axis=1)) ** 2, axis=0)
    M, _ = Fm.timing_metric(y, 16)
    return dict(y=y, R=R, Z0=Z0, Z=R["Z"], xr=xr, pb=pb, pa=pa, sym=xr[st:st + Fm.SYM], Y=Y, P=np.fft.fftshift(P), M=M, s0=s0, d=d)


RXS = None


def fig_rx(ours):
    global RXS
    RXS = RXS or make_rx_signals(); S = RXS; y = S["y"]; R = S["R"]; BL = C["fpga"]; GR = "#edf2f7"; DG = "#a0aec0"
    cv = Canvas(17.4, 12.0, (17.4, 12.0)); fb = BL if ours else "white"
    # ---- top row: x, width, text
    top = [(0.9, 1.6, "AD9361\n3.84 MS/s" if ours else "Radio Rx", GR if ours else "white"),
           (2.8, 1.6, "ADC I/Q\nsample RAMs\n(2 × 1024 words)" if ours else "ADC\nI/Q", GR if ours else "white"),
           (4.7, 2.2, "ofdm_detect.v\ncompare 256|S|² ≥ THR·E²\nguard, plateau" if ours else "Packet detect\nAGC control", fb),
           (7.2, 2.2, "ofdm_derot.v\nNCO, gain G\n(coarse, then fine)" if ours else "Carrier offset\ncorrection", fb),
           (9.7, 2.0, "controller (ofdm_rx.v)\nwindow 6 samples early,\nprefix skipped" if ours else "Remove guard\ninterval", fb),
           (12.0, 1.8, "ofdm_fft.v\n64 points\nradix 2" if ours else "FFT", fb),
           (14.1, 2.2, "ofdm_data.v\nequaliser W·Y, pilots:\ng and slope" if ours else "Pilot\ntracking", fb)]
    yb, hb = 7.7, 0.9; yc = yb + hb / 2
    for x, w, t, fc in top: cv.box(x, yb, w, hb, t, fc, 7.6 if ours else 9.5)
    for i in range(len(top) - 1): cv.arrow(top[i][0] + top[i][1], yc, top[i + 1][0], yc)
    cv.text(0.35, 9.0, "▽", fontsize=18, ha="center", va="center"); cv.line([0.35, 0.35, 0.9], [8.7, yc, yc])
    # ---- the estimator
    ex, ew, ey, eh = 7.0, 3.8, 5.5, 0.9
    cv.box(ex, ey, ew, eh, "controller (fine pass) + ofdm_chan.v\nΔf = coarse (CORDIC of ΣS) + fine (MAC of T1, T2)\nH = (T1 + T2)/2 · conj(train);  W = conj(H) R / |H|²" if ours
           else "Carrier offset\nestimation\nchannel estimation", fb, 7.4 if ours else 9.5)
    cv.line([5.8, 5.8], [yb, yc - 2.25]); cv.arrow(5.8, yc - 2.25, ex, yc - 2.25)                              # packet detect -> estimator (the frame start and the coarse carrier)
    cv.line([9.55, 9.55], [yc, ey + eh + 0.35]); cv.arrow(9.55, ey + eh + 0.35, 9.55, ey + eh)                  # corrected samples -> estimator
    cv.arrow(8.0, ey + eh, 8.0, yb, ls=":"); cv.text(8.1, 6.95, "Δf̂", fontsize=11, style="italic", va="center")
    if not ours:
        cv.line([5.8, 1.7], [7.2, 7.2], ls=":"); cv.arrow(1.7, 7.2, 1.7, yb, ls=":"); cv.line([5.8, 5.8], [yb, 7.2], ls=":")
        cv.text(3.7, 7.0, "gain (AGC)", fontsize=8.5, ha="center", va="top")
    else:
        cv.text(3.7, 7.35, "no AGC loop: fixed RF gain, digital gain G from E at the peak", fontsize=7.8, ha="center", va="top", color="#444")
    # ---- the data path and the estimator's output go to the demapper
    cv.line([16.3, 16.9, 16.9, 3.0], [yc, yc, 4.0, 4.0]); cv.arrow(3.0, 4.0, 3.0, 3.1)
    cv.line([7.4, 7.4, 1.6], [ey, 4.6, 4.6], ls=":"); cv.arrow(1.6, 4.6, 1.6, 3.1, ls=":")
    f_txt = "Δf̂ = %.0f Hz (coarse %.0f + fine %.0f);  true 9000 Hz" % (R["f"], R["f_c"], R["f_f"])
    cv.text(7.6, 5.1, f_txt, fontsize=7.8, va="center", color=C["im"])
    # ---- the lower row
    yl, hl = 2.2, 0.9
    if ours:
        cv.box(1.0, yl, 2.6, hl, "slicer + checker (ofdm_data.v)\nGray bits, PRBS-15,\nsymbol and bit errors, EVM", BL, 7.6)
        for x0, t in ((4.1, "counters,\nEVM sums"), (6.9, "capture RAM\n1024 corrected symbols"), (9.7, "AXI-Lite\nregisters"), (12.5, "driver,\nnotebook, GNU Radio")): cv.box(x0, yl, 2.4, hl, t, GR, 8)
        for x0 in (3.6, 6.5, 9.3, 12.1): cv.arrow(x0, yl + hl / 2, x0 + 0.5 if x0 == 3.6 else x0 + 0.4, yl + hl / 2)
    else:
        cv.box(1.0, yl, 2.6, hl, "Demapper", "white", 9.5)
        for x0, t in ((4.1, "De-Interleaver"), (6.9, "De-Puncture"), (9.7, "Viterbi\nDecoding"), (12.5, "De-Scrambler")): cv.box(x0, yl, 2.4, hl, t, "white", 9.5, ec=DG, ls="--", tc="#888")
        for x0 in (3.6, 6.5, 9.3, 12.1): cv.arrow(x0, yl + hl / 2, x0 + 0.5 if x0 == 3.6 else x0 + 0.4, yl + hl / 2, color=DG, ls="--")
        cv.arrow(14.9, yl + hl / 2, 15.8, yl + hl / 2); cv.text(15.9, yl + hl / 2, "bits", fontsize=9, va="center")
    # ---- the signals
    n = np.arange(len(y)); fs = 5.0; tt = np.arange(64)

    def ins(x, yy, w, h, title): return cv.inset(x, yy, w, h, title)
    a = ins(0.9, 9.0, 1.6, 1.75, "spectrum of the signal:\n28 carriers of 60 kHz"); fr = np.fft.fftshift(np.fft.fftfreq(64, 1 / FS)) / 1e6; a.plot(fr, 10 * np.log10(S["P"] / S["P"].max()), color=C["re"], lw=0.8); a.set_xlabel("MHz", fontsize=5, labelpad=0); a.set_ylim(-35, 3)
    a = ins(2.8, 9.0, 1.6, 1.75, "x[n] (Re): noise,\nthen the frame"); a.plot(n[:420], y.real[:420], color=C["re"], lw=0.5); a.axvline(LEAD, color=C["ref"], lw=0.7, ls="--"); a.set_xticks([]); a.set_yticks([])
    a = ins(4.7, 9.0, 2.2, 1.75, "M[n] = |S/E|:  plateau, threshold 0.5"); a.plot(np.arange(len(S["M"])) + 63, S["M"], color=C["re"], lw=0.8); a.axhline(0.5, color=C["sc"], lw=0.7, ls="--"); a.set_xlim(0, 420); a.set_ylim(0, 1.15); a.set_xticks([])
    a = ins(7.2, 9.0, 2.2, 1.75, "T2·conj T1:  before (red), after (blue)"); sc = np.mean(np.abs(S["pb"])); a.scatter(S["pb"].real / sc, S["pb"].imag / sc, s=2, color=C["im"]); a.scatter(S["pa"].real / sc, S["pa"].imag / sc, s=2, color=C["re"])
    a.axhline(0, color=C["ref"], lw=0.5); a.axvline(0, color=C["ref"], lw=0.5); a.set_aspect("equal"); a.set_xticks([]); a.set_yticks([])
    a = ins(9.7, 9.0, 2.0, 1.75, "one symbol, after the carrier correction:\n16 prefix + 64; window 6 early"); a.plot(np.arange(80), S["sym"].real, color=C["re"], lw=0.6); a.axvspan(0, 16, color=C["sc"], alpha=0.25, lw=0); a.axvspan(Fm.CP - Fm.BACK, Fm.CP - Fm.BACK + 64, color=C["tr"], alpha=0.12, lw=0); a.set_xticks([0, 16, 80]); a.set_yticks([])
    a = ins(12.0, 9.0, 1.8, 1.75, "|Y[k]|, one symbol:\n24 data, 4 pilots"); k = np.arange(-32, 32); Yk = np.abs(S["Y"]); ku = np.array([kk in Fm.USED for kk in k]); kp = np.array([kk in Fm.PIL for kk in k])
    a.vlines(k[ku & ~kp], 0, Yk[ku & ~kp], color=C["re"], lw=1); a.vlines(k[kp], 0, Yk[kp], color=C["sc"], lw=1.4); a.vlines(k[~ku], 0, Yk[~ku], color=C["grey"], lw=0.6); a.set_yticks([]); a.set_xticks([-14, 0, 14])
    g = R["gains"]; a = ins(14.1, 9.0, 2.2, 1.75, "pilot gain g per symbol (Re, Im):\nthe small residual carrier turns it"); a.plot(g.real, color=C["re"], lw=0.8); a.plot(g.imag, color=C["im"], lw=0.8); a.set_xticks([0, 44])
    a = ins(11.1, 5.0, 2.0, 1.75, "|H[k]|: flat"); H = R["H"]; a.plot(Fm.USED, np.abs(H), ".-", color=C["re"], ms=2, lw=0.6); a.set_ylim(0, 1.5 * np.abs(H).max()); a.set_xticks([-14, 14])
    a = ins(13.4, 5.0, 2.0, 1.75, "arg H[k]: a straight line\n(the delay)"); a.plot(Fm.USED, np.unwrap(np.angle(H)), ".-", color=C["im"], ms=2, lw=0.6); a.set_xticks([-14, 14])
    Z = S["Z"]; a = ins(1.2, 0.3, 2.2, 1.45, "Z after the pilots: 16 clusters;\ndecisions at 0, ±2/√10"); a.scatter(Z.real.ravel(), Z.imag.ravel(), s=1.2, color=C["re"], alpha=0.6)
    for v in (-2 / np.sqrt(10), 0, 2 / np.sqrt(10)): a.axvline(v, color=C["sc"], lw=0.6, ls="--"); a.axhline(v, color=C["sc"], lw=0.6, ls="--")
    a.set_aspect("equal"); a.set_xticks([]); a.set_yticks([])
    # ---- text
    if ours:
        cv.text(4.1, 1.45, "Our link is uncoded: the slicer's hard decisions are compared with the PRBS-15 the transmitter sent, so the error rate is measured symbol by symbol (no de-interleaver, no de-puncture, no Viterbi, no de-scrambler).\n"
                "The channel estimate is applied before the pilot step (W · Y), not inside the demapper. Blue: blocks written for this receiver; grey: the register block and the software.", fontsize=8, va="center", color="#444")
        cv.text(8.7, 11.6, "Our OFDM receiver (STS frame), block by block, with the signal at every block", fontsize=12, ha="center", va="center")
    else:
        cv.text(4.1, 1.45, "Dashed: the blocks of a coded system (IEEE 802.11a) that our link does not have. Dotted: control and side information (gain, Δf̂, the channel estimate).\n"
                "Our link ends at the demapper: it is uncoded, so the hard decisions are counted directly.", fontsize=8, va="center", color="#444")
        cv.text(8.7, 11.6, "The textbook OFDM receiver (after IEEE 802.11a), redrawn with the signal at every block", fontsize=12, ha="center", va="center")
    cv.text(0.1, 0.1, "Signals: the model's STS frame, carrier offset 9 kHz, delay 0.3 sample, SNR 22 dB per subcarrier; one OFDM symbol is 80 samples (16 prefix + 64). The solid line is the signal path, the red/blue pairs are before/after.", fontsize=7.6, color="#444", va="center")
    cv.save("ofdm_t_rx_ours.png" if ours else "ofdm_t_rx_textbook.png")


if __name__ == "__main__":
    for f in (fig_detector_textbook, fig_detector, fig_fine_cfo_textbook, fig_fine_cfo, lambda: fig_rx(False), lambda: fig_rx(True)):
        try: f(); print("ok", getattr(f, "__name__", "fig_rx"))
        except Exception as e:
            import traceback; print("FAILED", f.__name__, repr(e)); traceback.print_exc()
