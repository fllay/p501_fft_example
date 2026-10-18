#!/usr/bin/env python3
"""Analysis of a run of qpsk_b210_loop.py: bit error rate against the known repeating pattern, constellation, FLL frequency, spectrum."""
import sys, os
import numpy as np
from qpsk_b210_loop import tx_bits

d = sys.argv[1] if len(sys.argv) > 1 else "/tmp/qpsk_run"
pattern = sys.argv[2] if len(sys.argv) > 2 else "repeat8192"          # repeat8192: chapters 4a/4b; prbs15: the FPGA transmitter of chapter 4c
fs = 3.84e6
if pattern == "prbs15":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "p501_tx")); from qpsk_model import prbs15_bits
    tx = prbs15_bits(32767).astype(np.int8)
else:
    tx = tx_bits().astype(np.int8)
P = len(tx)
rx = np.fromfile(os.path.join(d, "rx_bits.u8"), dtype=np.uint8).astype(np.int8)
print(f"received {len(rx)} bits ({len(rx)/1.92e6:.1f} s of the link)")
raw = np.fromfile(os.path.join(d, "rx_raw.c64"), dtype=np.complex64)
txf = os.path.join(d, "tx_raw.c64")
txr = np.fromfile(txf, dtype=np.complex64) if os.path.exists(txf) else None
print((f"TX samples: rms {np.sqrt(np.mean(np.abs(txr)**2)):.3f}, peak {np.max(np.abs(txr)):.3f} (full scale 1.0) | " if txr is not None else "") + f"RX samples: rms {np.sqrt(np.mean(np.abs(raw)**2)):.4f}, peak {np.max(np.abs(raw)):.4f} (clipping at 1.0)")
# bit error rate: align with the repeating pattern by circular cross-correlation (on a stretch after the loops have locked), then count over the whole recording
start = int(0.35 * len(rx)) if len(rx) > 4_000_000 else 40000
seg = rx[start:start + (min(len(rx) - start, 2_000_000) // P) * P]
a = 2.0 * seg.reshape(-1, P).mean(axis=0) - 1.0                                    # average over the periods, +-1
cc = np.fft.ifft(np.fft.fft(2.0 * tx - 1.0) * np.conj(np.fft.fft(a))).real
shift = int(np.argmax(np.abs(cc))); inv = cc[shift] < 0
ref = np.roll(tx, -shift) if not inv else 1 - np.roll(tx, -shift)
# rx[start:] was aligned with ref, so the pattern position of rx[i] is (i - start) mod P
ref_full = ref[(np.arange(len(rx)) - start) % P]
err = (rx != ref_full).astype(np.int8)
nerr = int(err.sum()); where = np.where(err)[0]
print(f"alignment shift {shift} bits{' (inverted)' if inv else ''}; {nerr} bit errors in {len(err)} bits")
blk = 20000; nb = len(err) // blk; per = err[:nb * blk].reshape(nb, blk).sum(axis=1)
good = np.where(per <= blk // 1000)[0]                                           # blocks with at most 0.1 % errors
if len(where) == 0:
    print("RESULT: error-free from the first bit; BER < %.1e" % (1.0 / len(err)))
elif len(good) and good[0] * blk < len(err) // 5:
    lb = int(good[0]) * blk; after = err[lb:]
    print(f"RESULT: locked after {lb / 1.92e3:.0f} ms ({lb} bits, {int(err[:lb].sum())} errors during the pull-in); after lock: {int(after.sum())} errors in {len(after)} bits  ->  BER {after.sum() / len(after):.1e}" + ("" if after.sum() else f" (< {1.0 / len(after):.1e})"))
else:
    print(f"RESULT: NOT LOCKED or slipping: BER over the whole recording {err.mean():.2e}; errors per {blk} bits: {per[:20].tolist()}")
# block-by-block alignment: separates "never locked" (match about 0.5-0.75 at every block) from slips (match 1.0 with a changing alignment)
nper = 24; B = nper * P; tl = []
for j in range(min(len(rx) // B, 40)):
    sg = rx[j * B:(j + 1) * B]; av = 2.0 * sg.reshape(nper, P).mean(axis=0) - 1.0
    c2 = np.fft.ifft(np.fft.fft(2.0 * tx - 1.0) * np.conj(np.fft.fft(av))).real; k = int(np.argmax(np.abs(c2)))
    r2 = np.roll(tx, -k) if c2[k] > 0 else 1 - np.roll(tx, -k)
    tl.append((k, float(np.mean(sg == r2[np.arange(B) % P]))))
print("per block of %d bits (%.0f ms): match / alignment shift" % (B, B / 1.92e3))
print("  match :", " ".join(f"{m:.2f}" for k, m in tl)); print("  shift :", " ".join(f"{k}" for k, m in tl))
# frequency estimate of the FLL
fl = os.path.join(d, "fll_freq.f32")
if os.path.exists(fl):
    fr = np.fromfile(fl, dtype=np.float32) * fs / (2 * np.pi); fr_t = np.arange(len(fr)) * 1000 / fs
    tail = fr[len(fr)//2:]
    print(f"FLL frequency (the correction it applies, second half of the run): mean {np.mean(tail):+.1f} Hz, std {np.std(tail):.1f} Hz  ->  carrier offset of the received signal {-np.mean(tail):+.0f} Hz")
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    sy = np.fromfile(os.path.join(d, "sym_after_clock.c64"), dtype=np.complex64)
    sy = sy[len(sy) // 2:][:4000]                                                   # a steady-state burst of 4000 symbols (960 ksym/s)
    Rs = fs / 4; n4 = len(sy); L4 = np.abs(np.fft.fftshift(np.fft.fft(sy ** 4 * np.hanning(n4), 8 * n4))); f4 = np.fft.fftshift(np.fft.fftfreq(8 * n4, 1 / Rs)); i4 = int(np.argmax(L4))
    cfo = f4[i4] / 4                                                                 # QPSK: the 4th power removes the data, the line is at 4 x the offset (+- Rs/8 ambiguity)
    print(f"residual rotation before the Costas loop (4th-power estimate): {cfo:+.0f} Hz")
    fig, axs = plt.subplots(2, 2, figsize=(11, 8.4)); ax = axs.ravel()
    n = 1 << 16; X = np.fft.fftshift(np.fft.fft(raw[:n] * np.hanning(n))); f = np.fft.fftshift(np.fft.fftfreq(n, 1 / fs))
    ax[0].plot(f / 1e3, 20 * np.log10(np.abs(X) + 1e-9), lw=0.5); ax[0].set(title="received spectrum (RRC QPSK, 960 ksym/s)", xlabel="kHz", ylabel="dB"); ax[0].grid(alpha=.3)
    if os.path.exists(fl): ax[1].plot(fr_t, fr); ax[1].set(title="FLL: frequency correction", xlabel="s", ylabel="Hz"); ax[1].grid(alpha=.3)
    ax[2].plot(sy.real, sy.imag, ".", ms=1, alpha=.5); ax[2].set(title=f"after FLL and clock sync, before the Costas loop (rotating, residual {cfo:+.0f} Hz)", aspect="equal", xlabel="I", ylabel="Q"); ax[2].grid(alpha=.3); ax[2].title.set_fontsize(9)
    cs_file = os.path.join(d, "sym_after_costas.c64")
    if os.path.exists(cs_file):
        cs = np.fromfile(cs_file, dtype=np.complex64); cs = cs[len(cs) // 2:][:4000]
        ax[3].plot(cs.real, cs.imag, ".", ms=1.5, alpha=.5); ax[3].set(title="after the Costas loop: the constellation (DQPSK, 4 points)", aspect="equal", xlabel="I", ylabel="Q"); ax[3].grid(alpha=.3); ax[3].title.set_fontsize(9)
        r = np.abs(cs); ang = np.angle(cs * np.exp(-1j * np.pi / 4)); dev = (ang + np.pi / 4) % (np.pi / 2) - np.pi / 4
        evm = float(np.sqrt(np.mean(np.abs(cs - np.exp(1j * (np.round(np.angle(cs) / (np.pi / 2) - 0.5) * (np.pi / 2) + np.pi / 4)) * np.mean(r)) ** 2)) / np.mean(r))
        print(f"constellation after the Costas loop: EVM {100 * evm:.1f} % of the symbol amplitude (angular spread {np.degrees(np.std(dev)):.1f} degrees)")
    plt.tight_layout(); plt.savefig(os.path.join(d, "qpsk_run.png"), dpi=90); print("figure:", os.path.join(d, "qpsk_run.png"))
except Exception as e:
    print("(no figure:", e, ")")
