import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "/tmp/claude-0/-home-claude/164b9041-6620-56fd-b7f7-17496c21d4ff/scratchpad/zc_look.png"
RS = 960e3
N, U = 63, 1
n = np.arange(N)
x = np.exp(-1j * np.pi * U * n * (n + 1) / N)


def rrc(beta=0.35, sps=4, span=11):
    L = span * sps + 1
    t = (np.arange(L) - (L - 1) / 2) / sps
    h = np.zeros(L)
    for i, v in enumerate(t):
        if abs(v) < 1e-12:
            h[i] = 1 + beta * (4 / np.pi - 1)
        elif abs(abs(v) - 1 / (4 * beta)) < 1e-9:
            h[i] = beta / np.sqrt(2) * ((1 + 2 / np.pi) * np.sin(np.pi / (4 * beta)) + (1 - 2 / np.pi) * np.cos(np.pi / (4 * beta)))
        else:
            h[i] = (np.sin(np.pi * v * (1 - beta)) + 4 * beta * v * np.cos(np.pi * v * (1 + beta))) / (np.pi * v * (1 - (4 * beta * v) ** 2))
    return h / np.sqrt(np.sum(h ** 2) / sps)        # unit symbol energy at sps samples per symbol


def shape(sym, sps=4):
    up = np.zeros(len(sym) * sps, complex); up[::sps] = sym
    return np.convolve(up, rrc(sps=sps))


def papr_db(s):
    p = np.abs(s) ** 2
    return 10 * np.log10(p.max() / p.mean())


# ZC repeated so the middle period has no edge effects
zc_sh = shape(np.tile(x, 5)); mid = zc_sh[2 * N * 4 + 44: 3 * N * 4 + 44]
rng = np.random.default_rng(2)
q = rng.choice([-3, -1, 1, 3], 6000) + 1j * rng.choice([-3, -1, 1, 3], 6000)
q = q / np.sqrt(10)
qam_sh = shape(q)[60:-60]
print("PAPR, ZC at 1 sps: %.2f dB" % papr_db(x))
print("PAPR, ZC after RRC (0.35, 4 sps): %.2f dB" % papr_db(mid))
print("PAPR, random 16-QAM after RRC: %.2f dB" % papr_db(qam_sh))

fig, ax = plt.subplots(2, 2, figsize=(12, 8.2))

a = ax[0, 0]
a.plot(n, x.real, "o-", ms=3, lw=1, color="#4a9eed", label="I (real)")
a.plot(n, x.imag, "o-", ms=3, lw=1, color="#f59e0b", label="Q (imag)")
a.set_xlabel("symbol index n"); a.set_ylabel("amplitude"); a.grid(alpha=0.3); a.legend(loc="upper right", fontsize=8)
a.set_title("I and Q: oscillation that speeds up (a chirp)")

a = ax[0, 1]
sc = a.scatter(x.real, x.imag, c=n, cmap="viridis", s=26)
a.add_patch(plt.Circle((0, 0), 1, fill=False, color="gray", lw=0.8, ls="--"))
a.set_aspect("equal"); a.set_xlim(-1.3, 1.3); a.set_ylim(-1.3, 1.3); a.grid(alpha=0.3)
ND = len(set(np.round(np.angle(x), 6)))
print("distinct phases used: %d of %d symbols" % (ND, N))
a.set_xlabel("I"); a.set_ylabel("Q"); a.set_title("Constellation: %d symbols, %d distinct phases, all on the unit circle" % (N, ND), fontsize=10)
fig.colorbar(sc, ax=a, fraction=0.046, pad=0.04, label="n")

a = ax[1, 0]
fw = -U * (n + 1) / N                      # cycles per sample, unwrapped
fw = (fw + 0.5) % 1 - 0.5                  # wrapped to one sampling band
a.plot(n, fw * RS / 1e3, "o", ms=3, color="#8b5cf6")
a.set_xlabel("symbol index n"); a.set_ylabel("instantaneous frequency (kHz)"); a.grid(alpha=0.3)
a.set_title("Frequency sweeps the whole %.0f kHz band once (wraps at ±%.0f kHz)" % (RS / 1e3, RS / 2e3))

a = ax[1, 1]
tt = np.arange(len(mid)) / 4
a.plot(tt, np.abs(mid), color="#22c55e", lw=1.6, label="ZC, RRC-shaped (PAPR %.1f dB)" % papr_db(mid))
seg = qam_sh[400:400 + len(mid)]
a.plot(tt, np.abs(seg), color="#9ca3af", lw=1, alpha=0.9, label="random 16-QAM (PAPR %.1f dB over whole run)" % papr_db(qam_sh))
a.set_xlabel("time (symbols)"); a.set_ylabel("|signal|"); a.grid(alpha=0.3); a.legend(fontsize=8, loc="upper right")
a.set_ylim(0, max(np.abs(seg).max(), np.abs(mid).max()) * 1.15)
a.set_title("Envelope after RRC shaping: flat except mid-sequence", fontsize=10)

fig.suptitle("Zadoff-Chu sequence, length %d, root %d (a sequence of complex symbols, not a modulation)" % (N, U), fontsize=12)
fig.tight_layout(); fig.savefig(OUT, dpi=120)
print(OUT)
