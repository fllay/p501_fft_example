import numpy as np
rng = np.random.default_rng(9)
N = 63; n = np.arange(N); NCP = 8
zc = np.exp(-1j * np.pi * 1 * n * (n + 1) / N)
def qam(k): return (rng.choice([-3, -1, 1, 3], k) + 1j * rng.choice([-3, -1, 1, 3], k)) / np.sqrt(10)
worst_before, worst_after, worst_far = [], [], []
for _ in range(500):
    a, b = qam(300), qam(300)
    x = np.concatenate([a, zc[-NCP:], zc, b])            # [payload][CP][ZC][payload]
    c = np.abs(np.correlate(x, zc, mode="valid")) / N     # c[k]: window starting at k
    k0 = 300 + NCP                                        # correct start of the ZC proper
    worst_before.append(c[k0 - NCP:k0].max())             # windows starting inside the CP
    worst_after.append(c[k0 + 1:k0 + 9].max())            # the 8 positions after the peak
    worst_far.append(np.concatenate([c[:k0 - NCP - 1], c[k0 + 9:]]).max())
print("peak = 1.00 at the correct position")
print("largest value over the %d positions before the peak (inside the CP): %.2e" % (NCP, max(worst_before)))
print("largest value over the 8 positions after the peak: median %.2f, worst %.2f" % (np.median(worst_after), max(worst_after)))
print("largest value elsewhere (random payload): median %.2f, worst %.2f" % (np.median(worst_far), max(worst_far)))
print("overhead of an %d-symbol CP on a %d-symbol word: %.1f%%; on a 1000-symbol frame total: %.1f%%" % (NCP, N, 100 * NCP / (N + NCP), 100 * NCP / (N + NCP + 937)))
