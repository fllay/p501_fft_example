#!/usr/bin/env python3
"""Figures of TUTORIAL_OFDM.md (tutorial/img/ofdm_t_*.png) for the frame and receiver as implemented (Schmidl-and-Cox, 47 equal symbols).
The figures with real data use a recording of the P501's ADC while the B210 transmitted (qam16/sim/adc_ofdm850b.npy, made with qam16/p501_adc_capture.py; 850 MHz, B210 gain 79 dB); the others come from the model.
    python3 make_figures_ofdm_tutorial.py [recording.npy]"""
import sys, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ofdm_model as Fm
IMG = os.path.join(HERE, "..", "img")
REC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "qam16", "sim", "adc_ofdm850b.npy")
FS, N, CP, SYM = Fm.FS, Fm.N, Fm.CP, Fm.SYM
C = dict(sc="#e07020", tr="#2e8b57", data="#2b6cb0", data2="#4299e1", pil="#c53030", grey="#a0aec0", fpga="#bee3f8", gnu="#c6f6d5", py="#feebc8", old="#e2e8f0")

def box(ax, x, y, w, h, text, fc, fs=8.5, ec="k"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1)); ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs)
def arrow(ax, x0, y0, x1, y1, color="k", ls="-"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.2, ls=ls))

def real_frame():
    """one frame of the recording: the idle slot is the 80 samples of least energy, the S&C symbol starts right after it; (x, M, S, window start of the plateau, s0, coarse carrier in Hz)"""
    x = np.load(REC).astype(complex); x -= x.mean(); x /= 2048
    M, S = Fm.timing_metric(x, 32, 32); e = np.convolve(np.abs(x[:60000]) ** 2, np.ones(80) / 80, "valid"); g = int(np.argmin(e[2 * 3840:3 * 3840])) + 2 * 3840; s0 = g + 80
    pl = np.arange(s0 + 1, s0 + 16)                                             # the windows inside the prefix of the S&C symbol (the plateau is [s0, s0 + 16])
    fc = np.angle(np.sum(S[pl])) / (2 * np.pi * 32 / FS)
    return x, M, S, s0, s0, fc

