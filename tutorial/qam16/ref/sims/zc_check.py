import numpy as np
RS = 960e3

def zc(N, u):
    n = np.arange(N)
    return np.exp(-1j * np.pi * u * n * (n + 1) / N)       # odd N

def mseq6():
    a = [1] * 6
    for k in range(63 - 6):
        a.append(a[k + 5] ^ a[k])
    return 1 - 2 * np.array(a, float)

def pcorr(r, x):
    N = len(x)
    return np.array([np.abs(np.sum(r * np.conj(np.roll(x, l)))) / N for l in range(N)])   # periodic correlation vs lag

N = 63
x = zc(N, 25)
print("constant amplitude:", np.allclose(np.abs(x), 1))
c = pcorr(x, x); print("periodic autocorr: peak %.3f, max off-peak %.2e" % (c[0], c[1:].max()))
Np = 61
c12 = [np.abs(np.sum(zc(Np, 1) * np.conj(np.roll(zc(Np, 5), l)))) / Np for l in range(Np)]
print("cross-corr roots 1 vs 5 (N=61): min %.3f max %.3f, 1/sqrt(N)=%.3f" % (min(c12), max(c12), 1 / np.sqrt(Np)))
X = np.abs(np.fft.fft(x)) / np.sqrt(N); print("DFT magnitude flat: min %.3f max %.3f" % (X.min(), X.max()))

m = mseq6(); n = np.arange(N)
print("\nCFO behaviour, N=63, periodic correlation, peak magnitude (1 = no offset) and lag of the peak")
print("%12s %9s | %-18s | %-18s" % ("offset", "bins", "ZC u=25 (peak, lag)", "m-seq (peak, lag)"))
for f in (0, 2e3, 5e3, 9.7e3, 15e3, 30e3):
    d = f / RS * N                                   # offset in bins of the N-point sequence
    rot = np.exp(2j * np.pi * d * n / N)
    cz = pcorr(x * rot, x); cm = pcorr(m * rot, m)
    print("%9.1f Hz %9.2f | %5.2f at lag %2d      | %5.2f at lag %2d" % (f, d, cz.max(), cz.argmax(), cm.max(), cm.argmax()))
print("\nup/down chirp pair: root u and N-u (conjugate), offset 4 bins")
rot = np.exp(2j * np.pi * 4 * n / N)
print("peak lag, root 25:", pcorr(x * rot, x).argmax(), " root 38 (=63-25):", pcorr(zc(N, 38) * rot, zc(N, 38)).argmax())
