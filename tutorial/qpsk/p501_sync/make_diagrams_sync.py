#!/usr/bin/env python3
"""Figures of the m-sequence synchronisation project into tutorial/img/:
    qpsk_sync_frame.png   the frame format, the correlation of the phase steps with the m-sequence (from the integer model on a synthetic signal) and the frame tracker
    qpsk_sync_block.png   the implementation: the engine of the receiver with the synchroniser beside it (qpsk_rx_sync.v + qpsk_sync.v)
    python3 make_diagrams_sync.py"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "doc")); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "p501_rx"))
from make_diagrams import canvas, path, EDGE, RED, OUT
import qpsk_rx_fixed as F, qpsk_sync_fixed as S
from make_frame_signal import synth_frames
from qpsk_frame import chips

ENG, SYN, GREY, CTL, FRM = "#dbe9f7", "#d9f0d3", "#eeeeee", "#f6d9e4", "#fde9c9"


def pad(ax, x, y, w, h, text, fc, fs=7.4, ec=EDGE, lw=1.1, bold=False):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal", linespacing=1.3, zorder=3)


def frame_fig():
    PL = 192; FL = 64 + PL
    xi, xq = synth_frames(60000, pl=PL, f_off_hz=9700, snr_db=20); r = F.receive_fixed(xi, xq); s = S.run_sync(r["mi2"], r["mq2"], FL, PL)
    fig = plt.figure(figsize=(15.5, 9.2)); gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.25, 1.1], hspace=0.55, wspace=0.18)
    # (a) the frame
    ax = fig.add_subplot(gs[0, :]); ax.set_xlim(0, 1130); ax.set_ylim(0, 3); ax.axis("off")
    ax.set_title("The frame: a 64-symbol preamble whose phase STEPS are the chips of an m-sequence, then the payload (PRBS-15); repeated, back to back", fontsize=10, loc="left", fontweight="bold")
    ax.add_patch(Rectangle((0, 1.2), 64 * 1.0, 1.3, fc="#d9f0d3", ec=EDGE)); ax.text(32, 1.85, "preamble\n64 symbols", ha="center", va="center", fontsize=8.5)
    ax.add_patch(Rectangle((64, 1.2), 960 / 1.0 * 0.9, 1.3, fc="#dbe9f7", ec=EDGE)); ax.text(64 + 432, 1.85, "payload: PL symbols of PRBS-15 (restarted in every frame; 960 in the tests)", ha="center", va="center", fontsize=8.5)
    ax.add_patch(Rectangle((64 + 864, 1.2), 160 * 0.0 + 150, 1.3, fc="#d9f0d3", ec=EDGE)); ax.text(64 + 864 + 75, 1.85, "next\npreamble", ha="center", va="center", fontsize=8.5)
    ax.text(0, 0.55, "symbol 0: reference (step 0)   symbols 1..63: step 0 for chip +1, step 180 degrees for chip -1   chips = m-sequence x^6 + x + 1 (period 63, autocorrelation 63 / -1)", fontsize=8.3, color="#333")
    ax.text(0, 0.1, "the receiver correlates the phase STEP d = m_n conj(m_n-1) (no carrier phase in it, and only 2 pi f T from the frequency offset) with the chips: it works before any loop has locked", fontsize=8.3, color="#1d4f91")
    # (b) correlation magnitude vs symbol
    ax = fig.add_subplot(gs[1, 0]); n0 = 8000; n = np.arange(n0, n0 + 1100); met = s["met"][n0:n0 + 1100]; en = s["en"][n0:n0 + 1100]
    ax.plot(n, met / 1e3, color="#2a9d4f", lw=1.0, label="|C| (the correlation)"); ax.plot(n, en / 1e3, color="#b0b0b0", lw=0.9, label="sum |d| (the energy)"); ax.plot(n, 0.5469 * en / 1e3, color="#c0392b", lw=0.8, ls="--", label="threshold 140/256 x energy")
    pk = [p for p in s["peaks"] if n0 <= p < n0 + 1100]; ax.plot(pk, [s["met"][p] / 1e3 for p in pk], "v", color="#c0392b", ms=6)
    ax.set_xlabel("symbol index (frame length 256)"); ax.set_ylabel("thousands of counts"); ax.set_title("|C| against the threshold: one peak per frame (v)", fontsize=9, loc="left"); ax.legend(fontsize=7.5, loc="upper right"); ax.grid(alpha=.3)
    ax = fig.add_subplot(gs[1, 1]); w = np.arange(-30, 31); c = chips(); full = np.array([abs(np.dot(c, np.roll(c, k))) for k in w])
    ax.stem(w, full, basefmt=" ", linefmt="#2a9d4f", markerfmt="o"); ax.set_xlabel("shift (symbols)"); ax.set_ylabel("|autocorrelation|"); ax.set_title("why an m-sequence: autocorrelation 63, and 1 elsewhere (-36 dB)", fontsize=9, loc="left"); ax.grid(alpha=.3)
    # (c) the frequency from the correlation and the tracker
    ax = fig.add_subplot(gs[2, 0]); hp = [p for (nn, k, p) in s["events"] if k in ("hit", "lock")]
    f = [S.freq_hz(s["cre"][p], s["cim"][p]) for p in hp]; ax.plot(range(len(f)), np.array(f) / 1e3, "o-", ms=3, lw=0.8, color="#2a9d4f"); ax.axhline(9.7, color="#c0392b", ls="--", lw=1)
    ax.set_xlabel("frame"); ax.set_ylabel("kHz"); ax.set_title("frequency from the preamble: f = arg(C) / (2 pi) x 960 kHz, one value per frame (true +9.7 kHz)", fontsize=8.6, loc="left"); ax.grid(alpha=.3)
    ax = fig.add_subplot(gs[2, 1]); ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 40)
    pad(ax, 2, 24, 26, 12, "SEARCH\nremember the last peak", GREY, fs=7.8); pad(ax, 62, 24, 36, 12, "LOCKED\nexpected peak = ref + FL (+-1)", SYN, fs=7.8)
    path(ax, [(28, 32), (62, 32)], label="a peak one frame after the remembered one", lpos=0, ldy=0.8, fs=6.6)
    path(ax, [(62, 27), (28, 27)], label="3 misses in a row", lpos=0, ldy=-3.4, fs=6.6, color=RED)
    ax.text(80, 21, "hit: ref = peak;  miss: ref += FL", fontsize=7.4, ha="center"); ax.text(50, 12, "payload gate (for the engine's symbol n):  LOCKED and  2 <= n - ref - 1 < PL", fontsize=8.2, ha="center", fontweight="bold", color="#1d4f91")
    ax.text(50, 6, "the PRBS-15 checker counts only inside the gate and restarts when it opens", fontsize=7.8, ha="center", color="#333"); ax.set_title("the frame tracker and the gate", fontsize=8.8, loc="left")
    fig.suptitle("m-sequence frame synchronisation (chapter 4e, part 1)", fontsize=11.5, fontweight="bold", y=0.995); fig.savefig(os.path.join(OUT, "qpsk_sync_frame.png"), dpi=125, bbox_inches="tight"); plt.close(fig)


def block_fig():
    fig, ax = canvas(170, 100)
    ax.text(85, 97, "The synchroniser in the FPGA: rtl/qpsk_rx_sync.v with qpsk_sync.v beside the engine", fontsize=11, fontweight="bold", ha="center")
    ax.text(2, 91.5, "ENGINE of the receiver (chapter 4d)", fontsize=8, fontweight="bold", color="#2b4a6b")
    pad(ax, 2, 74, 24, 14, "ADC samples\nsample RAM\n(l_clk -> aclk)", GREY); pad(ax, 32, 74, 28, 14, "polyphase MAC\nmatched + derivative\n(16 arms x 44 taps)", ENG); pad(ax, 66, 74, 22, 14, "AGC\nm = (mi2, mq2)", ENG)
    pad(ax, 94, 74, 26, 14, "timing loop", ENG); pad(ax, 126, 74, 40, 14, "Costas loop (frequency OMEGA,\ngains CA/CB) -> decision ->\ndifferential decoder -> 2 bits", ENG)
    for a, b in ((26, 32), (60, 66), (88, 94)): path(ax, [(a, 81), (b, 81)])
    path(ax, [(120, 78), (126, 78)], arrow=False, color="#999")
    pad(ax, 126, 54, 40, 14, "PRBS-15 checker: BITS, MISMATCH\ncounts only when GATE = 1,\nrestarts when the gate opens", CTL, fs=7.2, ec=RED, lw=1.5)
    path(ax, [(146, 74), (146, 68)])
    ax.text(147.5, 70.5, "2 bits", fontsize=6.8)
    ax.add_patch(Rectangle((1, 1), 168, 46, fc="#f3faf1", ec="#2a9d4f", lw=1.3, ls="--", zorder=0))
    ax.text(3, 43.5, "SYNCHRONISER qpsk_sync.v: per symbol (pulse go = state S2), about 55 of the 104 clock cycles; the engine is not slowed down", fontsize=8, fontweight="bold", color="#1d6b34")
    path(ax, [(77, 74), (77, 50.5), (10, 50.5), (10, 40)], color="#2a9d4f"); ax.text(30, 51.5, "m: after the AGC, before the Costas loop", fontsize=7.2, color="#1d6b34")
    y = 26; bw = 24
    pad(ax, 3, y, bw, 13, "d = m x conj(m_prev)\n4 multipliers\nround >> 15, clip", SYN, fs=6.8); pad(ax, 32, y, bw, 13, "ring RAM 64 x 32\n(two copies:\ntwo taps per clock)", SYN, fs=6.8)
    pad(ax, 61, y, 30, 13, "C = sum chip[k] d[n-62+k]\nE = sum |d|     (63 taps,\n32 clocks)  chip = m-sequence", SYN, fs=6.8); pad(ax, 96, y, 24, 13, "M = |C| ~ max + min/2\ncandidate:\n256 M >= THR E", SYN, fs=6.8)
    pad(ax, 125, y, 40, 13, "peak at n-1: candidate, M(n-1) >= M(n-2),\nM(n-1) > M(n)   (one symbol look-ahead)", SYN, fs=6.8)
    for a, b in ((27, 32), (56, 61), (91, 96), (120, 125)): path(ax, [(a, y + 6.5), (b, y + 6.5)])
    pad(ax, 3, 4, 52, 15, "frame tracker: SEARCH -> LOCKED on two peaks FL apart (+-TOL);\nhit: ref = peak; miss when no peak by ref + FL + TOL + 1;\nMISSMAX misses -> SEARCH.   registers SY_FL, SY_PL, SY_THR,\nSY_TOL, SY_MISSMAX, SY_GUARD", CTL, fs=6.5)
    pad(ax, 59, 4, 52, 15, "gate = LOCKED and GUARD <= n - ref - 1 < PL\nread back: NDET, NHIT, NMISS, NFALSE, NLOCK, NLOST, REF,\nC = (CRE, CIM) at the last peak, MET, EN, PEAKIDX, LATE\nf = arg(C) / (2 pi) x 960 kHz", GREY, fs=6.5)
    pad(ax, 115, 4, 50, 15, "HARDWARE ACQUISITION: at a lock / hit, atan2 CORDIC of C\n(18 iterations) -> w = angle << 12 -> LOAD into OMEGA (S7);\nnarrow = locked and NSW hits after the lock -> tracking gains\nCA, CB, else CAW, CBW.   SY_LOAD, SY_NLOAD, SY_NSW", FRM, fs=6.3, ec=RED, lw=1.4)
    path(ax, [(30, 19), (30, y)], arrow=False, color="#999", ls="--"); path(ax, [(85, 19), (85, y)], arrow=False, color="#999", ls="--"); path(ax, [(140, y), (140, 19)], arrow=False, color="#999", ls="--")
    path(ax, [(93.5, 19), (93.5, 61), (126, 61)], color=RED); ax.text(100, 62.2, "GATE", fontsize=8, color=RED, fontweight="bold")
    path(ax, [(165, 8), (169.3, 8), (169.3, 81), (166, 81)], color=RED); ax.text(158.5, 21.5, "LOAD OMEGA,\nselect the CA / CB gains", fontsize=6.8, color=RED, ha="center")
    fig.savefig(os.path.join(OUT, "qpsk_sync_block.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    frame_fig(); block_fig(); print("wrote qpsk_sync_frame.png, qpsk_sync_block.png to", os.path.normpath(OUT))
