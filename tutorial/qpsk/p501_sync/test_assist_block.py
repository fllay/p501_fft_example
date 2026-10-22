"""Offline test of the epy block of qpsk_b210_frame_rx.grc (the source is taken from make_flowgraph_frame.py).   source tools/gnuradio_env.sh; python3 test_assist_block.py"""
import sys, numpy as np
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_flowgraph_frame as M
ns = {}; exec(M.ASSIST_SOURCE, ns); B = ns["blk"]
rng = np.random.default_rng(3)
a = [1,0,0,0,0,0]
while len(a) < 63: n = len(a)-6; a.append(a[n+1]^a[n])
chips = 1-2*np.array(a)
def synth(nfr, f_hz, snr_db, pl=960, preamble=True):
    steps = []
    for k in range(nfr):
        if preamble: steps += [1] + list(chips)
        else: steps += [1]*64
        steps += list(np.exp(1j*np.pi/2*rng.integers(0,4,pl)) if True else [])
    steps = np.array(steps, dtype=complex)
    ph = np.cumsum(np.angle(steps)) + 2*np.pi*f_hz/960e3*np.arange(len(steps)) + 1.234
    m = np.exp(1j*ph)
    sig = 10**(-snr_db/20)/np.sqrt(2)
    return m + sig*(rng.normal(size=len(m)) + 1j*rng.normal(size=len(m)))
def run(x, assist, chunk=(300, 6000)):
    b = B(thr=0.5, assist=assist, smooth=0.5); i=0; outs=[]; f=[]
    while i < len(x):
        k = int(rng.integers(*chunk)); c = x[i:i+k].astype(np.complex64); i += k
        o = [np.zeros(len(c), np.complex64), np.zeros(len(c), np.float32), np.zeros(len(c), np.float32)]
        b.work([c], o); outs.append(o[0]); f.append(o[1][-1]); hits = o[2][-1]
    return np.concatenate(outs), f, hits
def resid_hz(y):
    d = y[1:]*np.conj(y[:-1]); return np.angle(np.sum(d**4))/(8*np.pi)*960e3
nfr = 60
print("true Hz | SNR | hits (of %d) | last estimate Hz | residual Hz after assist (4th power, 2nd half) | before" % nfr)
for f_hz in (0, 9700, -9700, 60000, -150000, 300000):
    for snr in (20, 10, 6, 3):
        x = synth(nfr, f_hz, snr); y, f, hits = run(x, 1)
        h = len(x)//2
        print("%8d | %2d | %3d | %9.0f | %8.0f | %8.0f" % (f_hz, snr, hits, f[-1], resid_hz(y[h:]), resid_hz(x[h:])))
# pass-through: assist off leaves the stream unchanged
x = synth(10, 5000, 15); y, f, hits = run(x, 0); print("assist off: max |y-x| = %.2e, estimate still %.0f Hz, hits %d" % (np.max(np.abs(y-x)), f[-1], hits))
# false alarms: no preamble (random data), noise only
for what in ("random QPSK data", "noise only"):
    x = synth(500, 9700, 10, preamble=False) if what[0]=="r" else (rng.normal(size=500000)+1j*rng.normal(size=500000))
    y, f, hits = run(x, 1); print("%-17s: %d false preambles in %d symbols" % (what, hits, len(x)))