# ---------------------------------------------------------------- 1. method
def fig_method():
    fig, ax = plt.subplots(figsize=(11, 3.4)); ax.set_xlim(0, 11); ax.set_ylim(0, 3.4); ax.axis("off")
    box(ax, 0.1, 1.9, 1.9, 1.2, "float model\nofdm_model.py\nstudies, figures", C["old"]); box(ax, 2.5, 1.9, 1.9, 1.2, "integer model\nofdm_fixed.py\nevery register\nand shift", C["old"])
    box(ax, 4.9, 1.9, 1.9, 1.2, "RTL (xsim)\nrtl/ofdm_*.v\nbit-exact against\nthe integer model", C["fpga"]); box(ax, 7.3, 1.9, 1.7, 1.2, "overlay\np501_ofdm_rx_sc\ndriver, notebook", C["fpga"]); box(ax, 9.3, 1.9, 1.6, 1.2, "board tests\nloopback, air,\nB210", C["fpga"])
    for a, b in ((2.0, 2.5), (4.4, 4.9), (6.8, 7.3), (9.0, 9.3)): arrow(ax, a, 2.5, b, 2.5)
    box(ax, 0.1, 0.2, 4.3, 1.1, "GNU Radio receiver ofdm_b210_frame_rx.grc: the same algorithm in floating point,\nblock by block, with a plot after every stage (this is the lab bench)", C["gnu"], 8.5)
    arrow(ax, 1.0, 1.9, 1.0, 1.3, "#2e8b57"); ax.text(1.1, 1.55, "same steps", fontsize=8, color="#2e8b57")
    box(ax, 5.2, 0.2, 5.7, 1.1, "B210 transmitter: ofdm_frame_tx.py or ofdm_b210_frame_tx.grc (the frame of the model, repeated 1000 times per second)", C["gnu"], 8.5)
    arrow(ax, 8.1, 1.3, 8.1, 1.9, "#2e8b57", "--"); ax.set_title("The method: every stage reproduces the previous one, then the board", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(IMG, "ofdm_t_method.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 2. frame
def fig_frame():
    fig = plt.figure(figsize=(12, 7.4)); ax = fig.add_axes([0.04, 0.78, 0.92, 0.17]); ax.set_xlim(0, 3840); ax.set_ylim(0, 1); ax.axis("off")
    cols = [C["sc"], C["tr"], C["tr"]] + [C["data"] if i % 2 == 0 else C["data2"] for i in range(44)]
    for i, c in enumerate(cols): ax.add_patch(plt.Rectangle((i * 80, 0.1), 80, 0.8, fc=c, ec="k", lw=0.6))
    ax.add_patch(plt.Rectangle((3760, 0.1), 80, 0.8, fc="white", ec="k", lw=0.6, hatch="//"))
    for x, t in ((40, "S&C"), (120, "T1"), (200, "T2")): ax.text(x, 0.5, t, ha="center", va="center", fontsize=7.5, color="white", rotation=90)
    ax.text(2000, 0.5, "44 data symbols of 80 samples: 24 x 16-QAM + 4 QPSK pilots = 4224 bits", ha="center", va="center", fontsize=9, color="white", bbox=dict(fc=C["data"], ec="none")); ax.text(3800, -0.15, "idle 80", ha="center", fontsize=8); ax.text(0, -0.15, "0", fontsize=8); ax.text(3700, -0.15, "3760", ha="right", fontsize=8)
    ax.set_title("One frame = 3840 samples = 1 ms at 3.84 MS/s: 47 symbols of 80 samples (all alike) and an idle slot of 80", fontsize=11, pad=14)
    ax2 = fig.add_axes([0.06, 0.50, 0.88, 0.17]); ax2.set_xlim(0, 80); ax2.set_ylim(-0.3, 1.3); ax2.axis("off")
    ax2.add_patch(plt.Rectangle((0, 0.2), 16, 0.6, fc="#fbd38d", ec="k")); ax2.add_patch(plt.Rectangle((16, 0.2), 64, 0.6, fc="#bee3f8", ec="k"))
    ax2.text(8, 0.5, "CP 16", ha="center", va="center", fontsize=9); ax2.text(48, 0.5, "useful part: 64 samples = 1 / 60 kHz = 16.7 us", ha="center", va="center", fontsize=9)
    ax2.plot([0, 16], [0.9, 0.9], color="#e07020", lw=3); ax2.plot([64, 80], [0.1, 0.1], color="#e07020", lw=3); ax2.annotate("", xy=(8, 0.85), xytext=(72, 0.15), arrowprops=dict(arrowstyle="-|>", color="#e07020", ls="--", connectionstyle="arc3,rad=-0.25"))
    ax2.text(40, -0.15, "the prefix is a copy of the last 16 samples of the useful part", ha="center", fontsize=8.5, color="#e07020")
    ax2.annotate("", xy=(10, 0.8), xytext=(10, 1.15), arrowprops=dict(arrowstyle="-|>", color="k")); ax2.text(12, 1.2, "the FFT window starts here, 6 samples before the useful part (BACK): a timing error of up to +-6 samples stays inside the prefix", fontsize=8.5, va="center")
    ax2.set_title("One symbol", fontsize=10, loc="left")
    ax3 = fig.add_axes([0.06, 0.07, 0.88, 0.31]); ks = np.arange(-32, 32)
    for k in ks:
        if k in Fm.PIL: c, h = C["pil"], 1
        elif k in Fm.DATA: c, h = C["data"], 1
        elif k == 0: c, h = C["grey"], 0.25
        else: c, h = "white", 0.12
        ax3.bar(k, h, 0.85, color=c, ec="k", lw=0.5)
    for k in Fm.SC_K: ax3.plot(k, 1.12, "v", color=C["sc"], ms=7)
    ax3.set_xlim(-33, 32); ax3.set_ylim(0, 1.35); ax3.set_yticks([]); ax3.set_xlabel("subcarrier k (60 kHz each; bin = k mod 64)")
    ax3.set_title("Subcarriers: 24 data (blue), 4 pilots (red), DC unused (grey), 28 used = 1.68 MHz. T1 and T2 load all 28 with a known QPSK value; the S&C symbol only the even ones (orange)", fontsize=9.5)
    fig.savefig(os.path.join(IMG, "ofdm_t_frame.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 3. IFFT and the cyclic prefix
def fig_symbol():
    rng = np.random.default_rng(3); d = (rng.integers(0, 4, 24) * 2 - 3 + 1j * (rng.integers(0, 4, 24) * 2 - 3)) / np.sqrt(10)
    X = np.zeros(N, complex); X[Fm.bin_of(Fm.DATA)] = d; X[Fm.bin_of(Fm.PIL)] = Fm.PIL_V; x = np.fft.ifft(X) * np.sqrt(N); xs = np.concatenate([x[-CP:], x])
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.4))
    ax = axs[0]; ax.stem(np.arange(-32, 32), np.abs(np.fft.fftshift(X)), basefmt=" "); ax.set_title("frequency: the values X[k] of the 28 used subcarriers"); ax.set_xlabel("subcarrier k"); ax.set_ylabel("|X[k]|"); ax.grid(alpha=.3)
    ax = axs[1]; ax.plot(np.arange(80), np.abs(xs), color=C["data"]); ax.axvspan(0, 16, color="#fbd38d", alpha=.7); ax.set_title("time: |x[n]| = |sqrt(64) IFFT(X)| with the prefix"); ax.set_xlabel("sample n of the symbol"); ax.grid(alpha=.3); ax.text(8, np.abs(xs).max() * 0.92, "CP", ha="center")
    ax = axs[2]; mag = np.abs(xs) ** 2 / np.mean(np.abs(x) ** 2); r = np.sort(mag)[::-1]
    big = np.concatenate([np.abs(Fm.tx_frame(preamble="scu")[0][:3760]) ** 2]); big = big / big.mean(); ax.hist(10 * np.log10(big + 1e-9), bins=80, color=C["data"], alpha=.8, density=True)
    ax.set_title("OFDM sums 28 carriers: the power of a sample is spread (mean 0 dB)\npeaks 10 dB above the mean: the transmitter needs headroom"); ax.set_xlabel("sample power (dB relative to the mean)"); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(IMG, "ofdm_t_symbol.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 4. Schmidl and Cox on a real frame
def fig_sc():
    x, M, S, n0, s0, fc = real_frame(); a = s0 - 400; b = s0 + 3840 + 400
    fig, axs = plt.subplots(2, 2, figsize=(13, 6.6))
    ax = axs[0, 0]; t = np.arange(a, b); ax.plot((t - s0) / FS * 1e6, np.abs(x[a:b]), lw=.5, color=C["data"]); ax.set_title("received |x| (P501 ADC, B210 at 850 MHz): frame and idle slot", fontsize=10); ax.set_xlabel("time from the start of the S&C symbol (us)"); ax.set_ylabel("|x| (full scale 1)"); ax.grid(alpha=.3)
    ax = axs[0, 1]; u = np.arange(s0 + CP, s0 + CP + 64); rot = np.exp(-1j * 2 * np.pi * fc / FS * 32)
    ax.plot(np.arange(32), x[u[:32]].real, "o-", ms=3, label="first half"); ax.plot(np.arange(32), (x[u[32:]] * rot).real, "s--", ms=3, label="second half, turned back by the carrier offset")
    ax.set_title("S&C symbol (Re x): two equal halves of 32 samples", fontsize=10); ax.set_xlabel("sample in the half"); ax.legend(fontsize=8); ax.grid(alpha=.3)
    ax = axs[1, 0]; w0, w1 = s0 - 200, s0 + 200; ax.plot(np.arange(w0, w1) - s0, M[w0:w1], color="#d62728"); ax.axhline(0.65, color="k", ls="--", lw=.8); ax.text(-190, 0.67, "threshold 0.65", fontsize=8)
    ax.axvspan(0, 16, color="#fbd38d", alpha=.5); ax.set_title("M = |S|^2 / E^2: the plateau of 17 windows at the symbol start;\nthe spike before it is the idle slot (DC), see the guard", fontsize=9.5); ax.set_xlabel("start of the 64-sample window relative to the symbol start (samples)"); ax.set_ylim(-0.05, 1.1); ax.grid(alpha=.3)
    ax = axs[1, 1]; f = np.angle(S[w0:w1]) / 32 * FS / (2 * np.pi) / 1e3; ax.plot(np.arange(w0, w1) - s0, f, ".", ms=3)
    ax.axhline(fc / 1e3, color="k", ls="--", lw=.8); ax.text(-190, fc / 1e3 + 4, "mean on the plateau: %.1f kHz" % (fc / 1e3), fontsize=8)
    ax.set_title("arg S / (2 pi 32 / fs) = the carrier offset (kHz)", fontsize=10); ax.set_xlabel("start of the window relative to the symbol start (samples)"); ax.set_ylim(-60, 60); ax.set_ylabel("kHz"); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(IMG, "ofdm_t_sc.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 5. the guard: DC in the idle slot
def fig_guard():
    x, d = Fm.tx_frame(preamble="scu"); y = np.tile(x, 4); y = y / np.sqrt(np.mean(np.abs(y[:3760]) ** 2)) * 0.1
    rng = np.random.default_rng(2); y = y + 0.02 * (1 + 1j) / np.sqrt(2) * 1.0 + 1e-4 * (rng.standard_normal(len(y)) + 1j * rng.standard_normal(len(y)))
    c = y[32:] * np.conj(y[:-32]); e = np.abs(y[32:]) ** 2
    cs = lambda v: np.concatenate([[0], np.cumsum(v)]); Sc, Ec = cs(c), cs(e); S = Sc[32:] - Sc[:-32]; Eb = Ec[32:] - Ec[:-32]
    Ea = np.concatenate([np.zeros(32), Eb[:-32]]); P = np.mean(np.abs(y) ** 2)
    M1 = np.abs(S) ** 2 / (Eb ** 2 + 1e-18); M2 = np.abs(S) ** 2 / (Ea * Eb + 1e-18); M3 = np.abs(S) ** 2 / (Ea * Eb + (0.1 * 32 * P) ** 2 + 1e-18)
    a, b = 3840 + 3200, 3840 * 2 + 400; t = np.arange(a, b) - 3840 * 2
    fig, axs = plt.subplots(1, 4, figsize=(15, 3.4), sharey=False)
    axs[0].plot(t, np.abs(y[a + 63:b + 63]), lw=.6, color=C["data"]); axs[0].set_title("|x|: DC 0.02 and almost no noise in the idle slot\n(the B210's LO leakage)"); axs[0].axvspan(-80, 0, color="#fbd38d", alpha=.5); axs[0].text(-78, 0.3, "idle", fontsize=8)
    for ax, M, ttl in zip(axs[1:], (M1, M2, M3), ("|S|^2 / Eb^2 (the FPGA before the guard)", "|S|^2 / (Ea Eb)", "|S|^2 / (Ea Eb + guard)")):
        ax.plot(t, np.clip(M[a:b], 0, 3), color="#d62728"); ax.axhline(0.65, color="k", ls="--", lw=.8); ax.set_title(ttl); ax.set_ylim(-0.05, 3.1 if M is M1 else 1.1)
    axs[1].text(-620, 2.5, "the idle slot: M > 1", fontsize=8); axs[2].text(-620, 0.8, "two spikes: the idle slot\nlooks periodic", fontsize=8); axs[3].text(-620, 0.8, "one spike: the S&C symbol", fontsize=8)
    for ax in axs: ax.set_xlabel("samples from the frame boundary"); ax.grid(alpha=.3)
    fig.suptitle("Why the detector has a guard (simulated: the same frame with a DC offset and a very clean idle slot)", y=1.0); fig.tight_layout(); fig.savefig(os.path.join(IMG, "ofdm_t_guard.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 6. carrier estimate
def fig_cfo():
    rng = np.random.default_rng(4); x, d = Fm.tx_frame(preamble="scu")
    snrs = [8, 12, 16, 20, 24, 28]; sc_err, tot_err = [], []
    for s in snrs:
        ec, et = [], []
        for _ in range(60):
            y = Fm.channel(x, s, cfo_hz=9000.0, tau=3.4, ppm=10.0, rng=rng, lead=300, trail=300); r = Fm.receive(y, sync="scu", return_all=True)
            if r is not None: ec.append(r["f_c"] - 9000.0); et.append(r["f"] - 9000.0)
        sc_err.append(np.median(np.abs(ec))); tot_err.append(np.median(np.abs(et)))
    offs = np.arange(-90e3, 90.1e3, 10e3); est = []
    for o in offs:
        y = Fm.channel(x, 25, cfo_hz=o, tau=3.4, ppm=10.0, rng=rng, lead=300, trail=300); M, S = Fm.timing_metric(y, 32, 32); r = Fm.detect_sc(y, 0.5); est.append(np.nan if r is None else r[1])
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    axs[0].semilogy(snrs, sc_err, "o-", label="coarse (S&C, one symbol, 32 products)"); axs[0].semilogy(snrs, tot_err, "s-", label="coarse + fine (T1, T2 80 samples apart)")
    axs[0].set_xlabel("Es/N0 per subcarrier (dB)"); axs[0].set_ylabel("median |error| of the carrier estimate (Hz)"); axs[0].grid(alpha=.3, which="both"); axs[0].legend(); axs[0].set_title("the carrier offset (9 kHz) is measured twice")
    axs[1].plot(offs / 1e3, np.array(est) / 1e3, "o-"); axs[1].plot([-90, 90], [-90, 90], "k--", lw=.8); axs[1].axvspan(-60, 60, color="#c6f6d5", alpha=.4); axs[1].set_xlabel("true carrier offset (kHz)"); axs[1].set_ylabel("coarse estimate (kHz)")
    axs[1].set_title("the S&C estimate wraps beyond +-60 kHz", fontsize=10); axs[1].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(IMG, "ofdm_t_cfo.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 7. channel, equaliser and pilots on a real frame
def fig_equalizer():
    x, M, S, n0, s0, fc = real_frame(); a = s0 - 300; seg = x[a:a + 3840 + 600]
    r = Fm.receive(seg, sync="scu", track="complex+slope", gsmooth=5, return_all=True, genie=(300, fc)); s0r, f = r["s0"], r["f"]
    n = np.arange(len(seg)); xr = seg * np.exp(-2j * np.pi * f / FS * (n - s0r)); base = s0r + 80 + 160; kb = Fm.bin_of(Fm.DATA)
    Y = np.array([np.fft.fft(xr[base + l * SYM + CP - Fm.BACK:base + l * SYM + CP - Fm.BACK + N])[kb] / np.sqrt(N) for l in range(44)])
    H = r["H"]; Hd = dict(zip(Fm.USED, H)); Hdat = np.array([Hd[k] for k in Fm.DATA]); Z0 = Y / Hdat; Z1 = r["Z"]
    fig = plt.figure(figsize=(13, 7)); gs = fig.add_gridspec(2, 3)
    ax = fig.add_subplot(gs[0, 0]); ax.plot(Fm.USED, 20 * np.log10(np.abs(H)), "o-", ms=3); ax.set_title("|H[k]| (dB) from T1 and T2: flat"); ax.set_xlabel("subcarrier k"); ax.grid(alpha=.3)
    ax = fig.add_subplot(gs[0, 1]); ax.plot(Fm.USED, np.unwrap(np.angle(H)), "o-", ms=3); ax.set_title("arg H[k]: a straight line = a delay\n(the FFT window starts 6 samples early)"); ax.set_xlabel("subcarrier k"); ax.set_ylabel("rad"); ax.grid(alpha=.3)
    ax = fig.add_subplot(gs[0, 2]); ph = np.angle(r["gains"]); ax.plot(np.arange(44), ph, "o-", ms=3); ax.plot(np.arange(44), np.abs(r["gains"]), "s-", ms=3, color="#d62728"); ax.set_title("pilots: arg g (rad, blue), |g| (red) per symbol", fontsize=10); ax.set_xlabel("data symbol l"); ax.grid(alpha=.3)
    lim = 1.6
    for i, (Z, ttl) in enumerate(((Y / np.sqrt(np.mean(np.abs(Y) ** 2)), "after the FFT (unit rms): rotated and scaled by the channel"), (Z0, "divided by H[k]: the common phase error of every symbol is left"), (Z1, "pilot gain and slope removed: the 16 clusters"))):
        ax = fig.add_subplot(gs[1, i]); ax.plot(Z.real.ravel(), Z.imag.ravel(), ".", ms=2, alpha=.5, color=C["data"])
        lv = np.array([-3, -1, 1, 3]) / np.sqrt(10)
        for p in lv:
            for q in lv: ax.plot(p, q, "+", color="#d62728", ms=7)
        ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_aspect("equal"); ax.set_title(ttl, fontsize=9); ax.grid(alpha=.3)
    evm = 10 * np.log10(np.mean((np.abs(Z1 - Fm.hard(Z1))) ** 2) / np.mean(np.abs(Fm.hard(Z1)) ** 2)); fig.suptitle("A frame of the B210 recording (float model on the P501's ADC samples): channel, equaliser and pilots; EVM %.1f dB" % evm, y=1.0)
    fig.tight_layout(); fig.savefig(os.path.join(IMG, "ofdm_t_equalizer.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 8. the receiver in the FPGA, as built
def fig_block_rx():
    fig, ax = plt.subplots(figsize=(13, 5.2)); ax.set_xlim(0, 13); ax.set_ylim(0, 5.2); ax.axis("off")
    box(ax, 0.1, 3.6, 1.7, 1.2, "ADC 3.84 MS/s\nsample RAMs (two\n1024-word, clock\ncrossing)", C["old"], 8)
    box(ax, 2.2, 3.6, 2.1, 1.2, "ofdm_detect.v\nS&C: 32 products,\nplateau of M,\nCORDIC: coarse w,\ngain G", C["fpga"], 8)
    box(ax, 4.7, 3.6, 2.0, 1.2, "controller (ofdm_rx.v)\nwait for T2, fine w\nfrom T1 and T2,\nT1/T2 check,\nwindow addresses", C["fpga"], 8)
    box(ax, 7.1, 3.6, 1.8, 1.2, "ofdm_derot.v\nNCO, gain,\nderotation\n(latency 7)", C["fpga"], 8)
    box(ax, 9.3, 3.6, 1.7, 1.2, "ofdm_fft.v\n64 points,\nradix 2,\n768 clocks", C["fpga"], 8)
    box(ax, 11.3, 3.6, 1.6, 1.2, "ofdm_chan.v\nH from T1 + T2,\nnoise, weights\nW = conj(H) R/|H|^2", C["fpga"], 8)
    box(ax, 1.4, 1.2, 3.2, 1.5, "ofdm_data.v (per data symbol, 175 + 333 clocks)\nequaliser W Y, pilot gain g and slope\n(CORDIC), 5-symbol average, correction", C["fpga"], 8)
    box(ax, 5.0, 1.2, 2.6, 1.5, "slicer and checker\nGray bits, PRBS-15,\nsymbol and bit errors,\nEVM sums", C["fpga"], 8)
    box(ax, 8.0, 1.2, 2.5, 1.5, "capture RAM (1024 soft\nsymbols), H copy,\ncounters", C["old"], 8); box(ax, 10.9, 1.2, 2.0, 1.5, "AXI-Lite\nregisters\n(driver, notebook)", C["old"], 8)
    for a, b in ((1.8, 2.2), (4.3, 4.7), (6.7, 7.1), (8.9, 9.3), (11.0, 11.3)): arrow(ax, a, 4.2, b, 4.2)
    arrow(ax, 12.1, 3.6, 4.0, 2.7); arrow(ax, 10.15, 3.6, 3.2, 2.7); arrow(ax, 4.6, 1.95, 5.0, 1.95); arrow(ax, 7.6, 1.95, 8.0, 1.95); arrow(ax, 10.5, 1.95, 10.9, 1.95)
    ax.text(0.2, 0.5, "A frame is found while the previous one is still being finished: the detector re-arms as soon as its last window has been read. Every block is bit-exact against ofdm_fixed.py.", fontsize=9)
    ax.set_title("The receiver in the FPGA (blue: new for OFDM; grey: as in the earlier overlays)", fontsize=11); fig.tight_layout(); fig.savefig(os.path.join(IMG, "ofdm_t_block_rx.png"), dpi=130); plt.close(fig)

# ---------------------------------------------------------------- 9. the receiver in GNU Radio
def fig_grc():
    fig, ax = plt.subplots(figsize=(14, 5.6)); ax.set_xlim(0, 14); ax.set_ylim(0, 5.6); ax.axis("off")
    row = [("B210\nsource", C["gnu"], "1"), ("DC removal\n(one-pole IIR,\nsubtract)", C["gnu"], "1"), ("S&C metric\ndelay, conj, mult,\nmoving averages,\nguard, divide", C["gnu"], "2"), ("S&C frame\ndetector", C["py"], "2"), ("coarse CFO\ncorrection", C["py"], "3"), ("fine CFO and\nT1/T2 check", C["py"], "3")]
    for i, (t, c, tab) in enumerate(row):
        box(ax, 0.2 + i * 2.3, 3.8, 2.0, 1.2, t, c, 8); ax.text(1.2 + i * 2.3, 5.2, "tab " + tab, ha="center", fontsize=8, color="#555")
        if i: arrow(ax, 0.2 + i * 2.3 - 0.3, 4.4, 0.2 + i * 2.3, 4.4)
    row2 = [("keep 64 of 80\nstream to vector\nFFT 64, x 1/8", C["gnu"], "4"), ("keep the 29 used\nbins\nstream to vector", C["gnu"], "4"), ("channel\nestimator", C["py"], "5"), ("equalizer and\npilot tracking", C["py"], "6"), ("16-QAM\nslicer", C["py"], "6"), ("symbol error\ncounter", C["py"], "6")]
    for i, (t, c, tab) in enumerate(row2):
        box(ax, 0.2 + i * 2.3, 1.5, 2.0, 1.2, t, c, 8); ax.text(1.2 + i * 2.3, 2.9, "tab " + tab, ha="center", fontsize=8, color="#555")
        if i: arrow(ax, 0.2 + i * 2.3 - 0.3, 2.1, 0.2 + i * 2.3, 2.1)
    arrow(ax, 12.2, 3.8, 1.2, 2.75, "#888", "--")
    box(ax, 0.2, 0.1, 2.3, 0.6, "stock GNU Radio block", C["gnu"], 8); box(ax, 2.7, 0.1, 2.3, 0.6, "embedded Python block", C["py"], 8)
    ax.text(5.3, 0.4, "Every stage has its own plot tab. Behind the detector the stream has exactly 3760 samples\n(47 symbols of 80) per frame, so the blocks that follow stay in step without tags.", fontsize=8.5, va="center")
    ax.set_title("The receiver in GNU Radio Companion: ofdm_b210_frame_rx.grc", fontsize=11); fig.tight_layout(); fig.savefig(os.path.join(IMG, "ofdm_t_grc_chain.png"), dpi=130); plt.close(fig)

if __name__ == "__main__":
    for f in (fig_method, fig_frame, fig_symbol, fig_guard, fig_block_rx, fig_grc, fig_sc, fig_cfo, fig_equalizer):
        try: f(); print("ok", f.__name__)
        except Exception as e:
            import traceback; print("FAILED", f.__name__, repr(e)); traceback.print_exc()
