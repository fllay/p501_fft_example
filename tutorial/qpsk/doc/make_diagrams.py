#!/usr/bin/env python3
"""Draws the block diagrams of TUTORIAL_QPSK.md into tutorial/img/ (qpsk_block_system.png, qpsk_block_tx.png, qpsk_block_rx.png): python3 make_diagrams.py"""
import os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "img")
COL = dict(logic="#dbe9f7", mem="#fde9c9", dsp="#d9f0d3", io="#eeeeee", ctl="#f6d9e4")
EDGE, RED = "#33475b", "#b03030"


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w / 10, h / 10)); ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off"); return fig, ax


def box(ax, x, y, w, h, text, kind="logic", fs=7.5, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=COL[kind], ec=EDGE, lw=1.1, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal", linespacing=1.3, zorder=3)


def path(ax, pts, label=None, color=EDGE, ls="-", lpos=0, ldx=0, ldy=1.0, fs=6.8, lha="center", arrow=True):
    """Polyline with an arrow head at the end; the label sits on segment number `lpos`."""
    for a, b in zip(pts[:-2], pts[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=1.2, ls=ls, zorder=1)
    ax.annotate("", xy=pts[-1], xytext=pts[-2], arrowprops=dict(arrowstyle="-|>" if arrow else "-", color=color, lw=1.2, ls=ls, shrinkA=0, shrinkB=0), zorder=1)
    if label:
        a, b = pts[lpos], pts[lpos + 1]
        ax.text((a[0] + b[0]) / 2 + ldx, (a[1] + b[1]) / 2 + ldy, label, ha=lha, va="bottom", fontsize=fs, color=color if color == RED else "#222", zorder=4, linespacing=1.2)


def region(ax, x, y, w, h, label):
    ax.add_patch(Rectangle((x, y), w, h, fc="#f4f7fa", ec="#9fb0c0", lw=1, ls="--", zorder=0))
    ax.text(x + 1.2, y + h - 1.2, label, fontsize=7.5, color="#475b6e", va="top", style="italic")


def legend(ax, x, y):
    for i, (k, t) in enumerate([("logic", "logic / registers"), ("mem", "memory / ROM"), ("dsp", "multipliers (DSP48)"), ("ctl", "control / registers / counters"), ("io", "outside this block")]):
        ax.add_patch(Rectangle((x + i * 30, y), 2.6, 2.2, fc=COL[k], ec=EDGE, lw=0.8)); ax.text(x + i * 30 + 3.6, y + 1.1, t, fontsize=6.8, va="center")


# ============================================================ system
def system():
    fig, ax = canvas(150, 92)
    ax.text(75, 88.5, "p501_qpsk_trx: the transmitter and the receiver in one overlay", fontsize=10.5, fontweight="bold", ha="center")
    region(ax, 30, 56, 62, 28, "l_clk domain: 7.68 MHz (= 2 x the 3.84 MSPS sample rate)")
    region(ax, 30, 6, 62, 40, "pl_clk0 domain: 100 MHz (registers and the receiver engine)")
    box(ax, 2, 28, 18, 30, "Zynq PS\n\nPython (PYNQ)\nJupyter,\nscripts as root\n\nMMIO read /\nwrite", "io", 8, True)
    path(ax, [(20, 43), (26, 43)], arrow=False); ax.plot([26, 26], [20, 70], color=EDGE, lw=1.6)
    ax.text(26, 72, "AXI-Lite\n(axi_cpu_interconnect)", fontsize=6.8, ha="center", va="bottom")
    box(ax, 34, 62, 22, 14, "qpsk_regs  (dds_regs.v)\n0x9C460000\nenable, amp, commit\n(hand-over to l_clk)", "ctl", 7)
    box(ax, 62, 62, 24, 14, "qpsk_tx\nPRBS-15 -> DQPSK\n-> RRC pulse -> dac_i, dac_q", "logic", 7.5, True)
    box(ax, 34, 14, 19, 26, "registers of qpsk_rx\n0x9C470000\nTA TB CA CB MU REF\nG0 W0 MAXR CTRL\ncounters, OMEGA,\nRATE, capture RAM", "ctl", 6.8)
    box(ax, 58, 14, 30, 26, "qpsk_rx\nsample RAM -> matched filter\n-> AGC -> timing loop\n-> Costas loop -> bits\n-> PRBS-15 checker\n(engine on aclk)", "logic", 7.5, True)
    path(ax, [(26, 69), (34, 69)]); path(ax, [(26, 27), (34, 27)])
    path(ax, [(56, 69), (62, 69)], "enable\namp", ldy=0.6, fs=6.2)
    path(ax, [(53, 27), (58, 27)])
    box(ax, 98, 28, 16, 50, "axi_ad9361\n(ADI core)\n\nDAC path\ndac_data_i0/q0\ndac_valid_i0\n\n\nADC path\nadc_data_i0/q0\nadc_valid_i0\n\nl_clk out", "io", 7.2)
    path(ax, [(86, 69), (98, 69)], "dac_i/q, ce", ldy=0.8)
    path(ax, [(98, 33), (93, 33), (93, 33), (88, 33)], "adc_i/q,\nadc_valid", ldy=0.5, lpos=0, ldx=0.5, fs=6.3)
    path(ax, [(106, 78), (106, 83), (58, 83), (58, 77.5)], "l_clk", ldy=0.5, lpos=1, ldx=22, fs=6.5) if False else None
    box(ax, 122, 44, 26, 34, "AD9361\nRF transceiver\n915 MHz, 3.84 MSPS\n(configured over SPI\nby p501_radio.py,\nPS side)", "io", 7.2, True)
    path(ax, [(114, 70), (122, 70)], "LVDS data", ldy=0.5, fs=6.3); path(ax, [(122, 52), (114, 52)], "data clock", ldy=0.5, fs=6.3)
    box(ax, 122, 18, 12, 9, "TX1\nantenna", "io", 7); box(ax, 136, 18, 12, 9, "RX1\nantenna", "io", 7)
    path(ax, [(128, 44), (128, 27)], "RF out", ldx=-5.5, ldy=-5, fs=6.3); path(ax, [(142, 27), (142, 44)], "RF in", ldx=5.5, ldy=-5, fs=6.3)
    ax.text(75, 2, "One P501: the transmitter and the receiver share the AD9361 (TX1 and RX1) and the PS; the B210 (GNU Radio) is the other end of the link.", fontsize=7.2, ha="center")
    legend(ax, 4, 90) if False else None
    fig.savefig(os.path.join(OUT, "qpsk_block_system.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


# ============================================================ transmitter
def transmitter():
    fig, ax = canvas(150, 92)
    ax.text(75, 88, "qpsk_tx.v : one output sample for every ce (= dac_valid), 4 samples per symbol", fontsize=10.5, fontweight="bold", ha="center")
    # top row: bit source -> symbol
    box(ax, 2, 56, 20, 20, "PRBS-15\nLFSR\nx^15 + x^14 + 1\nseed 0x7FFF\n(lfsr, l1, l2)", "logic", 7.5, True)
    box(ax, 28, 56, 20, 20, "2 bits per\nsymbol\nc = {lfsr[14],\nl1[14]}\nfirst bit = MSB", "logic", 7.5)
    box(ax, 54, 56, 20, 20, "pre-differential\nmap\n[0,1,3,2]\n(swap 2 and 3)", "logic", 7.5)
    box(ax, 80, 56, 20, 20, "differential\nencoder\nd = d + p\n(mod 4)", "logic", 7.5, True)
    box(ax, 106, 56, 18, 20, "quadrant\nni = d1 ^ d0\nnq = d1\n(1 = negative)", "logic", 7.5)
    box(ax, 130, 56, 18, 20, "last 12\nsymbols\nhist_i, hist_q\n(shift registers)", "mem", 7.5, True)
    for a, b in [(22, 28), (48, 54), (74, 80), (100, 106), (124, 130)]: path(ax, [(a, 66), (b, 66)])
    ax.text(12, 52.2, "advances only when ph = 3", fontsize=6.6, ha="center", color="#555", style="italic"); ax.text(90, 52.2, "d changes only when ph = 3", fontsize=6.6, ha="center", color="#555", style="italic")
    # bottom row (right to left): hist + ROM -> adders -> register -> scale -> output
    box(ax, 130, 14, 18, 20, "qpsk_rrc_coef\nROM:\n12 taps h[4j+ph]\n16-bit signed", "mem", 7.2, True)
    box(ax, 98, 14, 26, 20, "12 additions / subtractions\nsum = SUM +-h[j]\nsign j from hist bit j\n(symbols are +-1: no\nmultipliers)", "dsp", 7.2, True)
    box(ax, 72, 14, 20, 20, "ysum_i, ysum_q\n17-bit registers\n(pipeline\nstage 1)", "logic", 7.2)
    box(ax, 44, 14, 22, 20, "x amp (Q15)\ndac = prod[30:15]\n(pipeline stage 2,\n2 DSP multipliers)", "dsp", 7.2, True)
    box(ax, 4, 14, 34, 20, "dac_i, dac_q (16-bit registers)\n-> axi_ad9361\ndac_data_i0, dac_data_q0\n(12 bits used by the AD9361)", "io", 7.2, True)
    path(ax, [(139, 56), (139, 45), (111, 45), (111, 34)], "signs of the 12 symbols", lpos=1, ldy=0.8, fs=6.8)
    path(ax, [(130, 24), (124, 24)], "h[11..0]", ldy=0.7, fs=6.5)
    path(ax, [(98, 24), (92, 24)]); path(ax, [(72, 24), (66, 24)]); path(ax, [(44, 24), (38, 24)])
    box(ax, 130, 0, 18, 8, "ph counter 0..3", "ctl", 7.2)
    path(ax, [(139, 8), (139, 14)], "ph", ldx=2.5, ldy=-1.5, fs=6.8)
    box(ax, 44, 0, 22, 8, "amp  (Q15)", "ctl", 7.2); path(ax, [(55, 8), (55, 14)])
    ax.text(100, 4, "enable = 0 resets state, output = 0.  enable = 1 starts the PRBS at its first bit.", fontsize=6.8, ha="center", style="italic", color="#444")
    ax.text(75, 39.5, "symbol points d = 0, 1, 2, 3  ->  (+,+)  (-,+)  (-,-)  (+,-)   (GNU Radio constellation_dqpsk)", fontsize=7, ha="center", color="#222")
    fig.savefig(os.path.join(OUT, "qpsk_block_tx.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


# ============================================================ receiver
def receiver():
    fig, ax = canvas(155, 112)
    ax.text(77, 108, "qpsk_rx.v : one pass of the engine per symbol (about 65 of the 104 clock cycles that 100 MHz gives at 960 ksym/s)", fontsize=10, fontweight="bold", ha="center")
    region(ax, 1, 66, 54, 36, "adc_clk (= l_clk) domain"); region(ax, 56, 66, 99, 36, "aclk = pl_clk0 (100 MHz) domain: engine and registers")
    row1 = [("adc_i, adc_q\nadc_valid", "io", 2, 12), ("sample RAM\nsram[0..255]\nwr_cnt, wr_gray", "mem", 17, 17), ("two flops +\nGray -> binary:\nwr_sync", "ctl", 37, 16),
            ("MAC, 44 taps\n4 parallel DSP\nmultiplies\nROM: 16 arms,\nmatched +\nderivative", "dsp", 58, 19), ("AGC\nm' = m x g >> 10\nd' = d x g >> 10\ng from the level\n(MU, REF, G0)", "dsp", 80, 19),
            ("derotate\nz = m' e^(-j theta)\ncos/sin ROM\n1024 entries", "dsp", 102, 16), ("slicer\nsigns of zi, zq\ndifferential\ndecode\n-> 2 bits", "logic", 121, 15), ("PRBS-15\nchecker\nBITS,\nMISMATCH", "logic", 139, 14)]
    for t, k, x, w in row1: box(ax, x, 70, w, 24, t, k, 6.9, True)
    for a, b in [(14, 17), (34, 37), (53, 58), (77, 80), (99, 102), (118, 121), (136, 139)]: path(ax, [(a + (0 if a not in (14,) else 0), 82), (b, 82)])
    ax.text(10, 96, "", fontsize=1)
    # timing loop under MAC / AGC
    box(ax, 62, 36, 35, 22, "timing error detector\ne_t = (mi2*di2 + mq2*dq2) >> 13\nrate  += (TB * e_t + 2^20) >> 21\np     += 64<<16 + rate + (TA * e_t) >> 21", "dsp", 6.9, True)
    path(ax, [(89, 70), (89, 58)], "m', d'", ldx=3, ldy=-0.5, fs=6.6)
    path(ax, [(68, 58), (68, 70)], "p: sample t, arm k", color=RED, ls="--", ldx=-10.5, ldy=-0.5, fs=6.6, lha="center")
    # Costas loop under derotate / slicer
    box(ax, 100, 36, 36, 22, "Costas error detector\ne_c = sgn(zi) zq - sgn(zq) zi\nomega += (CB * e_c) >> 8\ntheta += omega + (CA * e_c) >> 8", "dsp", 6.9, True)
    path(ax, [(104, 70), (104, 58)], "z", ldx=2, ldy=-0.5, fs=6.6)
    path(ax, [(112, 58), (112, 70)], "theta", color=RED, ls="--", ldx=3.5, ldy=-1.2, fs=6.6)
    # capture RAM under the slicer
    box(ax, 139, 36, 15, 22, "capture RAM\n1024 x {zq, zi}\nread at +0x1000", "mem", 6.6, True)
    path(ax, [(143, 70), (143, 58)]) if False else None
    path(ax, [(131, 70), (131, 62), (146, 62), (146, 58)], "zi, zq", lpos=1, ldy=0.4, fs=6.6)
    # registers
    box(ax, 2, 6, 152, 18, "AXI-Lite register block (aclk):   TA TB CA CB MU REF G0 W0 MAXR  (loop gains, AGC, start values)   |   CTRL: run, capture arm   |   read back:  STATUS SYMBOLS BITS MISMATCH OMEGA RATE GAIN WRCNT OVERRUNS", "ctl", 7, True)
    path(ax, [(79, 24), (79, 36)], "TA, TB", ldx=3.5, ldy=-1, fs=6.6); path(ax, [(118, 24), (118, 36)], "CA, CB", ldx=3.5, ldy=-1, fs=6.6)
    path(ax, [(146, 36), (146, 24)]); ax.text(148, 29, "read", fontsize=6.6)
    ax.text(30, 50, "engine sequence per symbol:\nST_WAIT: until the 44 samples ending at\nsample t are written (wr_sync - base - t > 0)\n-> ST_MAC: 47 cycles of multiply-accumulate\n-> S0 .. S9: AGC, timing, derotation, Costas,\n    decision, counters (one cycle each)", fontsize=6.9, ha="center", va="center", color="#333", bbox=dict(boxstyle="round", fc="white", ec="#9fb0c0"))
    path(ax, [(30, 62), (56, 62), (58, 74)], None, color="#9fb0c0", ls=":") if False else None
    ax.text(77, 29, "", fontsize=1)
    ax.text(77, 1.2, "dashed red = feedback of the two loops;  the AGC (S3) and both loops update once per symbol; SYMBOLS counts the passes", fontsize=6.9, ha="center", color="#444")
    fig.savefig(os.path.join(OUT, "qpsk_block_rx.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    system(); transmitter(); receiver(); print("wrote", os.path.normpath(OUT))
