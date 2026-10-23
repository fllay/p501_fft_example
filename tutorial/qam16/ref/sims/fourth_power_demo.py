import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RS = 960e3
DF = 9.7e3
rng = np.random.default_rng(1)


def dqpsk_symbols(n):
    chunks = rng.integers(0, 4, n)
    pre = np.array([0, 1, 3, 2])[chunks]
    d = np.cumsum(pre) % 4
    pts = np.array([1 + 1j, -1 + 1j, -1 - 1j, 1 - 1j]) / np.sqrt(2)
    return pts[d]


def received(n, snr_db, df=DF):
    s = dqpsk_symbols(n)
    k = np.arange(n)
    rot = np.exp(1j * (2 * np.pi * df / RS * k + 0.7))      # offset + unknown constant phase
    n0 = 10 ** (-snr_db / 10)                                # Es = 1
    noise = np.sqrt(n0 / 2) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    return s * rot + noise


def estimate(m):
    d = m[1:] * np.conj(m[:-1])
    D = d ** 4
    acc = D.sum()
    f = np.angle(acc) / (8 * np.pi) * RS
    return f, np.abs(acc) / np.abs(D).sum()


# ---------- figure 1: constellations ----------
snrs = [30, 20, 12, 6]
fig, ax = plt.subplots(3, 4, figsize=(13, 9.5))
for c, snr in enumerate(snrs):
    m = received(1500, snr)
    d = m[1:] * np.conj(m[:-1])
    D = d ** 4
    f, q = estimate(m[:512])
    for r, (z, lim, title) in enumerate([
        (m, 1.8, "m_n  (matched-filter output)"),
        (d, 2.0, "d_n = m_n · conj(m_n-1)"),
        (D, 3.0, "d_n^4"),
    ]):
        a = ax[r, c]
        a.scatter(z.real, z.imag, s=4, alpha=0.5)
        a.set_xlim(-lim, lim); a.set_ylim(-lim, lim); a.set_aspect("equal")
        a.axhline(0, color="gray", lw=0.5); a.axvline(0, color="gray", lw=0.5)
        if r == 0:
            a.set_title("Es/N0 = %d dB" % snr, fontsize=11)
        if c == 0:
            a.set_ylabel(title, fontsize=10)
    ang = 4 * 2 * np.pi * DF / RS
    ax[2, c].plot([0, 2.5 * np.cos(ang)], [0, 2.5 * np.sin(ang)], "r-", lw=1.2)
    ax[2, c].text(-2.8, 2.5, "N=512 est: %.1f kHz\nquality %.2f" % (f / 1e3, q), fontsize=8, va="top")
fig.suptitle("DQPSK, 9.7 kHz offset: red line = true angle of d^4 (4·2π·Δf·T = %.3f rad)\n"
             "points beyond the axes are clipped" % (4 * 2 * np.pi * DF / RS), fontsize=11)
fig.tight_layout()
fig.savefig("/tmp/claude-0/-home-claude/164b9041-6620-56fd-b7f7-17496c21d4ff/scratchpad/fourth_power_constellations.png", dpi=110)

# ---------- figure 2: accuracy vs SNR ----------
snr_axis = np.arange(0, 31, 2)
fig2, a2 = plt.subplots(1, 2, figsize=(11, 4))
for N in (128, 512, 2048):
    rms, outl = [], []
    for snr in snr_axis:
        err = []
        for _ in range(150):
            f, _ = estimate(received(N, snr))
            err.append(f - DF)
        err = np.array(err)
        outl.append(np.mean(np.abs(err) > 5e3) * 100)
        good = err[np.abs(err) <= 5e3]
        rms.append(np.sqrt(np.mean(good ** 2)) if len(good) > 5 else np.nan)
    a2[0].semilogy(snr_axis, rms, "o-", label="N=%d" % N)
    a2[1].plot(snr_axis, outl, "o-", label="N=%d" % N)
a2[0].set_xlabel("Es/N0 (dB)"); a2[0].set_ylabel("rms error, outliers excluded (Hz)"); a2[0].grid(True, which="both", alpha=0.3); a2[0].legend()
a2[1].set_xlabel("Es/N0 (dB)"); a2[1].set_ylabel("outliers: |error| > 5 kHz (%)"); a2[1].grid(True, alpha=0.3); a2[1].legend()
fig2.suptitle("4th-power estimator accuracy vs SNR (ideal timing, 150 trials per point)")
fig2.tight_layout()
fig2.savefig("/tmp/claude-0/-home-claude/164b9041-6620-56fd-b7f7-17496c21d4ff/scratchpad/fourth_power_accuracy.png", dpi=110)

# a few numbers to read back
for snr in (30, 20, 12, 6, 0):
    e = np.array([estimate(received(512, snr))[0] - DF for _ in range(300)])
    print("SNR %2d dB N=512: rms %.0f Hz, outliers %.1f %%" % (snr, np.sqrt(np.mean(e[np.abs(e) < 5e3] ** 2)) if np.any(np.abs(e) < 5e3) else float("nan"), 100 * np.mean(np.abs(e) > 5e3)))
