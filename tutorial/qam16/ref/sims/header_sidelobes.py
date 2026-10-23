import numpy as np
rng = np.random.default_rng(5)
N = 63; n = np.arange(N)
def zc(u): return np.exp(-1j * np.pi * u * n * (n + 1) / N)
a = [1] * 6
for k in range(57): a.append(a[k + 5] ^ a[k])
mseq = (1 - 2 * np.array(a, float)).astype(complex)
seqs = {"ZC root 1": zc(1), "ZC root 25": zc(25), "m-sequence (BPSK)": mseq}

def qam(k):
    return (rng.choice([-3, -1, 1, 3], k) + 1j * rng.choice([-3, -1, 1, 3], k)) / np.sqrt(10)

print("A) aperiodic autocorrelation of the sync word alone: peak / largest sidelobe")
for name, s in seqs.items():
    c = np.abs(np.correlate(s, s, mode="full")); k0 = N - 1
    side = np.delete(c, k0)
    print("  %-18s %.1f  (%.1f dB)" % (name, c[k0] / side.max(), 20 * np.log10(c[k0] / side.max())))

print("\nB) sync word inside random 16-QAM (500 symbols each side), zero offset, no noise:")
print("   peak / largest other correlation value, 2000 trials")
for name, s in seqs.items():
    r = []
    for _ in range(2000):
        x = np.concatenate([qam(500), s, qam(500)])
        c = np.abs(np.correlate(x, s, mode="valid"))      # c[k] = |sum x[k+n] conj(s[n])|
        k0 = 500
        other = np.concatenate([c[:k0 - 1], c[k0 + 2:]])
        r.append(c[k0] / other.max())
    r = np.array(r)
    print("  %-18s median %.2f   5th pct %.2f   min %.2f" % (name, np.median(r), np.percentile(r, 5), r.min()))
