import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RS, SPS, BETA, SPAN = 960e3, 4, 0.35, 11
FS = RS * SPS
DF = 9.7e3
NSYM = 1024
rng = np.random.default_rng(7)


def rrc(beta=BETA, sps=SPS, span=SPAN):
    n = span * sps + 1
    t = (np.arange(n) - (n - 1) / 2) / sps
    h = np.zeros(n)
    for i, x in enumerate(t):
        if abs(x) < 1e-12:
            h[i] = 1 + beta * (4 / np.pi - 1)
        elif abs(abs(x) - 1 / (4 * beta)) < 1e-9:
            h[i] = beta / np.sqrt(2) * ((1 + 2 / np.pi) * np.sin(np.pi / (4 * beta)) + (1 - 2 / np.pi) * np.cos(np.pi / (4 * beta)))
        else:
            h[i] = (np.sin(np.pi * x * (1 - beta)) + 4 * beta * x * np.cos(np.pi * x * (1 + beta))) / (np.pi * x * (1 - (4 * beta * x) ** 2))
    return h / np.sqrt(np.sum(h ** 2))          # unit energy: Es = 1, matched-filter output = symbol amplitude


H = rrc()
PTS = np.array([1 + 1j, -1 + 1j, -1 - 1j, 1 - 1j]) / np.sqrt(2)


def make(snr_db):
    nsym = NSYM + SPAN + 4
    chunks = rng.integers(0, 4, nsym)
    d = np.cumsum(np.array([0, 1, 3, 2])[chunks]) % 4
    s = PTS[d]
    up = np.zeros(nsym * SPS, complex); up[::SPS] = s
    tx = np.convolve(up, H)
    n = np.arange(len(tx))
    rx = tx * np.exp(1j * (2 * np.pi * DF / FS * n + 1.1))
    sig2 = 10 ** (-snr_db / 10)                  # N0 per complex sample, Es = 1
    rx = rx + np.sqrt(sig2 / 2) * (rng.standard_normal(len(rx)) + 1j * rng.standard_normal(len(rx)))
    mf = np.convolve(rx, H)                      # matched filter, all 4 samples per symbol
    # symbol instants: group delay of tx + mf = SPAN*SPS samples
    off = SPAN * SPS
    return rx[off:off + NSYM * SPS], mf[off:off + NSYM * SPS]


def tone_peak(z, fs_eff, pad=4, search=None):
    """frequency (Hz) of the strongest tone in z, FFT with zero padding and parabolic interpolation"""
    nf = pad * len(z)
    S = np.abs(np.fft.fft(z, nf))
    fr = np.fft.fftfreq(nf, 1 / fs_eff)
    if search is not None:
        S = np.where(np.abs(fr) <= search, S, 0)
    k = int(np.argmax(S))
    a, b, c = np.log(S[(k - 1) % nf] + 1e-30), np.log(S[k] + 1e-30), np.log(S[(k + 1) % nf] + 1e-30)
    den = a - 2 * b + c
    delta = 0.5 * (a - c) / den if den != 0 else 0.0
    return (k + delta) * fs_eff / nf


def est_all(snr_db):
    rx, mf = make(snr_db)
    m = mf[::SPS]                                              # ideal timing, 1 sps
    d = m[1:] * np.conj(m[:-1])
    fA = np.angle(np.sum(d ** 4)) / (8 * np.pi) * RS           # A: lag-1 angle of d^4
    fB = tone_peak(m ** 4, RS, search=RS / 2) / 4              # FFT of m^4 at symbol rate (needs timing)
    fC = tone_peak(mf ** 4, FS, search=FS / 8 * 4 / 4 * 4) / 4  # FFT of x^4 on matched-filtered 4 sps, no timing
    fD = tone_peak(rx ** 4, FS, search=FS / 8 * 4 / 4 * 4) / 4  # FFT of x^4 on raw 4 sps, no timing, no filter
    return fA, fB, fC, fD


names = ["A: lag-1 angle of d^4 (1 sps, timing)", "FFT of m^4 (1 sps, timing)",
         "FFT of x^4 (4 sps, after matched filter, no timing)", "FFT of x^4 (4 sps, raw, no timing)"]
snrs = np.arange(0, 31, 2)
TR = 120
rms = np.full((4, len(snrs)), np.nan); out = np.zeros((4, len(snrs)))
for j, snr in enumerate(snrs):
    err = np.array([[e - DF for e in est_all(snr)] for _ in range(TR)])      # TR x 4
    for i in range(4):
        e = err[:, i]; good = np.abs(e) <= 5e3
        out[i, j] = 100 * np.mean(~good)
        rms[i, j] = np.sqrt(np.mean(e[good] ** 2)) if good.sum() > 5 else np.nan
    print("SNR %2d dB  outliers%%: %s   rms Hz: %s" % (snr, " ".join("%5.1f" % v for v in out[:, j]), " ".join("%7.0f" % v for v in rms[:, j])), flush=True)

fig, ax = plt.subplots(1, 2, figsize=(12, 4.3))
for i in range(4):
    ax[0].semilogy(snrs, rms[i], "o-", label=names[i], ms=4)
    ax[1].plot(snrs, out[i], "o-", label=names[i], ms=4)
ax[0].set_xlabel("Es/N0 (dB)"); ax[0].set_ylabel("rms error, outliers excluded (Hz)"); ax[0].grid(True, which="both", alpha=0.3)
ax[1].set_xlabel("Es/N0 (dB)"); ax[1].set_ylabel("outliers |error| > 5 kHz (%)"); ax[1].grid(True, alpha=0.3); ax[1].legend(fontsize=7)
fig.suptitle("Frequency estimators for DQPSK, %d symbols, offset %.1f kHz, %d trials/point" % (NSYM, DF / 1e3, TR))
fig.tight_layout()
fig.savefig("/tmp/claude-0/-home-claude/164b9041-6620-56fd-b7f7-17496c21d4ff/scratchpad/compare_estimators.png", dpi=110)
