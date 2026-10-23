import numpy as np
RS = 960e3; T = 1 / RS; N = 63; n = np.arange(N)
x = np.exp(-1j * np.pi * 25 * n * (n + 1) / N)
a = [1] * 6
for k in range(57): a.append(a[k + 5] ^ a[k])
m = 1 - 2 * np.array(a, float)

def pc(r, s):
    return np.array([abs(np.sum(r * np.conj(np.roll(s, l)))) / N for l in range(N)])

def rx(s, f0, rate):
    t = n * T
    return s * np.exp(2j * np.pi * (f0 * t + 0.5 * rate * t ** 2))

print("sequence duration: %.1f us" % (N * T * 1e6))
print("\nA) frequency ramp INSIDE the sequence (start offset 0 Hz): peak magnitude")
print("%12s %14s | %8s %8s" % ("ramp Hz/s", "change in seq", "ZC", "m-seq"))
for r in (1e4, 1e6, 1e7, 1e8, 3e8, 1e9):
    print("%12.0e %11.2f Hz | %8.2f %8.2f" % (r, r * N * T, pc(rx(x, 0, r), x).max(), pc(rx(m, 0, r), m).max()))

print("\nB) static offset: ZC peak lag (0 = correct timing) and peak magnitude, N=63")
prev = None
for f in np.arange(0, 20001, 1000):
    c = pc(rx(x, f, 0), x); l = int(c.argmax()); l = l if l < N / 2 else l - N
    print("%6d Hz  lag %3d  peak %.2f   m-seq peak %.2f" % (f, l, c.max(), pc(rx(m, f, 0), m).max()))
print("\nthreshold Rs/(2N) = %.1f kHz" % (RS / (2 * N) / 1e3))
