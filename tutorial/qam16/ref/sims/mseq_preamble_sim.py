import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RS = 960e3
T = 1 / RS
rng = np.random.default_rng(3)
OUT = "/tmp/claude-0/-home-claude/164b9041-6620-56fd-b7f7-17496c21d4ff/scratchpad/mseq_preamble_sim.png"

# recurrence a[k+n] = a[k+t] ^ a[k]  <->  x^n + x^t + 1 (primitive for these n, t)
POLY = {5: 3, 6: 5, 7: 6}


def mseq(n):
    t = POLY[n]
    a = [1] * n
    for k in range(2 ** n - 1 - n):
        a.append(a[k + t] ^ a[k])
    s = 1 - 2 * np.array(a, dtype=float)          # 0 -> +1, 1 -> -1
    ac = np.array([np.dot(s, np.roll(s, l)) for l in range(len(s))])
    assert ac[0] == len(s) and np.all(ac[1:] == -1), "not a maximal-length sequence"
    return s


SEQ = {31: mseq(5), 63: mseq(6), 127: mseq(7)}

# ---- panel 1: correlation peak vs carrier offset ----
df = np.linspace(-30e3, 30e3, 1201)


def coherent(s, f):
    k = np.arange(len(s))
    return np.abs(np.exp(2j * np.pi * f[:, None] * k[None, :] * T).sum(axis=1)) / len(s)   # |sum s*conj(s) e^{jwk}| / L


def partitioned(s, f, m):
    L = len(s); seg = L // m
    tot = 0
    for i in range(m):
        k = np.arange(i * seg, (i + 1) * seg)
        tot = tot + np.abs(np.exp(2j * np.pi * f[:, None] * k[None, :] * T).sum(axis=1))
    return tot / (seg * m)


# ---- panel 2: frequency estimate from the known sequence (remove modulation, then tone) ----
def tone_est(z, pad=8):
    nf = pad * len(z)
    S = np.abs(np.fft.fft(z, nf))
    k = int(np.argmax(S))
    a, b, c = np.log(S[(k - 1) % nf] + 1e-30), np.log(S[k] + 1e-30), np.log(S[(k + 1) % nf] + 1e-30)
    den = a - 2 * b + c
    d = 0.5 * (a - c) / den if den != 0 else 0.0
    kk = k + d
    if kk > nf / 2:
        kk -= nf
    return kk / nf * RS


def trial(s, snr_db, f):
    L = len(s); k = np.arange(L)
    n0 = 10 ** (-snr_db / 10)
    rx = s * np.exp(1j * (2 * np.pi * f * k * T + rng.uniform(0, 2 * np.pi)))
    rx = rx + np.sqrt(n0 / 2) * (rng.standard_normal(L) + 1j * rng.standard_normal(L))
    return tone_est(rx * s)


snrs = np.arange(0, 25, 3)
TR = 300
res = {}
for L in (31, 63, 127):
    rms, outl = [], []
    for snr in snrs:
        e = np.array([trial(SEQ[L], snr, rng.uniform(-30e3, 30e3)) for _ in range(TR)])
        # error against the truth used in each trial
        rms.append(e)
    res[L] = rms

# redo with stored truths (clean implementation)
res = {}
for L in (31, 63, 127):
    rms, outl = [], []
    for snr in snrs:
        err = []
        for _ in range(TR):
            f = rng.uniform(-30e3, 30e3)
            err.append(trial(SEQ[L], snr, f) - f)
        err = np.array(err); good = np.abs(err) < 2e3
        outl.append(100 * np.mean(~good))
        rms.append(np.sqrt(np.mean(err[good] ** 2)) if good.sum() > 5 else np.nan)
    res[L] = (rms, outl)
    print("L=%3d  rms Hz: %s" % (L, " ".join("%7.1f" % v for v in rms)))
    print("       outliers %%: %s" % " ".join("%5.1f" % v for v in outl))


def crlb_hz(L, snr_db):
    rho = 10 ** (snr_db / 10)
    return np.sqrt(6 / (rho * L * (L ** 2 - 1))) / (2 * np.pi * T)      # complex tone in complex noise (Rife-Boorstyn)


for L in (31, 63, 127):
    print("peak @ 9.7 kHz, L=%d: coherent %.2f" % (L, coherent(SEQ[L], np.array([9.7e3]))[0]),
          " partitioned x4: %.2f" % partitioned(SEQ[L][:(L // 4) * 4], np.array([9.7e3]), 4)[0] if L >= 63 else "")

fig, ax = plt.subplots(1, 2, figsize=(12.5, 4.6))
cols = {31: "#4a9eed", 63: "#f59e0b", 127: "#22c55e"}
for L in (31, 63, 127):
    ax[0].plot(df / 1e3, coherent(SEQ[L], df), color=cols[L], label="coherent, L=%d" % L)
ax[0].plot(df / 1e3, partitioned(SEQ[127][:124], df, 4), "--", color="#8b5cf6", label="L=127, 4 segments, non-coherent sum")
ax[0].axvline(9.7, color="gray", lw=0.8, ls=":"); ax[0].text(10.2, 0.92, "9.7 kHz", fontsize=9, color="gray")
ax[0].set_xlabel("carrier offset (kHz), Rs = 960 ksym/s"); ax[0].set_ylabel("correlation peak (1 = no offset)")
ax[0].grid(alpha=0.3); ax[0].legend(fontsize=8); ax[0].set_title("Detection: peak lost to frequency offset")
for L in (31, 63, 127):
    rms, outl = res[L]
    rms = [r if o <= 1.0 else np.nan for r, o in zip(rms, outl)]      # only where <= 1 % of trials were outliers (|error| > 2 kHz)
    ax[1].semilogy(snrs, rms, "o-", color=cols[L], ms=4, label="FFT estimate, L=%d" % L)
    ax[1].semilogy(snrs, [crlb_hz(L, s) for s in snrs], "--", color=cols[L], lw=1)
ax[1].set_xlabel("preamble Es/N0 (dB)"); ax[1].set_ylabel("rms frequency error (Hz)")
ax[1].grid(alpha=0.3, which="both"); ax[1].legend(fontsize=8)
ax[1].set_title("Frequency estimate from known sequence (dashed = CRLB)")
fig.tight_layout(); fig.savefig(OUT, dpi=120)
print(OUT)
