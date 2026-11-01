#!/usr/bin/env python3
"""Block diagrams of tutorial 5 (16-QAM), each block with a small plot of the signal at that point: the textbook single-carrier receiver (A.0) and ours (A.5).
The signals come from the integer model of the FPGA receiver (qam16_rx_fixed.py: FLL, front end, ZC synchroniser, PLL): 45 frames of 16-QAM (RRC 0.35, 960 ksym/s, 4 samples per symbol), carrier offset 9.7 kHz,
10.4 ppm, SNR 22 dB per symbol, the FLL and AGC in their acquisition mode for the first 20 frames, a frame of the tracking state for the constellations. The eye diagram is of a separate clean record (no offset).
    python3 make_figures_qam16_diagrams.py        writes qam16_fig_rx_textbook.png and qam16_fig_block_rx.png in ../img"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import qam16_rx_fixed as X
import frame16 as F
import make_signal16 as MS
from study_pll_lowsnr import GI_ACQ
from qpsk_rx_model import rrc_proto
IMG = os.path.join(HERE, "..", "img")
FS, RS, LV = 3.84e6, 960e3, X.LV
C = dict(sc="#e07020", tr="#2e8b57", data="#2b6cb0", grey="#a0aec0", fpga="#bee3f8", old="#e2e8f0", re="#2b6cb0", im="#c53030", ref="#888888")


# ---------------------------------------------------------------- the signals
def make_signals():
    GI_TRK = X.FL.gains(0.0001)[0]
    xi, xq, _ = MS.synth16(45, snr_db=22.0, cfo_hz=9700.0, ppm=10.4, seed=3)
    fl = X.FL.fll_stage(xi, xq, GI_ACQ, 0, F0=0, sched={19200: (GI_TRK, 0)})
    fe, sy, r = X.receive16(xi, xq, X.regs16(), fll=(GI_ACQ, 0, 0), fll_sched={19200: (GI_TRK, 0)}, trace=True)
    tr = np.array(r.trace, dtype=np.int64)                                       # j, pos, kind, zi, zq, e, omega, theta
    starts = np.nonzero(tr[:, 1] == 0)[0]; i0 = starts[-3]; fr = tr[i0:i0 + F.FRAME]            # one frame of the tracking state
    j0 = int(fr[0, 0])
    rho = sy.M / np.maximum(sy.E, 1) / 2 ** 14
    # a clean record for the eye (no carrier offset, no clock error)
    ci, cq, _ = MS.synth16(6, snr_db=22.0, cfo_hz=0.0, ppm=0.0, seed=3, phase0=0.0)
    y = ci + 1j * cq; h = rrc_proto(1); h = h / np.sqrt(np.sum(h ** 2) / 4)
    m = np.convolve(y, h[::-1], mode="same") / np.sqrt(np.mean(np.abs(y) ** 2) * np.sum(h ** 2) / 4)
    best = max(range(4), key=lambda s: np.std(m.real[2000 + s::4][:4000]))
    return dict(xi=xi, xq=xq, fl=fl, fe=fe, sy=sy, r=r, tr=tr, fr=fr, j0=j0, rho=rho, m=m, best=best)


S = make_signals()


class Canvas:
    def __init__(self, W, H, y0=0.0):
        self.fig = plt.figure(figsize=(W, H - y0)); self.W, self.H, self.y0 = W, H, y0
        self.ax = self.fig.add_axes([0, 0, 1, 1]); self.ax.set_xlim(0, W); self.ax.set_ylim(y0, H); self.ax.axis("off")

    def box(self, x, y, w, h, text, fc="white", fs=8.5, ec="k", ls="-", tc="k"):
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1, ls=ls)); self.ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc)

    def arrow(self, x0, y0, x1, y1, color="k", ls="-"):
        self.ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.2, ls=ls))

    def line(self, xs, ys, color="k", lw=1.2, ls="-"): self.ax.plot(xs, ys, color=color, lw=lw, ls=ls)
    def text(self, x, y, s, **kw): self.ax.text(x, y, s, **kw)

    def inset(self, x, y, w, h, title):
        a = self.fig.add_axes([x / self.W, (y - self.y0) / (self.H - self.y0), w / self.W, h / (self.H - self.y0)])
        a.set_title(title, fontsize=6.5, pad=1.5); a.tick_params(labelsize=5, length=2, pad=1); a.set_facecolor("#fafafa")
        for s in a.spines.values(): s.set_linewidth(0.6)
        return a

    def save(self, name): self.fig.savefig(os.path.join(IMG, name), dpi=130); plt.close(self.fig); print("wrote", name)


def bare(a): a.set_xticks([]); a.set_yticks([])


def thresholds(a, unit=1.0, lw=0.4):
    for v in (-2, 0, 2): a.axvline(v * unit, color=C["sc"], lw=lw, ls="--"); a.axhline(v * unit, color=C["sc"], lw=lw, ls="--")


# the plots that both figures use ---------------------------------------------------------------------------
def p_spectrum(a):
    x = (S["xi"] + 1j * S["xq"])[:200000].astype(complex); P = np.mean(np.abs(np.fft.fft(x[:len(x) // 256 * 256].reshape(-1, 256) * np.hanning(256), axis=1)) ** 2, axis=0)
    f = np.fft.fftshift(np.fft.fftfreq(256, 1 / FS)) / 1e6; a.plot(f, 10 * np.log10(np.fft.fftshift(P) / P.max()), color=C["re"], lw=0.8); a.set_ylim(-45, 3); a.set_xlabel("MHz", fontsize=5, labelpad=0)


def p_samples(a): a.plot(S["xi"][3000:3160], color=C["re"], lw=0.6); a.plot(S["xq"][3000:3160], color=C["im"], lw=0.6); bare(a)


def p_fll(a):
    fr = S["fl"]["fr"].astype(float) / 2 ** 32 * FS / 1e3; t = np.arange(len(fr)) * 4 / FS * 1e3; a.plot(t[::40], fr[::40], color=C["re"], lw=0.8)
    a.axhline(-9.7, color=C["sc"], lw=0.7, ls="--"); a.set_xlabel("ms", fontsize=5, labelpad=0); a.set_ylabel("kHz", fontsize=5, labelpad=0)


def p_taps(a):
    import qpsk_rx_fixed as Q
    cm, cd = Q.coefs(); a.plot(cm[0], color=C["re"], lw=0.8, label="matched"); a.plot(cd[0], color=C["im"], lw=0.8, label="derivative"); a.legend(fontsize=5, loc="upper right", frameon=False); bare(a)


def p_agc(a): a.plot(S["fe"]["g"][:6000], color=C["re"], lw=0.8); a.set_xlabel("symbol", fontsize=5, labelpad=0)


def p_timing(a):
    r = S["fe"]["rate"].astype(float) / 2 ** 22 * 1e6; a.plot(np.arange(len(r))[::10], r[::10], color=C["re"], lw=0.8); a.axhline(-10.4, color=C["sc"], lw=0.7, ls="--"); a.set_ylim(-500, 500)
    a.set_xlabel("symbol", fontsize=5, labelpad=0); a.set_ylabel("ppm", fontsize=5, labelpad=0)


def p_symbols(a):
    j0 = S["j0"]; mi, mq = S["fe"]["mi2"][j0:j0 + F.FRAME] / LV, S["fe"]["mq2"][j0:j0 + F.FRAME] / LV
    a.scatter(mi, mq, s=1.2, color=C["im"], alpha=0.6); a.set_xlim(-4.5, 4.5); a.set_ylim(-4.5, 4.5); a.set_aspect("equal"); bare(a)


def p_omega(a):
    tr = S["tr"]; a.plot(tr[::20, 6].astype(float) / 2 ** 32 * RS / 1e3, color=C["re"], lw=0.8); a.set_xlabel("symbol (x 20)", fontsize=5, labelpad=0); a.set_ylabel("kHz", fontsize=5, labelpad=0)


def p_derot(a):
    fr = S["fr"]; d = fr[fr[:, 2] == 1]; a.scatter(d[:, 3] / LV, d[:, 4] / LV, s=1.2, color=C["re"], alpha=0.6); thresholds(a); a.set_xlim(-4.5, 4.5); a.set_ylim(-4.5, 4.5); a.set_aspect("equal"); bare(a)


def p_pos(a):
    tr = S["tr"]; i0 = int(np.nonzero(tr[:, 1] == 0)[0][-3]); seg = tr[i0 - 400:i0 + 2 * F.FRAME]; a.plot(seg[:, 0] - seg[0, 0], seg[:, 1], color=C["re"], lw=0.8); a.set_xlabel("symbol", fontsize=5, labelpad=0); a.set_yticks([0, 71, 966])


def p_rho(a):
    j0 = S["j0"]; n = np.arange(j0 - 300, j0 + 2 * F.FRAME); a.plot(n - n[0], S["rho"][n], color=C["re"], lw=0.8); a.axhline(0.6, color=C["sc"], lw=0.7, ls="--"); a.axhline(0.45, color=C["sc"], lw=0.7, ls=":")
    a.set_ylim(0, 1.15); a.set_xlabel("symbol", fontsize=5, labelpad=0)


def p_pd(a):
    fr = S["fr"]
    for kind, col, lb in ((1, C["data"], "data"), (2, C["im"], "pilot"), (3, C["tr"], "word")): d = fr[fr[:, 2] == kind]; a.plot(d[:, 1], d[:, 5], ".", ms=1.2, color=col, label=lb)
    a.legend(fontsize=5, loc="upper right", frameon=False, markerscale=3); a.set_xlabel("position in the frame", fontsize=5, labelpad=0)


def p_err(a):
    fr = S["fr"]; d = fr[fr[:, 2] == 1]; si = np.array([X._level(int(v)) for v in d[:, 3]]); sq = np.array([X._level(int(v)) for v in d[:, 4]])
    a.scatter((d[:, 3] - si * LV) / LV, (d[:, 4] - sq * LV) / LV, s=1.2, color=C["im"], alpha=0.6); a.axhline(0, color=C["ref"], lw=0.5); a.axvline(0, color=C["ref"], lw=0.5); a.set_xlim(-1.3, 1.3); a.set_ylim(-1.3, 1.3); a.set_aspect("equal"); bare(a)


def p_evm(a): e = S["r"].evm; a.plot(e, ".-", ms=2, lw=0.6, color=C["re"]); a.set_xlabel("frame", fontsize=5, labelpad=0); a.set_ylabel("EVM dB", fontsize=5, labelpad=0)


def p_eye(a):
    m, s = S["m"], S["best"]; k0 = 2000 + s
    for i in range(300): seg = m.real[k0 + 4 * i - 4:k0 + 4 * i + 5]; a.plot(np.arange(-4, 5), seg, color=C["re"], lw=0.3, alpha=0.4)
    a.set_xticks([-4, 0, 4]); a.set_yticks([])


# ---------------------------------------------------------------- 1. the textbook receiver
def fig_textbook():
    cv = Canvas(18.0, 11.2, y0=-0.2); DG = "#a0aec0"; dx = 0.5
    cv.text(9.0, 10.8, "The textbook single-carrier QAM receiver, redrawn with the signal at every block", fontsize=12, ha="center", va="center")
    cols = [(0.3, 1.5, "Radio Rx", "w"), (2.1, 1.5, "ADC\nI/Q", "w"), (3.9, 1.5, "AGC", "w"), (5.7, 1.9, "Matched filter\n(RRC)", "w"), (7.9, 1.9, "Timing\nrecovery\n(a loop)", "w"), (10.2, 1.9, "Carrier\nrecovery\n(FLL + PLL)", "w"), (12.5, 1.6, "Equaliser", "d"), (14.4, 1.4, "Slicer", "w"), (16.1, 1.3, "Decoder", "d")]
    cols = [(x + dx, w, t, k) for x, w, t, k in cols]
    yb, hb = 7.0, 0.9; yc = yb + hb / 2
    for x, w, t, kind in cols:
        if kind == "d": cv.box(x, yb, w, hb, t, "white", 9.5, ec=DG, ls="--", tc="#888")
        else: cv.box(x, yb, w, hb, t, "white", 9.5)
    for i in range(len(cols) - 1):
        dash = cols[i + 1][3] == "d" or cols[i][3] == "d"; cv.arrow(cols[i][0] + cols[i][1], yc, cols[i + 1][0], yc, color=DG if dash else "k", ls="--" if dash else "-")
    cv.text(0.25, 8.35, "▽", fontsize=16, ha="center", va="center"); cv.line([0.25, 0.25, 0.8], [8.05, yc, yc])
    cv.arrow(cols[-1][0] + cols[-1][1], yc, cols[-1][0] + cols[-1][1] + 0.35, yc); cv.text(cols[-1][0] + cols[-1][1] + 0.4, yc, "bits", fontsize=9, va="center")
    # the gain loop (dotted) and the frame synchroniser
    ax_, rx_ = cols[2][0] + 0.75, cols[0][0] + 0.75
    cv.line([ax_, ax_, rx_], [yb, 6.2, 6.2], ls=":"); cv.arrow(rx_, 6.2, rx_, yb, ls=":"); cv.text((ax_ + rx_) / 2, 6.05, "gain (AGC loop)", fontsize=7.5, ha="center", va="top")
    fx, fw, fy, fh = 9.1, 4.1, 4.0, 0.9
    cv.box(fx, fy, fw, fh, "Frame synchronisation\n(correlation with a known word)", "white", 9)
    tap = cols[4][0] + cols[4][1] + 0.2; cv.line([tap, tap], [yc, fy + fh + 0.45]); cv.arrow(tap, fy + fh + 0.45, tap, fy + fh)
    ret = cols[5][0] + 1.3; cv.line([ret, ret], [fy + fh, yb - 0.45], ls=":"); cv.arrow(ret, yb - 0.45, ret, yb, ls=":"); cv.text(ret + 0.1, 5.95, "start of the frame, carrier word → Δf, θ", fontsize=7.5, va="center")
    # the signals above the blocks
    def ins(i, t, w=None, y=8.15, h=1.9): return cv.inset(cols[i][0], y, w or cols[i][1], h, t)
    p_spectrum(ins(0, "spectrum: RRC 0.35,\n960 ksym/s")); p_samples(ins(1, "x[n]: I (blue), Q (red)")); p_agc(ins(2, "gain g per symbol\n(acquisition)")); p_eye(ins(3, "eye of the matched\nfilter (carrier removed)")); p_timing(ins(4, "timing rate in ppm: settles\nat the clock error"))
    a = ins(5, "before (red) / after (blue)\nthe carrier loop"); j0 = S["j0"]; a.scatter(S["fe"]["mi2"][j0:j0 + F.FRAME] / LV, S["fe"]["mq2"][j0:j0 + F.FRAME] / LV, s=1.2, color=C["im"], alpha=0.5); fr = S["fr"]; d = fr[fr[:, 2] == 1]; a.scatter(d[:, 3] / LV, d[:, 4] / LV, s=1.2, color=C["re"], alpha=0.6)
    a.set_xlim(-4.5, 4.5); a.set_ylim(-4.5, 4.5); a.set_aspect("equal"); bare(a)
    cv.text(cols[6][0] + 0.8, 8.9, "flat channel:\nnot needed", fontsize=8, ha="center", va="center", color="#888"); cv.text(cols[8][0] + 0.65, 8.9, "uncoded:\nnot in our link", fontsize=8, ha="center", va="center", color="#888")
    p_err(ins(7, "decision error\nz − decision"))
    p_rho(cv.inset(fx, 1.1, fw, 2.3, "correlation with the Zadoff-Chu word: one peak per frame\n(threshold 0.6 dashed)"))
    cv.text(0.3, 4.6, "Dotted: control and side information. Dashed: blocks that a link with\na long channel or with coding has and that this link does not need.\n"
            "The signals are from the integer model of the FPGA receiver: carrier\noffset 9.7 kHz, clock offset 10.4 ppm, SNR 22 dB per symbol; the eye\nis of a clean record with no carrier offset.\n\n"
            "Timing recovery and carrier recovery are loops: the timing loop moves\nthe sampling instant (its rate settles at the clock error), the carrier\nloop turns the symbols until the clusters stand still.", fontsize=8, va="top", color="#444")
    cv.save("qam16_fig_rx_textbook.png")


# ---------------------------------------------------------------- 2. our receiver
def fig_ours():
    cv = Canvas(14.6, 12.8, y0=-2.0); NEW, OLD = C["fpga"], C["old"]; OR = C["sc"]
    cv.text(7.3, 12.4, "The 16-QAM receiver (rtl/qam16_rx.v, ID 0xDD520006) with the signal at every block: the engine runs once per symbol, about 70 of the 104 clocks at 100 MHz", fontsize=10.5, ha="center", va="center")
    cv.ax.add_patch(plt.Rectangle((0.2, 11.95), 0.3, 0.2, fc=OLD, ec="k")); cv.text(0.6, 12.05, "as in the QPSK receiver", va="center", fontsize=8.5); cv.ax.add_patch(plt.Rectangle((3.0, 11.95), 0.3, 0.2, fc=NEW, ec="k")); cv.text(3.4, 12.05, "new or changed for 16-QAM", va="center", fontsize=8.5)
    ya, hh = 8.6, 1.2; yca = ya + hh / 2
    row = [(0.2, 1.8, "ADC\n3.84 MS/s\nsample RAM", OLD), (2.4, 1.9, "band-edge FLL\n(derotation)\nqpsk_fll.v", OLD), (4.7, 2.2, "polyphase matched +\nderivative filter\n(44 taps, 4 sps)", OLD), (7.2, 2.0, "power AGC\n(rounded)", NEW), (9.6, 2.1, "timing error\nand loop\n(acq. gains)", OLD), (12.2, 2.2, "symbols\nmi2, mq2\n(1 per symbol)", OLD)]
    for x, w, t, fc in row: cv.box(x, ya, w, hh, t, fc, 8.5)
    for i in range(5): cv.arrow(row[i][0] + row[i][1], yca, row[i + 1][0], yca)
    ins = [(0.2, 1.8, "spectrum of the ADC signal", p_spectrum), (2.4, 1.9, "FLL frequency (it pulls the\noffset to within a few kHz)", p_fll), (4.7, 2.2, "the filter taps: matched\nand derivative (one phase of 16)", p_taps),
           (7.2, 2.0, "AGC gain g: acquisition,\nthen tracking", p_agc), (9.6, 2.1, "timing rate: settles at the\nclock error (-10.4 ppm, dashed)", p_timing), (12.2, 2.2, "mi2, mq2 of one frame: turning\n(the carrier is not yet removed)", p_symbols)]
    for x, w, t, f in ins: f(cv.inset(x, 10.1, w, 1.6, t))
    yb = 5.6; hb = 1.2; ycb = yb + hb / 2
    cv.box(0.2, yb, 3.2, hb, "loop filter\nCA, CB → omega, theta", OLD, 8.5); cv.box(4.2, yb, 2.8, hb, "16-symbol delay (D = 8 to 10)\nderotation by the NCO\n(1024-entry sin / cos table)", OLD, 8)
    cv.box(7.6, yb, 3.0, hb, "events: position counter (CP 0-7,\nword 8-70, data 71-966),\ntheta0 and w at every lock", NEW, 7.6); cv.box(11.2, yb, 3.2, hb, "qam_zc_sync.v\ncorrelator, rho = |C| / sum |x|,\nSEARCH - VERIFY - LOCKED,\ncarrier from the two half words", NEW, 7.6)
    cv.line([13.3, 13.3], [ya, yb + hb]); cv.arrow(13.3, yb + hb + 0.4, 13.3, yb + hb); cv.line([12.7, 12.7, 5.2], [ya, 7.75, 7.75]); cv.arrow(5.2, 7.75, 5.2, yb + hb)
    cv.text(8.6, 7.9, "16 symbols later: the answer of the synchroniser is ready before symbol 1", fontsize=7.5, color="#444", va="bottom")
    cv.arrow(11.2, ycb, 10.6, ycb, OR); cv.arrow(7.6, ycb, 7.0, ycb, OR); cv.arrow(3.4, ycb, 4.2, ycb, OR); cv.text(3.8, ycb + 0.15, "theta", fontsize=7.5, color=OR, ha="center", va="bottom")
    p_omega(cv.inset(0.5, 3.8, 2.4, 1.5, "PLL frequency omega: settles\nat the residual offset"))
    p_derot(cv.inset(4.4, 3.8, 1.5, 1.5, "z after the NCO:\n16 clusters"))
    p_pos(cv.inset(7.9, 3.8, 2.6, 1.5, "position counter, set by the\nframe events (0 ... 966)"))
    p_rho(cv.inset(11.3, 3.8, 3.0, 1.5, "rho: one peak per frame\n(0.6 and 0.45 dashed)"))
    yc, hc = 1.4, 1.2; ycc = yc + hc / 2
    cv.box(0.2, yc, 3.2, hc, "phase detector (shift-add)\ndata: Im(z conj s); pilot x3;\nknown CP / word symbols (aided)", NEW, 8); cv.box(4.2, yc, 2.8, hc, "16-QAM slicer\nlevels ±1, ±3 (x 4096),\nthresholds 0, ±8192", NEW, 8)
    cv.box(7.6, yc, 3.0, hc, "Gray decision; PRBS-15 checker\n(symbol and bit errors, frames)\nEVM sums, capture RAM (1024)", NEW, 8); cv.box(11.2, yc, 3.2, hc, "AXI-Lite registers 0x00-0xD8\ncapture RAM at 0x1000", OLD, 8)
    cv.arrow(6.7, yb, 6.7, yc + hc); cv.arrow(4.2, ycc, 3.4, ycc); cv.arrow(3.2, yc + hc, 3.2, yb, OR); cv.arrow(7.0, ycc, 7.6, ycc); cv.arrow(10.6, ycc, 11.2, ycc)
    p_pd(cv.inset(0.4, -1.2, 3.0, 1.9, "phase error e over the frame")); p_err(cv.inset(4.4, -1.2, 1.9, 1.9, "decision error z − s\n(what the EVM sums add)")); p_evm(cv.inset(7.9, -1.2, 2.6, 1.9, "EVM of every frame:\nacquisition, then lock"))
    cv.text(11.2, -0.3, "Signals: integer model of the receiver, 45 frames,\ncarrier offset 9.7 kHz, clock 10.4 ppm, SNR 22 dB per symbol;\nthe FLL and AGC gains change at frame 20 (as in the driver).", fontsize=7.5, color="#444", va="center")
    cv.save("qam16_fig_block_rx.png")


# ---------------------------------------------------------------- 3. and 4. the transmitter: the textbook chain and the FPGA module qam16_tx_fr.v, with the signal at every block
def tx_signals():
    import qam16_tx_model as TM
    from qpsk_model import coef_int
    sym = np.array(TM.frame_symbols(2), dtype=np.int64); di, dq = TM.model(7736, amp=0x4000)
    bits = F.prbs15_bits(4 * 63)[:96]
    return dict(TM=TM, sym=sym, di=di, dq=dq, h=np.array(coef_int(), dtype=float), bits=np.array(bits, dtype=int))


def tx_plots(T):
    sym = T["sym"]; PA = T["TM"].PA; out = {}
    def bits(a): a.step(np.arange(96), T["bits"], where="post", color=C["re"], lw=0.7); a.set_ylim(-0.2, 1.3); a.set_yticks([0, 1]); a.set_xticks([0, 48, 96]); a.set_xlabel("bit (24 symbols)", fontsize=5, labelpad=0)
    def mapper(a):
        idx = [q for q in range(71, F.FRAME) if (q - 71) % F.BLK != F.BLK - 1]; v = sym[idx] / 64.0
        a.scatter(v[:, 0], v[:, 1], s=2, color=C["re"]); a.set_xlim(-4.2, 4.2); a.set_ylim(-4.2, 4.2); a.set_aspect("equal"); thresholds(a); bare(a)
    def assemble(a):
        n = 140; m = np.hypot(sym[:n, 0], sym[:n, 1]) / PA; a.axvspan(0, 8, color=C["sc"], alpha=0.3, lw=0); a.axvspan(8, 71, color=C["tr"], alpha=0.2, lw=0)
        a.plot(m, color=C["re"], lw=0.7); pil = [71 + b * F.BLK + F.BLK - 1 for b in range(F.N_BLK) if 71 + b * F.BLK + F.BLK - 1 < n]; a.plot(pil, m[pil], "o", ms=2.5, color=C["im"]); a.set_xlim(0, n); a.set_xticks([0, 8, 71, 134]); a.set_yticks([])
    def upsample(a):
        v = sym[71:71 + 12, 0] / 64.0; x = np.zeros(48); x[::4] = v; a.vlines(np.arange(48), 0, x, color=C["re"], lw=1.0); a.axhline(0, color=C["ref"], lw=0.5); a.set_xticks([0, 24, 48]); a.set_yticks([])
    def taps(a): a.plot(T["h"], color=C["re"], lw=0.8); a.set_xticks([0, 22, 44]); a.set_yticks([])
    def shaped(a):
        n0 = 4 * 71 + 22; a.plot(T["di"][n0:n0 + 120], color=C["re"], lw=0.7); a.plot(T["dq"][n0:n0 + 120], color=C["im"], lw=0.7); a.set_xticks([0, 40, 80, 120]); a.set_yticks([])
    def spectrum(a):
        z = (T["di"] + 1j * T["dq"])[400:400 + 7000].astype(complex); P = np.mean(np.abs(np.fft.fft(z[:len(z) // 256 * 256].reshape(-1, 256) * np.hanning(256), axis=1)) ** 2, axis=0)
        f = np.fft.fftshift(np.fft.fftfreq(256, 1 / FS)) / 1e6; a.plot(f, 10 * np.log10(np.fft.fftshift(P) / P.max()), color=C["re"], lw=0.8); a.set_ylim(-45, 3); a.set_xlabel("MHz", fontsize=5, labelpad=0)
    return dict(bits=bits, mapper=mapper, assemble=assemble, upsample=upsample, taps=taps, shaped=shaped, spectrum=spectrum)


def fig_tx_textbook():
    T = tx_signals(); P = tx_plots(T); cv = Canvas(18.4, 9.0, y0=2.7); DG = "#a0aec0"
    cv.text(9.2, 8.6, "The textbook single-carrier QAM transmitter, redrawn with the signal at every block", fontsize=12, ha="center", va="center")
    cols = [(0.3, 1.5, "Bits", "w"), (2.1, 1.9, "Encoder,\ninterleaver", "d"), (4.3, 1.6, "Mapper\n(QAM)", "w"), (6.2, 2.0, "Add the known\nword and pilots\n(frame)", "w"), (8.5, 1.5, "Upsample\nby 4", "w"), (10.3, 1.9, "Pulse-shaping\nfilter (RRC)", "w"), (12.5, 1.6, "DAC", "w"), (14.4, 1.7, "Radio Tx\n▷", "w")]
    yb, hb = 4.6, 0.95; yc = yb + hb / 2
    for x, w, t, kind in cols:
        if kind == "d": cv.box(x, yb, w, hb, t, "white", 9, ec=DG, ls="--", tc="#888")
        else: cv.box(x, yb, w, hb, t, "white", 9.5)
    for i in range(len(cols) - 1):
        dash = cols[i + 1][3] == "d" or cols[i][3] == "d"; cv.arrow(cols[i][0] + cols[i][1], yc, cols[i + 1][0], yc, color=DG if dash else "k", ls="--" if dash else "-")
    def ins(i, t, h=1.9, w=None): return cv.inset(cols[i][0], 5.85, w or cols[i][1], h, t)
    P["bits"](ins(0, "bits (PRBS-15)")); P["mapper"](ins(2, "16-QAM symbols of\none frame")); P["assemble"](ins(3, "|symbol|, the first 140 of 967:\nprefix, word (constant), data, pilot")); P["upsample"](ins(4, "I of 12 symbols,\nthree zeros between"))
    P["shaped"](ins(5, "the shaped signal (I, Q)")); P["spectrum"](ins(6, "spectrum"))
    cv.text(3.05, 6.8, "(coded system only)", fontsize=8, ha="center", color="#888")
    cv.text(0.3, 3.9, "Dashed: the blocks of a coded system that our link does not have. The known word and the pilots are added to the data symbols so that the receiver can\nfind the frame and the carrier; upsampling puts three zeros between the symbols and the root-raised-cosine filter turns them into a band-limited signal\n(its taps are in the figure of our transmitter, A.5b). Signals: the integer model of the FPGA transmitter (qam16_tx_model.py); the unit of the symbols is the level 64.", fontsize=8, va="top", color="#444")
    cv.save("qam16_fig_tx_textbook.png")


def fig_tx_ours():
    T = tx_signals(); P = tx_plots(T); cv = Canvas(18.4, 9.2, y0=0.9); BL, OLD = C["fpga"], C["old"]
    cv.text(9.2, 8.8, "Our 16-QAM transmitter in the FPGA (rtl/qam16_tx_fr.v), block by block, with the signal at every block", fontsize=12, ha="center", va="center")
    cols = [(0.3, 1.9, "PRBS-15 (x^15 + x^14 + 1)\nrestarted every frame\n4 bits per symbol", BL), (2.5, 1.9, "Gray mapper\n00 → -192, 01 → -64,\n10 → +192, 11 → +64\n(units of 1/64)", BL), (4.7, 2.6, "symbol source: position counter\nCP 0-7 and word 8-70: ROM\nZC x 202; pilots ±202;\ndata: mapper", BL),
            (7.6, 2.0, "history of the last\n12 symbols (I and Q)", BL), (9.9, 2.8, "polyphase RRC FIR:\n12 taps of one phase x\n12 symbols, 24 multipliers,\nsum (+ 32) >> 6", BL), (13.0, 2.4, "DAC value\nclip((y amp) >> 15)\namp Q15", BL), (15.7, 1.6, "DAC\n3.84 MS/s", OLD)]
    yb, hb = 5.0, 1.3; yc = yb + hb / 2
    for x, w, t, fc in cols: cv.box(x, yb, w, hb, t, fc, 7.8)
    for i in range(len(cols) - 1): cv.arrow(cols[i][0] + cols[i][1], yc, cols[i + 1][0], yc)
    def ins(i, t, h=1.9): return cv.inset(cols[i][0], 6.6, cols[i][1], h, t)
    P["bits"](ins(0, "bits (24 symbols)")); P["mapper"](ins(1, "symbol values / 64")); P["assemble"](ins(2, "|symbol| (202 = 1), the first 140 of 967:\nprefix, word (constant), data, pilot (red)"))
    P["upsample"](ins(3, "I of 12 symbols, four samples\neach (one is nonzero)")); P["taps"](ins(4, "the 45 taps h[4j + phase]\n(integers, RRC 0.35)")); P["shaped"](ins(5, "dac_i, dac_q (amp = 0.5)"))
    cv.ax.add_patch(plt.Rectangle((0.2, 3.9), 17.2, 0.5, fc="#ebf8ff", ec=C["grey"], lw=0.8)); cv.text(8.8, 4.15, "everything on l_clk, one step per `ce` (= dac_valid of the AD9361 interface: one DAC request, 3.84 MS/s, at most every second clock): no handshake, no buffer", ha="center", va="center", fontsize=8)
    cv.text(0.3, 3.5, "The frame: CP 8 | ZC word 63 | 14 x (63 data + 1 pilot) = 967 symbols = 1.007 ms, repeated back to back; the payload is the PRBS-15 the receiver's checker expects.\nThe 24 products are registered and summed in the next clock (the first build summed 12 products in one clock: 10.09 ns for a 10 ns clock).\nSignals: qam16_tx_model.py, the bit-exact model (xsim equals it sample for sample, 14,000 samples).", fontsize=8, va="top", color="#444")
    P["spectrum"](cv.inset(13.0, 1.1, 3.4, 1.7, "spectrum of the DAC signal"))
    cv.save("qam16_fig_tx.png")


if __name__ == "__main__":
    for f in (fig_textbook, fig_ours, fig_tx_textbook, fig_tx_ours):
        try: f()
        except Exception:
            import traceback; print("FAILED", f.__name__); traceback.print_exc()
