#!/usr/bin/env python3
"""Block diagrams of chain 3 (polyphase -> 4th power -> Costas, overlay p501_qpsk_trx_4p) into tutorial/img/:
    qpsk_chains_compare.png   the three chains side by side (what is in the signal path, what is a side path)
    qpsk_chain3_block.png     the Verilog implementation: the engine of qpsk_rx_4p.v with the estimator qpsk_fe.v + qpsk_fe_auto.v and the one mux that loads the Costas frequency
    qpsk_chain3_modes.png     what FE_AUTO does in time: Costas only / once / continuous

    python3 make_diagrams_4p.py"""
import os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "doc"))
from make_diagrams import canvas, box, path, COL, EDGE, RED, OUT

EST = "#d9f0d3"        # the estimator
ENG = "#dbe9f7"        # the engine of the receiver (chapter 4d)
FLLC = "#fde9c9"       # the FLL
CTL = "#f6d9e4"        # control, registers
GREY = "#eeeeee"


def pad(ax, x, y, w, h, text, fc, fs=7.6, bold=False, ec=EDGE, lw=1.1, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=fc, ec=ec, lw=lw, ls=ls, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal", linespacing=1.3, zorder=3)


# ---------------------------------------------------------------------------------------------- 1. the three chains
def compare():
    fig, ax = canvas(165, 96)
    ax.text(82.5, 93, "The three carrier-frequency chains, each its own overlay", fontsize=11, fontweight="bold", ha="center")
    rows = [
        (68, "1  polyphase -> Costas", "overlay p501_qpsk_trx  (chapter 4d)", [("ADC\n3.84 MSPS", GREY), ("polyphase matched filter\n+ timing loop + AGC", ENG), ("Costas loop\n(phase + frequency)", ENG), ("decision, bits,\nPRBS-15 checker", ENG)], False),
        (44, "2  FLL -> polyphase -> Costas", "overlay p501_qpsk_trx_fll", [("ADC\n3.84 MSPS", GREY), ("FLL band-edge\nderotator, closed loop", FLLC), ("polyphase matched filter\n+ timing loop + AGC", ENG), ("Costas loop", ENG), ("decision, bits,\nPRBS-15 checker", ENG)], False),
        (20, "3  polyphase -> 4th power -> Costas", "overlay p501_qpsk_trx_4p", [("ADC\n3.84 MSPS", GREY), ("polyphase matched filter\n+ timing loop + AGC", ENG), ("Costas loop", ENG), ("decision, bits,\nPRBS-15 checker", ENG)], True),
    ]
    for y, title, sub, blocks, est in rows:
        ax.text(2, y + 15.5, title, fontsize=9, fontweight="bold", color="#1d4f91"); ax.text(70, y + 15.5, sub, fontsize=7.8, color="#555", style="italic")
        n = len(blocks); w = 27 if n == 5 else 33; gap = (161 - n * w) / (n - 1)
        xs = [2 + k * (w + gap) for k in range(n)]
        for x, (t, c) in zip(xs, blocks): pad(ax, x, y, w, 12, t, c, fs=7.4)
        for k in range(n - 1): path(ax, [(xs[k] + w, y + 6), (xs[k + 1], y + 6)])
        if est:                                                          # the estimator is a side path: tap after the polyphase block, load into the Costas loop
            ex, ew = xs[1] + 4, 46; cx = xs[2] + w / 2
            pad(ax, ex, y - 12, ew, 9, "4th-power estimator + atan2 (hardware)\nwindow N symbols, quality gate", EST, fs=7.0)
            path(ax, [(xs[1] + w / 2, y), (xs[1] + w / 2, y - 3)])
            ax.text(xs[1] + w / 2 + 1.5, y - 1.6, "m", fontsize=7, color="#222")
            path(ax, [(ex + ew, y - 7.5), (cx, y - 7.5), (cx, y)], color=RED)
            ax.text(cx + 2, y - 5.5, "loads the Costas frequency (OMEGA)\nwhen a window passes the gate", fontsize=7, color=RED, va="center")
    ax.text(82.5, 1.5, "blue = the receiver of chapter 4d,  orange = the FLL (a derotator in front of it),  green = the estimator: a side path that reads the symbols and only writes the Costas frequency", fontsize=7.4, ha="center", color="#333")
    fig.savefig(os.path.join(OUT, "qpsk_chains_compare.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


# ---------------------------------------------------------------------------------------------- 2. the Verilog block diagram
def block():
    fig, ax = canvas(170, 114)
    ax.text(85, 111, "Chain 3 in the FPGA: rtl/qpsk_rx_4p.v with qpsk_fe.v and qpsk_fe_auto.v", fontsize=11, fontweight="bold", ha="center")
    ax.text(2, 105.5, "ENGINE of the receiver (aclk = 100 MHz, once per symbol, about 65 of the 104 clock cycles)", fontsize=8, fontweight="bold", color="#2b4a6b")
    pad(ax, 12, 86, 24, 12, "ADC samples\nsample RAM 256 x 32\n(l_clk -> aclk,\nGray counter)", GREY, fs=7)
    pad(ax, 42, 86, 28, 12, "polyphase MAC\n16 arms x 44 taps\nmatched + derivative,\nI and Q  (ST_MAC, S0)", ENG, fs=7)
    pad(ax, 76, 86, 22, 12, "AGC\nm = m' x g >> 10\n(S1, S2, S3)", ENG, fs=7)
    pad(ax, 104, 86, 26, 12, "timing loop\ne_t, rate, p\n(S2, S3, S4)", ENG, fs=7)
    for a, b in ((36, 42), (70, 76), (98, 104)): path(ax, [(a, 92), (b, 92)])
    path(ax, [(117, 98), (117, 102), (56, 102), (56, 98)], color="#777", ls="--")
    ax.text(86, 102.8, "p: next sample instant and arm", fontsize=6.8, color="#555", ha="center")
    # m bus
    ax.plot([87, 87], [86, 79], color=EDGE, lw=1.2, zorder=1); ax.plot([4, 87], [79, 79], color=EDGE, lw=1.2, zorder=1)
    ax.text(89, 82.5, "m = (mi2, mq2): after the AGC, before the derotation", fontsize=7.2, color="#222")
    path(ax, [(24, 79), (24, 70)])                                                    # to the derotation
    ax.plot(24, 79, "o", color=EDGE, ms=3, zorder=4); ax.plot(4, 79, "o", color="#2a9d4f", ms=3, zorder=4)
    # Costas row
    ax.text(2, 74.5, "COSTAS LOOP", fontsize=8, fontweight="bold", color="#2b4a6b")
    pad(ax, 12, 55, 24, 15, "derotation\nz = m x exp(-j theta)\n1024-entry sin/cos table\n(S5)", ENG, fs=6.9)
    pad(ax, 42, 55, 28, 15, "error + decision\ne_c = sgn(zi) zq - sgn(zq) zi\ndifferential decoder, PRBS-15\nchecker, capture RAM (S6)", ENG, fs=6.6)
    pad(ax, 76, 55, 30, 15, "omega register (32 bit)\nS7:  omega <= load ? ld_w\n          : omega + (CB x e_c >> 8)", CTL, fs=6.8, ec=RED, lw=1.6)
    pad(ax, 112, 55, 28, 15, "NCO phase (S8)\ntheta += omega\n          + (CA x e_c >> 8)", ENG, fs=6.9)
    path(ax, [(36, 62.5), (42, 62.5)]); ax.text(39, 63.2, "z", fontsize=7, ha="center")
    path(ax, [(70, 62.5), (76, 62.5)]); ax.text(73, 63.2, "e_c", fontsize=6.6, ha="center")
    path(ax, [(106, 62.5), (112, 62.5)]); ax.text(109, 63.2, "omega", fontsize=6.2, ha="center")
    path(ax, [(126, 70), (126, 75.5), (30, 75.5), (30, 70)], color=EDGE); ax.text(78, 76.2, "theta", fontsize=7, ha="center")
    path(ax, [(56, 55), (56, 51), (130, 51), (130, 55)], color=EDGE); ax.text(100, 51.8, "e_c  (CA path)", fontsize=7, ha="center")
    ax.text(91, 71.8, "the one mux", fontsize=7.6, color=RED, fontweight="bold", ha="center")
    # estimator
    ax.add_patch(Rectangle((1, 1), 168, 47, fc="#f3faf1", ec="#2a9d4f", lw=1.3, ls="--", zorder=0))
    ax.text(3, 44.6, "ESTIMATOR: qpsk_fe.v (accumulators) + qpsk_fe_auto.v (controller);  `go` = state S2 of every symbol", fontsize=8, fontweight="bold", color="#1d6b34")
    y = 29
    xs = [(8, 22), (34, 22), (60, 20), (84, 28), (116, 22), (142, 26)]
    txt = ["d = m x conj(m_prev)\n4 multipliers\nround >> 15, clip +-16383", "CORDIC vectoring\n13 iterations\nangle (16 bit), |d|", "psi = 4 x angle\nexp(j psi) from the\nsin/cos table (Q15)",
           "window accumulators\nACC_RE += c   ACC_IM += s\nACC_ABS += |d|  (N symbols)", "atan2 CORDIC\n18 iterations\nangle (turns x 2^20)", "gate and load\n|ACC| >= cnt x QMIN ?\nw = angle << 10"]
    for (x, w), t in zip(xs, txt): pad(ax, x, y, w, 12, t, EST, fs=6.5)
    for k in range(5): path(ax, [(xs[k][0] + xs[k][1], y + 6), (xs[k + 1][0], y + 6)])
    path(ax, [(4, 79), (4, 46.5), (19, 46.5), (19, y + 12)], color="#2a9d4f")
    ax.text(5.2, 60, "m", fontsize=7.4, color="#1d6b34")
    # control and registers
    pad(ax, 3, 4, 78, 17, "control (qpsk_fe_auto.v):  FE_AUTO bit 0 enable, bit 1 continuous\narms the window itself (the first symbol after the enable, then contiguous windows)\nonce: stops after the first window that passes the gate;  continuous: re-arms after every window\nregisters written by Python: FE_N, FE_QMIN, FE_AUTO, FE_CTRL (one manual window)", CTL, fs=6.6)
    pad(ax, 87, 4, 80, 17, "read back: ACC_RE, ACC_IM, ACC_ABS, FE_CNT, FE_FIRST (the manual windows)\nFE_NLOAD (loads), FE_NWIN (windows), FE_WEST (last value loaded), FE_WLAST (last window)\nPython: f = atan2(ACC_IM, ACC_RE) / (8 pi) x 960 kHz  for a manual window", GREY, fs=6.6)
    path(ax, [(81, 12.5), (87, 12.5)], arrow=False, color="#999")
    path(ax, [(45, 21), (45, y)], arrow=False, color="#999", ls="--"); path(ax, [(98, 21), (98, y)], arrow=False, color="#999", ls="--")
    # the load request back to the mux
    path(ax, [(155, y + 12), (155, 46.5), (92, 46.5), (92, 55)], color=RED)
    ax.text(124, 49.4, "ld_w, ld_pend: one load request per window that passes the gate;  ld_ack from S7 clears it", fontsize=6.8, color=RED, ha="center")
    fig.savefig(os.path.join(OUT, "qpsk_chain3_block.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


# ---------------------------------------------------------------------------------------------- 3. the modes in time
def modes():
    fig, axs = plt.subplots(3, 1, figsize=(15.5, 7.6), sharex=True)
    N = 1024; nwin = 6
    titles = ["FE_AUTO = 0   (Costas only): no window is armed, no load is ever requested; omega = the Costas integrator", "FE_AUTO = 1   (once): windows follow each other until one passes the gate; that one loads omega; then the Costas loop tracks alone",
              "FE_AUTO = 3   (continuous): every window that passes loads omega; between the loads the Costas integrator keeps updating it"]
    for k, ax in enumerate(axs):
        ax.set_ylim(0, 3.0); ax.set_yticks([]); ax.set_title(titles[k], fontsize=9, loc="left")
        for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
        ax.axvline(0, color="#999", lw=0.8); ax.text(0, 2.75, " enable (FE_AUTO written)", fontsize=7.4, color="#555", va="center")
    # costas only
    axs[0].add_patch(Rectangle((0, 0.4), nwin * N, 1.3, fc="#e8eef6", ec="#999", lw=0.8)); axs[0].text(nwin * N / 2, 1.05, "Costas loop only:  omega <= omega + CB x e_c >> 8  at every symbol", ha="center", va="center", fontsize=8.5)
    # once: windows 0..2, the third passes
    for i in range(3):
        ok = i == 2
        axs[1].add_patch(Rectangle((i * N, 1.7), N, 0.8, fc="#d9f0d3" if ok else "#f6d9d9", ec="#2a9d4f" if ok else "#b05050"))
        axs[1].text(i * N + N / 2, 2.1, "window %d\nN symbols\n%s" % (i + 1, "passes the gate" if ok else "quality < q_min: no load, next window"), ha="center", va="center", fontsize=7.2)
    axs[1].annotate("", xy=(3 * N, 1.2), xytext=(3 * N, 1.7), arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.5))
    axs[1].text(3 * N + 40, 1.45, "LOAD  omega <= atan2 result\n(S7 of the next symbol)", fontsize=7.6, color=RED, va="center")
    axs[1].add_patch(Rectangle((3 * N, 0.4), (nwin - 3) * N, 0.7, fc="#e8eef6", ec="#999", lw=0.8)); axs[1].text(3 * N + (nwin - 3) * N / 2, 0.75, "estimator idle (lock_once); Costas loop tracks", ha="center", va="center", fontsize=8)
    axs[1].add_patch(Rectangle((0, 0.4), 3 * N, 0.7, fc="#e8eef6", ec="#999", lw=0.8)); axs[1].text(1.5 * N, 0.75, "omega: Costas integrator (still at its start value)", ha="center", va="center", fontsize=8)
    # continuous
    for i in range(nwin):
        axs[2].add_patch(Rectangle((i * N, 1.7), N, 0.8, fc="#d9f0d3", ec="#2a9d4f"))
        axs[2].text(i * N + N / 2, 2.1, "window %d" % (i + 1), ha="center", va="center", fontsize=7.4)
        axs[2].annotate("", xy=((i + 1) * N, 1.15), xytext=((i + 1) * N, 1.7), arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.3))
    axs[2].text(0.5 * N, 0.8, "load every window; in between omega = loaded value + CB x e_c (the Costas loop pulls it towards the true frequency)", fontsize=8, va="center")
    for ax in axs: ax.set_xlim(-250, nwin * N + 700)
    axs[2].set_xticks([i * N for i in range(nwin + 1)]); axs[2].set_xticklabels(["%d symbols\n%.1f ms" % (i * N, i * N / 960.0) for i in range(nwin + 1)], fontsize=7.4)
    fig.suptitle("What FE_AUTO does: the windows (N = 1024 symbols = 1.07 ms each), the gate and the loads into the Costas frequency", fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig(os.path.join(OUT, "qpsk_chain3_modes.png"), dpi=130); plt.close(fig)


if __name__ == "__main__":
    compare(); block(); modes(); print("wrote qpsk_chains_compare.png, qpsk_chain3_block.png, qpsk_chain3_modes.png to", os.path.normpath(OUT))
