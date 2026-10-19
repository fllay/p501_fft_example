#!/usr/bin/env python3
"""Draws the FUNCTIONAL diagrams of TUTORIAL_QPSK.md section A.5 into tutorial/img/ (what each block does and why it is needed; the Verilog implementation
diagrams are in make_diagrams.py):   qpsk_func_link.png  qpsk_func_tx.png  qpsk_func_rx.png  qpsk_func_timing.png  qpsk_func_costas.png

    python3 make_functional_diagrams.py
"""
import os, textwrap
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from make_diagrams import canvas, path, EDGE, RED, OUT

TX_C, RX_C, CH_C, WHY_C = "#dbe9f7", "#d9f0d3", "#fbe3e3", "#1d4f91"


def rbox(ax, x, y, w, h, fc, ec=EDGE, lw=1.1, z=2, r=1.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=%g" % r, fc=fc, ec=ec, lw=lw, zorder=z))


def card(ax, x, y, w, h, title, does, why, ref, color, wrap, fs=7.0):
    """A block of the functional diagram: title, what it does, WHY it is needed (blue), and where it is in the text (grey)."""
    rbox(ax, x, y, w, h, color)
    top = y + h - 1.6
    ax.text(x + 1.3, top, title, fontsize=fs + 1.6, fontweight="bold", va="top", zorder=3, linespacing=1.25)
    yy = top - 3.0 * (title.count("\n") + 1) - 0.8
    t1 = textwrap.fill(does, wrap); ax.text(x + 1.3, yy, t1, fontsize=fs, va="top", zorder=3, linespacing=1.35)
    yy -= 2.5 * (t1.count("\n") + 1) + 1.3
    t2 = textwrap.fill("Why: " + why, wrap); ax.text(x + 1.3, yy, t2, fontsize=fs, va="top", color=WHY_C, zorder=3, linespacing=1.35)
    ax.text(x + 1.3, y + 1.0, ref, fontsize=fs - 0.8, va="bottom", color="#666", style="italic", zorder=3)


COLS = [2 + i * 33.5 for i in range(5)]           # five columns of width 28 across the 165-unit canvas
CW = 28


# ------------------------------------------------------------------ 1. the link and what goes wrong
def link():
    fig, ax = canvas(165, 108)
    ax.text(82.5, 104.5, "The link, the things that go wrong in it, and the block that fixes each", fontsize=11, fontweight="bold", ha="center")
    ax.text(2, 97.8, "TRANSMITTER  (P501 FPGA, or B210 with GNU Radio)", fontsize=8, color="#2b4a6b", fontweight="bold")
    tx = ["Test bits\nPRBS-15", "Bit pairs, pre-diff map,\ndifferential encoder", "QPSK points\n(+-1, +-1) = 4 phases", "Pulse shaping\nroot-raised cosine,\n4 samples per symbol", "DAC and AD9361:\n915 MHz carrier"]
    for x, t in zip(COLS, tx):
        rbox(ax, x, 80, CW, 14, TX_C); ax.text(x + CW / 2, 87, t, ha="center", va="center", fontsize=7.8, zorder=3, linespacing=1.3)
    for i in range(4): path(ax, [(COLS[i] + CW, 87), (COLS[i + 1], 87)])
    path(ax, [(COLS[4] + CW / 2, 80), (COLS[4] + CW / 2, 73)])
    # channel
    rbox(ax, 0.5, 45, 164, 28, CH_C, ec="#b05050", lw=1.2, z=1, r=1.6)
    ax.text(3, 70.3, "THE CHANNEL AND THE TWO RADIOS: what the receiver has to cope with", fontsize=8.5, color="#8a2a2a", fontweight="bold", va="center")
    tags = ["12-bit ADC: the signal must\nbe well above one\nquantisation step", "Level unknown:\npath loss, antenna gain,\nRX gain setting", "Noise; unknown sample\ninstant; sample clocks\ndiffer by 10.4 ppm", "Carrier offset +9.7 kHz\n(two crystals) and an\nunknown phase", "4-fold phase ambiguity:\na locked loop can sit\n90 / 180 / 270 deg off"]
    for x, t in zip(COLS, tags):
        rbox(ax, x, 48, CW, 17, "#fff6f6", ec="#b05050", lw=1, r=1.2); ax.text(x + CW / 2, 56.5, t, ha="center", va="center", fontsize=7.2, color="#6b1d1d", zorder=3, linespacing=1.3)
    # receiver
    ax.text(2, 36.3, "RECEIVER  (P501 FPGA, or GNU Radio on the PC)", fontsize=8, color="#2b4a6b", fontweight="bold")
    rx = ["RF down-conversion,\nADC 3.84 MSPS", "AGC\n(gain loop)", "Matched filter +\nsymbol timing loop", "Carrier recovery\n(Costas loop)", "Decision +\ndifferential decode"]
    for x, t in zip(COLS, rx):
        rbox(ax, x, 14, CW, 18, RX_C); ax.text(x + CW / 2, 23, t, ha="center", va="center", fontsize=7.8, zorder=3, linespacing=1.3)
    for i in range(4): path(ax, [(COLS[i] + CW, 23), (COLS[i + 1], 23)])
    path(ax, [(COLS[0] - 1.0, 73), (COLS[0] - 1.0, 59), (COLS[0] - 1.0, 59)], arrow=False, color="#b05050") if False else None
    for x in COLS:                                                                 # "this problem is solved by this block"
        path(ax, [(x + CW / 2, 48), (x + CW / 2, 32.4)], color=RED)
    path(ax, [(COLS[4] + CW, 23), (COLS[4] + CW + 1.5, 23)], arrow=False)
    ax.text(82.5, 9.0, "bits out -> compared with the PRBS-15 by the bit error counter", fontsize=7.8, ha="center", color="#333")
    ax.text(82.5, 4.5, "red arrows: the problem above is solved by the block below it", fontsize=7.8, ha="center", color=RED)
    path(ax, [(COLS[4] + CW / 2, 14), (COLS[4] + CW / 2, 11)])
    fig.savefig(os.path.join(OUT, "qpsk_func_link.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------ 2. transmitter
def transmitter():
    fig, ax = canvas(165, 50)
    ax.text(82.5, 47, "Transmitter: the functional blocks, what each does and why it is needed", fontsize=11, fontweight="bold", ha="center")
    W = 23.6; G = 3.4; wrap = 29
    xs = [2 + i * (W + G) for i in range(6)]
    cards = [
        ("1  Test bits\n    PRBS-15", "A pseudo-random bit sequence, period 32767 bits, generated by a 15-bit shift register.", "the receiver can predict the next bit from the last ones, so it counts bit errors with no reference copy and no software.", "Verilog: B.2"),
        ("2  Bit pairs and\n    map [0,1,3,2]", "Two bits form one symbol (1.92 Mbit/s -> 960 ksym/s). Chunks 2 and 3 swap.", "half the symbol rate for the same data, so half the bandwidth; the swap makes neighbouring phases differ in one bit only (Gray-like): a small phase error costs one bit.", "Verilog: B.2"),
        ("3  Differential\n    encoder", "d = d + p (mod 4): the data are the CHANGE of phase between symbols.", "the receiver's carrier loop cannot tell which of the 4 rotations it locked to; with the change of phase as data, the bits come out right whatever the rotation.", "Verilog: B.2"),
        ("4  Symbol\n    mapper", "d = 0..3 -> (+,+) (-,+) (-,-) (+,-): only the signs of I and Q.", "four equal-amplitude points: constant power, and the symbols are +-1, so the next filter needs additions only.", "Verilog: B.2"),
        ("5  Pulse shaping\n    RRC filter", "Each symbol becomes a root-raised-cosine pulse, 4 samples per symbol, 12 taps per phase (polyphase).", "a square pulse would spread over many MHz; the RRC limits the band to 1.3 MHz, and with the receiver's matched filter it leaves no inter-symbol interference at the sampling instants.", "Verilog: B.4, B.5"),
        ("6  Amplitude and\n    DAC / RF", "x amp (Q15), 16-bit samples to the AD9361, up-converted to 915 MHz; TX attenuation sets the power.", "sets the output level without clipping; the attenuation (20 to 89.75 dB) keeps the transmitted power very low.", "Verilog: B.6; Python: E.2"),
    ]
    for x, c in zip(xs, cards):
        card(ax, x, 2, W, 41, c[0], c[1], c[2], c[3], TX_C, wrap, fs=7.4)
    for i in range(5): path(ax, [(xs[i] + W, 22.5), (xs[i + 1], 22.5)])
    fig.savefig(os.path.join(OUT, "qpsk_func_tx.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------ 3. receiver
def receiver():
    fig, ax = canvas(165, 68)
    ax.text(82.5, 65, "Receiver: the functional blocks, what each does and why it is needed", fontsize=11, fontweight="bold", ha="center")
    W = 49.5; G = 6.0; wrap = 58
    xs = [2 + i * (W + G) for i in range(3)]
    y1, y2, H = 35, 2, 28.5
    top = [
        ("1  ADC samples and a sample RAM", "The AD9361 delivers 12-bit I/Q at 3.84 MSPS; a 256-entry dual-clock RAM hands them from the sample clock to the 100 MHz engine.", "the two clocks are unrelated, and the filter needs a window of 44 samples around the instant that the timing loop picks.", "Verilog: C.3"),
        ("2  AGC (level)", "A gain g follows the symbol magnitude towards a reference (2.0): g += MU x (REF - level).", "the loops below are designed for a known amplitude (their gain grows with its square); the received level changes by tens of dB with distance and gains.", "Verilog: C.5"),
        ("3  Matched filter and timing loop", "A polyphase RRC filter bank (16 arms of 1/16 sample) and a derivative filter; the timing error y x y' moves the arm and sample index.", "the filter maximises the SNR and removes ISI, but only if it is sampled at the right instant; the transmitter's clock is not ours (10.4 ppm), so the instant drifts and must be tracked.", "Verilog: C.4, C.6; A.5.4"),
    ]
    bot = [
        ("4  Carrier recovery: Costas loop", "z = m x exp(-j theta), a phase detector e = sgn(zi) zq - sgn(zq) zi, a 2nd-order loop (omega, theta) drives the NCO.", "the two radios' LOs differ by 9.7 kHz = 3.6 degrees per symbol, and the phase is unknown: without the loop the constellation would spin. omega is the measured carrier offset.", "Verilog: C.7, C.8; A.5.5"),
        ("5  Decision and differential decoder", "The signs of zi and zq give the point; the change from the previous point, through the map [0,1,3,2], gives the two bits.", "this is where the 4-fold ambiguity of the Costas loop disappears: a rotated constellation gives the same changes.", "Verilog: C.9"),
        ("6  Bit checker, counters, capture RAM", "A self-synchronising PRBS-15 checker counts bits and mismatches (3 per error); the loop states and 1024 soft symbols can be read back.", "bit errors are counted at 1.92 Mbit/s inside the FPGA, with no DMA and no software in the path; the capture RAM shows the constellation.", "Verilog: C.10, C.11"),
    ]
    for x, c in zip(xs, top): card(ax, x, y1, W, H, c[0], c[1], c[2], c[3], RX_C, wrap, fs=7.6)
    xs2 = list(reversed(xs))
    for x, c in zip(xs2, bot): card(ax, x, y2, W, H, c[0], c[1], c[2], c[3], RX_C, wrap, fs=7.6)
    for i in range(2): path(ax, [(xs[i] + W, y1 + H / 2), (xs[i + 1], y1 + H / 2)])
    path(ax, [(xs[2] + W / 2, y1), (xs[2] + W / 2, y2 + H)])
    for i in range(2): path(ax, [(xs2[i], y2 + H / 2), (xs2[i + 1] + W, y2 + H / 2)])
    fig.savefig(os.path.join(OUT, "qpsk_func_rx.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------ 4. timing recovery in pictures
def timing():
    nf = 16
    rng = np.random.RandomState(3)
    beta = 0.35
    t = np.arange(-8 * nf, 8 * nf + 1) / nf
    with np.errstate(divide="ignore", invalid="ignore"):
        rc = np.sinc(t) * np.cos(np.pi * beta * t) / (1 - (2 * beta * t) ** 2)
    rc[np.isclose(abs(t), 1 / (2 * beta))] = np.pi / 4 * np.sinc(1 / (2 * beta))
    nsym = 1500
    sym = rng.choice([-1.0, 1.0], nsym)
    x = np.zeros(nsym * nf); x[::nf] = sym
    y = np.convolve(x, rc, mode="same")
    dy = np.gradient(y) * nf                                       # slope per symbol
    offs = np.arange(-nf // 2, nf // 2 + 1)
    scurve = np.array([np.mean([y[k * nf + o] * dy[k * nf + o] for k in range(20, nsym - 20)]) for o in offs])
    fig = plt.figure(figsize=(15, 5.8))
    ax1 = fig.add_axes([0.05, 0.12, 0.43, 0.74]); ax2 = fig.add_axes([0.57, 0.12, 0.40, 0.74])
    tt = np.arange(-nf, nf + 1) / nf
    for k in range(40, 260):                                       # the eye diagram: 220 traces of the matched-filter output, two symbols wide
        ax1.plot(tt, y[k * nf - nf:k * nf + nf + 1], color="#33475b", lw=0.6, alpha=0.18)
    ax1.axvline(0, color="#2a9d4f", lw=2); ax1.axvline(-0.25, color="#c0392b", lw=1.5, ls="--"); ax1.axvline(0.25, color="#8e44ad", lw=1.5, ls="--")
    ax1.text(0.02, 1.62, "on time:\nevery trace passes through +-1\n(no inter-symbol interference)", color="#2a9d4f", fontsize=8.5, va="top")
    ax1.text(-0.27, -1.62, "early: the traces\nspread out", color="#c0392b", fontsize=8.5, ha="right", va="bottom")
    ax1.text(0.27, -1.62, "late: the traces\nspread out", color="#8e44ad", fontsize=8.5, va="bottom")
    ax1.set_ylim(-1.8, 1.8); ax1.set_xlabel("time around the symbol instant (symbols)"); ax1.set_ylabel("matched filter output y")
    ax1.set_title("the eye diagram: the receiver must sample where the eye is open", fontsize=10); ax1.grid(alpha=0.25)
    ax2.plot(offs / nf, scurve, "o-", color="#33475b")
    ax2.axhline(0, color="#999", lw=0.8); ax2.axvline(0, color="#2a9d4f", lw=2)
    ax2.set_xlabel("sampling-instant error (symbols):  negative = early, positive = late"); ax2.set_ylabel("average timing error  e = y x y'")
    ax2.set_title("the error detector's S-curve: e is 0 exactly when the instant is right", fontsize=10); ax2.grid(alpha=0.25)
    i_e = np.argmin(abs(offs / nf + 0.2)); i_l = np.argmin(abs(offs / nf - 0.2))
    ax2.annotate("early: e > 0\nthe loop moves the instant later", (offs[i_e] / nf, scurve[i_e]), xytext=(-0.47, scurve.max() * 0.45), arrowprops=dict(arrowstyle="->", color="#c0392b"), fontsize=8.5, color="#c0392b")
    ax2.annotate("late: e < 0\nthe loop moves it earlier", (offs[i_l] / nf, scurve[i_l]), xytext=(0.12, scurve.min() * 0.40), arrowprops=dict(arrowstyle="->", color="#8e44ad"), fontsize=8.5, color="#8e44ad")
    ax2.text(0.02, scurve.max() * 0.95, "y' (the derivative filter) is the slope of y:\nits sign says on which side of the peak we are.\nThe loop integrates e: the integrator becomes the\nsample-clock offset (10.4 ppm here).", fontsize=8.2, va="top", color="#333")
    fig.suptitle("Why symbol timing needs a loop, and why the receiver has a derivative filter (the pulse train of one axis; the same for I and Q)", fontsize=10.5, fontweight="bold")
    fig.savefig(os.path.join(OUT, "qpsk_func_timing.png"), dpi=130); plt.close(fig)


# ------------------------------------------------------------------ 5. Costas loop in pictures
def costas():
    fig = plt.figure(figsize=(15, 6.2))
    axd = fig.add_axes([0.01, 0.05, 0.52, 0.80]); axd.set_xlim(0, 100); axd.set_ylim(0, 62); axd.axis("off")
    axp = fig.add_axes([0.60, 0.13, 0.38, 0.70])
    # block diagram of the loop
    def blk(x, y, w, h, t, c="#d9f0d3", fs=8): rbox(axd, x, y, w, h, c); axd.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, zorder=3, linespacing=1.3)
    blk(2, 40, 14, 11, "samples after\nthe matched\nfilter  m", "#eeeeee")
    blk(24, 40, 14, 11, "derotate\nz = m e^(-j theta)\n(NCO cos/sin)")
    blk(48, 40, 16, 11, "slicer:\nnearest of the\n4 points")
    blk(74, 40, 22, 11, "bits\n(after the differential\ndecoder)", "#eeeeee")
    blk(24, 12, 20, 14, "phase detector\ne = sgn(zi) zq\n  - sgn(zq) zi")
    blk(54, 12, 18, 14, "loop filter\nalpha x e\n+ integrator beta")
    blk(78, 12, 18, 14, "NCO\ntheta += omega\n+ alpha x e")
    for a, b in [(16, 24), (38, 48), (64, 74)]: path(axd, [(a, 45.5), (b, 45.5)])
    path(axd, [(27, 40), (27, 26)], "z", ldx=2.0, ldy=-6)
    path(axd, [(44, 19), (54, 19)], "e"); path(axd, [(72, 19), (78, 19)])
    path(axd, [(87, 26), (87, 33), (35, 33), (35, 40)], color=RED, ls="--"); axd.text(60, 33.8, "theta: the NCO phase", fontsize=7.5, color=RED, ha="center")
    axd.text(52, 4.5, "omega (the integrator) settles on the carrier offset: this is the 'carrier offset' value that the receiver reports (+9.7 kHz).\nalpha and beta come from one loop bandwidth: wide = fast pull-in but noisy, narrow = quiet but slow.", fontsize=7.8, ha="center", color="#333", linespacing=1.4)
    axd.text(2, 58.5, "The Costas loop: why every block is there", fontsize=11, fontweight="bold")
    axd.text(2, 55.0, "derotate: removes the rotation   |   detector: measures what is left   |   loop filter: smooths, learns the frequency   |   NCO: makes the rotation", fontsize=7.2, color=WHY_C)
    # detector characteristic
    phi = np.radians(np.linspace(-180, 180, 1441))
    z = np.exp(1j * (np.pi / 4 + phi))
    zi, zq = z.real, z.imag
    # all four points rotate together: use the nearest-point decision of the actual constellation point (the point of that quadrant)
    e = np.sign(zi) * zq - np.sign(zq) * zi
    axp.plot(np.degrees(phi), e, color="#33475b", lw=1.6)
    axp.axhline(0, color="#999", lw=0.8)
    for k in (-180, -90, 0, 90, 180): axp.plot([k], [0], "o", ms=9, color="#2a9d4f", zorder=3)
    for k in (-135, -45, 45, 135): axp.plot([k], [0], "x", ms=9, mew=2, color="#c0392b", zorder=3)
    axp.set_xlabel("rotation of the constellation, degrees"); axp.set_ylabel("detector output e (|z| = 1)")
    axp.set_xticks(range(-180, 181, 45)); axp.grid(alpha=0.25)
    axp.set_title("the phase detector: four stable points (green), four unstable ones (red x)", fontsize=10)
    axp.text(0, -1.25, "the loop locks at 0, 90, 180 or 270 degrees with equal ease:\nthat is why the data are sent as phase CHANGES", ha="center", fontsize=8.5, color=WHY_C)
    axp.set_ylim(-1.6, 1.6)
    fig.savefig(os.path.join(OUT, "qpsk_func_costas.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------ 6. GNU Radio blocks side by side with the Verilog
GRC_C, GRC_PY, GRC_UHD, V_LOGIC, V_DSP, V_MEM, V_CTL = "#d6e4ff", "#fff2c2", "#ffe0b3", "#dbe9f7", "#d9f0d3", "#fde9c9", "#f6d9e4"


def pair(ax, y, h, gname, gsub, gcol, mid, vtext, vcol, gx=2, gw=70, vx=96, vw=67):
    """One row: the GNU Radio block (as it is named in Companion) on the left, the Verilog that does the same job on the right."""
    rbox(ax, gx, y, gw, h, gcol, r=1.2); rbox(ax, vx, y, vw, h, vcol, r=1.2)
    ax.text(gx + 1.4, y + h - 1.5, gname, fontsize=8.3, fontweight="bold", va="top", zorder=3)
    ax.text(gx + 1.4, y + h - 5.0 - 3.4 * gname.count("\n"), gsub, fontsize=6.9, va="top", color="#333", family="monospace", zorder=3, linespacing=1.35)
    ax.text((gx + gw + vx) / 2, y + h / 2, mid, fontsize=7.2, ha="center", va="center", color=WHY_C, zorder=4, linespacing=1.25, bbox=dict(fc="white", ec="none", pad=1.5))
    ax.annotate("", xy=(vx, y + h / 2), xytext=(gx + gw, y + h / 2), arrowprops=dict(arrowstyle="<->", color="#8a97a6", lw=1.0), zorder=1)
    ax.text(vx + 1.4, y + h / 2, vtext, fontsize=7.1, va="center", family="monospace", zorder=3, linespacing=1.4)


def grc_header(ax, ytop, left, right):
    ax.text(2 + 35, ytop, left, fontsize=9.5, fontweight="bold", ha="center", color="#27456f")
    ax.text(96 + 33.5, ytop, right, fontsize=9.5, fontweight="bold", ha="center", color="#27456f")


def grc_tx():
    h = 12.0; gap = 2.4; band = 8.0; H = 14 + 8 * (h + gap) + band + 3
    fig, ax = canvas(165, H)
    ax.text(82.5, H - 3, "Transmitter: the blocks of qpsk_b210_tx.grc (GNU Radio) and the Verilog of qpsk_tx.v that does the same job", fontsize=10.5, fontweight="bold", ha="center")
    grc_header(ax, H - 8.5, "GNU Radio Companion block (qpsk_b210_tx.grc)", "FPGA: Verilog (qpsk_tx.v, p501_qpsk.py)")
    rows = [
        ("epy_block  \"PRBS-15 bytes\"", "embedded Python source block\n32767 packed bytes (8 periods), repeating", GRC_PY, "test bits", "lfsr, l1, l2  (15-bit LFSR,\nx^15 + x^14 + 1, two steps per symbol)", V_LOGIC),
        ("digital_constellation_modulator", "= generic_mod, a hierarchical block of the 5 below", GRC_C, "", "", None),
        ("  blocks.packed_to_unpacked_bb", "bits_per_symbol = 2, MSB first", GRC_C, "2 bits\nper symbol", "c = {lfsr[14], l1[14]}   (first bit = MSB)", V_LOGIC),
        ("  digital.map_bb  [0, 1, 3, 2]", "the pre-differential code", GRC_C, "pre-diff map", "p = (c == 2) ? 3 : (c == 3) ? 2 : c", V_LOGIC),
        ("  digital.diff_encoder_bb  (4)", "differential encoder, modulus 4", GRC_C, "differential\nencoder", "dn = d + p;   d <= dn   (2-bit adder: the\nwrap-around of 2 bits is the modulo 4)", V_LOGIC),
        ("  digital.chunks_to_symbols_bc", "constellation_dqpsk points", GRC_C, "symbol\nmapper", "ni = dn[1] ^ dn[0],  nq = dn[1]  -> hist_i, hist_q\n(sign of the last 12 symbols)", V_MEM),
        ("  filter.pfb_arb_resampler_ccf", "sps = 4, RRC 0.35, 32 arms, 11 symbols", GRC_C, "pulse shaping\nx4 samples", "qpsk_rrc_coef ROM: 4 phases x 12 taps (ph);\nsum_i, sum_q = 12 adders / subtractors", V_DSP),
        ("blocks_multiply_const_vxx", "const = tx_amp * tx_on", GRC_C, "level,\non / off", "prod = ysum x amp >> 15;  enable, amp from\nqpsk_regs  (tx_on -> enable, tx_amp -> amp)", V_DSP),
        ("uhd_usrp_sink  (B210)", "3.84 MSPS, 915 MHz, gain = tx_gain, TX/RX", GRC_UHD, "DAC + RF", "dac_i, dac_q -> axi_ad9361 dac_data_i0/q0 ->\nAD9361;  TX attenuation: p501_radio.py", V_LOGIC),
    ]
    y = H - 14 - h
    for g, sub, gc, mid, vt, vc in rows:
        if vc is None:                                             # the label of the hierarchical block, in a band of its own
            ymid = y + h + (gap - band) / 2
            ax.text(2, ymid + 2.4, g, fontsize=8.3, fontweight="bold", va="center"); ax.text(2, ymid - 1.8, sub, fontsize=6.9, va="center", family="monospace", color="#333")
            y -= band; continue
        pair(ax, y, h, g, sub, gc, mid, vt, vc); y -= h + gap
    fig.savefig(os.path.join(OUT, "qpsk_func_vs_grc_tx.png"), dpi=130, bbox_inches="tight"); plt.close(fig)


def rx_rows_figure(rows, title, name):
    h = 12.0; gap = 2.4; H = 14 + len(rows) * (h + gap) + 2
    fig, ax = canvas(165, H)
    ax.text(82.5, H - 3, title, fontsize=10.5, fontweight="bold", ha="center")
    grc_header(ax, H - 8.5, "GNU Radio Companion block (qpsk_b210_rx.grc)", "FPGA: Verilog (qpsk_rx.v, p501_qpsk_rx.py)")
    y = H - 14 - h
    for g, sub, gc, mid, vt, vc in rows:
        pair(ax, y, h, g, sub, gc, mid, vt, vc); y -= h + gap
    fig.savefig(os.path.join(OUT, name), dpi=130, bbox_inches="tight"); plt.close(fig)


def grc_rx():
    a = [
        ("uhd_usrp_source  (B210)", "3.84 MSPS, 915 MHz, gain = rx_gain, RX2", GRC_UHD, "RF + ADC", "adc_i, adc_q, adc_valid -> sram[256] (wr_cnt),\nGray-coded counter to the 100 MHz clock", V_MEM),
        ("analog_agc2_xx", "attack 0.06, decay 1e-3, reference 1, max gain 200", GRC_C, "AGC", "S1: m' = m x g >> 10;  S2: level a;  S3: g += MU x (REF - a) >> 16\n(registers MU, REF, G0)", V_DSP),
        ("blocks_complex_to_float + analog_rail_ff x2\n+ blocks_float_to_complex", "the limiter: each component clipped to +-1.5", GRC_C, "keep the\nloops safe", "clip16(), clip24() in S0, S1: the fixed-point\nsaturation does it, no extra block", V_LOGIC),
        ("digital_fll_band_edge_cc", "sps 4, roll-off 0.35, 55 taps, w = 2 pi / N", GRC_C, "coarse\nfrequency", "NONE in the FPGA. The Costas loop does the pull-in:\nregister W0 + rx.acquire() (hints 0, +-6, +-12 kHz)", V_CTL),
        ("digital_pfb_clock_sync_xxx  (ccf)", "sps 4, loop_bw 2 pi / N, taps = rrc_taps,\nfilter_size 32, max_dev 0.05", GRC_C, "matched filter\n+ timing loop", "qpsk_rx_rom: 16 arms x 44 taps (cm, cd), MAC in ST_MAC;\nS2: e_t;  S3: rate (TB);  S4: p (TA);  MAXR = max_dev\n(only the arm chosen by p is computed)", V_DSP),
        ("digital_costas_loop_cc", "order 4, w = 2 pi / N", GRC_C, "carrier\nrecovery", "S5: z = m' x exp(-j theta)  (qpsk_rx_trig table)\nS6: e_c;  S7: omega += CB x e_c;  S8: theta += omega + CA x e_c", V_DSP),
    ]
    rx_rows_figure(a, "Receiver, front half: from the antenna to the symbols", "qpsk_func_vs_grc_rx1.png")
    b = [
        ("digital_constellation_decoder_cb", "constellation_dqpsk: nearest of the 4 points", GRC_C, "slicer", "s_i = zi > 0;  s_q = zq > 0;  pt = point 0..3   (S6)", V_LOGIC),
        ("digital_diff_decoder_bb  (4)", "modulus 4", GRC_C, "differential\ndecode", "dd = pt - prev      (2-bit subtraction)", V_LOGIC),
        ("digital_map_bb  [0, 1, 3, 2]", "the inverse of the pre-differential code (the same map)", GRC_C, "inverse map", "cc = (dd == 2) ? 3 : (dd == 3) ? 2 : dd", V_LOGIC),
        ("blocks_unpack_k_bits_bb  (2)", "2 bits per byte, MSB first", GRC_C, "the bits", "bits2 = {b0, b1};  b0 = cc[1], b1 = cc[0]", V_LOGIC),
        ("epy_block  \"PRBS-15 BER\"\n+ blocks_keep_one_in_n + qtgui_number_sink", "a[n] = a[n-15] ^ a[n-14]; 3 mismatches per error;\nflags a stuck stream (0.5)", GRC_PY, "bit error\ncounter", "prbs_sr, pred0, pred1;  n_bits, n_mism  (3 per error)\nBER = mism / 3 / bits  in P501QpskRx.stats()", V_LOGIC),
        ("qtgui_const_sink_x  /  qtgui_freq_sink_x", "constellation after the Costas loop; spectrum", "#e6e6e6", "viewers", "cap_mem[1024] = {zq, zi}, read by rx.capture();\nthe notebook draws the picture (the spectrum: tutorial 1)", V_MEM),
    ]
    rx_rows_figure(b, "Receiver, back half: from the symbols to the bit error rate", "qpsk_func_vs_grc_rx2.png")


if __name__ == "__main__":
    link(); transmitter(); receiver(); timing(); costas(); grc_tx(); grc_rx(); print("wrote the functional diagrams to", os.path.normpath(OUT))
