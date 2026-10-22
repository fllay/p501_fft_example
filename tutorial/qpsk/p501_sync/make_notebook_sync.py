#!/usr/bin/env python3
"""Writes notebook/P501_QPSK_SYNC_Live.ipynb: the P501 side of the interactive test of the m-sequence frame synchroniser (overlay p501_qpsk_trx_sync). The B210 side is the GNU Radio
flowgraph tutorial/qpsk/p501_sync/qpsk_b210_frame_tx.grc (or qpsk_frame_tx.py).     python3 make_notebook_sync.py"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "notebook", "P501_QPSK_SYNC_Live.ipynb"))
cells = []


def md(text): cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)})
def code(text): cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip("\n").splitlines(True)})


md("""
# Live: frame synchronisation with a known m-sequence, in the P501 FPGA, against a B210 and GNU Radio

The receiver of the overlay **`p501_qpsk_trx_sync`** finds the start of each frame by correlating the **phase steps** of the received symbols with a known 63-chip **m-sequence** preamble, 915.0 MHz, 3.84 MSPS, 960 ksym/s differential QPSK.

**The frames** (sent by the B210): a 64-symbol **preamble** (a reference symbol, then 63 phase steps: step 0 for a chip +1, step 180 degrees for a chip -1) followed by `PL` **payload** symbols of PRBS-15 (restarted in every frame);
`FL = 64 + PL` symbols per frame (960 -> 1024 symbols = 1.067 ms, 937.5 frames per second).

**What the FPGA does** (beside the receiver of chapter 4d, once per symbol):
* `d = m x conj(m_previous)`: the phase step (it has no carrier phase in it, and only `2 pi f T` from the frequency offset), so it works **before the Costas loop has locked**;
* `C = sum chip[k] d[n-62+k]` over the last 63 steps (and `E = sum |d|`): at the last step of the preamble `|C|` is almost `E` (a quality of about 0.9); on random data it is about `E / 8` (0.13); the threshold is 0.55 by default;
* a **peak** (candidate, larger than its neighbours) is one frame; **two peaks one frame apart (+-1 symbol) lock** the tracker; it predicts the next peak, counts **hits** and **misses**, and after 3 misses in a row searches again;
* `arg(C) = 2 pi f T`: the **frequency offset** from the preamble (data aided, |f| < 480 kHz);
* the **payload gate** (locked, and the symbol is inside the payload): the PRBS-15 checker counts bit errors only there;
* **hardware acquisition** (the synchroniser and the Costas loop cooperate, all in the FPGA): at every lock/hit an atan2 CORDIC turns `C` into the frequency and the hardware **writes it into the Costas loop's frequency** (the first 8 times, or at every frame);
  the Costas loop starts with wide **acquisition gains** and the tracker switches it to the narrow **tracking gains** four frames after the lock. No hint, no search loop in Python: the receiver locks at any offset up to +-110 kHz.

**Before you start**
* Overlay `p501_qpsk_trx_sync` copied to `/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync/` (with `p501_qpsk.py`, `p501_qpsk_rx.py`, `p501_qpsk_rx_sync.py`), and the notebooks of `p501_fft_dds` (for `p501_radio.py`).
* The transmitter: the B210 flowgraph **`tutorial/qpsk/p501_sync/qpsk_b210_frame_tx.grc`** (set *Transmit* ON, TX gain 80; **`payload_syms` must match the *Payload* control below**: 960 by default), or `python3 qpsk_frame_tx.py --payload 960 --seconds 600`.
* Antennas on TX1 / RX1 of the P501 and on the TX/RX port of the B210, a few centimetres apart. **Very low power** (B210 TX gain 80 dB at most). Check the rules where you are before transmitting.
* **Start the transmitter first, then press Start receiver.** The transmitter can be the B210 (flowgraph) **or the P501's own FPGA transmitter, which now sends the same frames** (`rtl/qpsk_tx_fr.v`, the *FPGA transmits* control): then the whole link is in the FPGA, in the AD9361's digital loopback or over the air between the P501's antennas.
* Everything ends quiet: the last cell (*Stop and silence*) turns the transmitter off and sets the TX attenuation to its maximum.
""")

md("## Configuration, overlay and bring-up")
code('''
BIT       = "/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync/p501_qpsk_trx_sync.bit"   # transmitter + receiver with the frame synchroniser in one overlay (the .hwh next to it)
FS        = 3_840_000          # sample rate
LO        = 915_000_000        # carrier, Hz: the B210 flowgraph uses the same
RX_GAIN   = 70                 # P501 RX gain-table index 0..76: 70 for the B210's weak signal through the air
TX_ATTEN0 = 89.75              # TX attenuation (dB) at the start and at the end: the transmitter is silent
PAYLOAD   = 960                # payload symbols per frame: the same as payload_syms of the flowgraph (a multiple of 4)
''')
code('''
import sys, time, os, io, threading
import numpy as np
from pynq import Overlay

sys.path.insert(0, '/home/xilinx/jupyter_notebooks')
sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds')            # p501_radio.py, p501_dds.py
sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync')      # p501_qpsk.py, p501_qpsk_rx.py, p501_qpsk_rx_sync.py
import p501_radio
from p501_qpsk import P501QpskTxFrames
from p501_qpsk_rx import soft_quality, constellation_ok, UNIT, REG, _signed, SYMBOL_RATE
import importlib, p501_qpsk_rx, p501_qpsk_rx_sync
for _m in (p501_qpsk_rx, p501_qpsk_rx_sync): importlib.reload(_m)                   # a module that is already imported is not re-read: reload, so that a newer file is used without restarting the kernel
from p501_qpsk_rx_sync import P501QpskRxSync
print('driver:', p501_qpsk_rx_sync.__file__)
assert hasattr(__import__("p501_qpsk"), "P501QpskTxFrames"), "p501_qpsk.py is older than this notebook: copy notebook/p501_qpsk.py again and restart the kernel"
_need = [m for m in ("configure_sync", "configure_acquisition", "acquire_hw", "gate_enable", "sync_status", "wait_lock", "corr_freq_hz") if not hasattr(P501QpskRxSync, m)]
assert not _need, f"p501_qpsk_rx_sync.py is older than this notebook (missing {_need}): copy notebook/p501_qpsk_rx_sync.py again to /home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync/ and RESTART THE KERNEL (a module that is already imported is not re-read)"

results = {}
def check(name, ok, detail):
    results[name] = (bool(ok), detail)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

ol = Overlay(BIT)                                  # programs the PL
tx = P501QpskTxFrames(ol.qpsk_regs, FS)            # transmitter registers at 0x9C460000: enable, amplitude, frames (the FTW register: bit 31 frames, bits 15:0 the payload symbols)
rx = P501QpskRxSync(ol.qpsk_rx)                    # receiver registers at 0x9C470000 (the constructor checks the ID 0xDD520005: the frame synchroniser)
ad = p501_radio.bring_up(ol, LO, 4_000_000, TX_ATTEN0, RX_GAIN)     # the AD9361 over SPI; TX attenuation at its maximum during the calibrations
tx.off(); rx.stop()

a_tx, a_rx = ol.ip_dict["qpsk_regs"]["phys_addr"], ol.ip_dict["qpsk_rx"]["phys_addr"]
check("both blocks in the overlay", a_tx == 0x9C460000 and a_rx == 0x9C470000, f"qpsk_regs at 0x{a_tx:08X}, qpsk_rx at 0x{a_rx:08X}")
check("AD9361 up", ad.info["ok"], f"LO locks {ad.info['rx_lock']}/{ad.info['tx_lock']}, ENSM 0x{ad.info['ensm']:X}, calibrations {ad.info['calibrations']}")
''')

md("""
## Self-test: the FPGA transmitter into the FPGA receiver, inside the AD9361 (digital loopback)

No antennas, no B210. First the FPGA transmitter sends PRBS-15 **without frames**: the synchroniser must find **no** frame; with the gate off the checker counts everything (the receiver of chapter 4d) and must see no bit error;
with the gate on and the tracker not locked, the checker must count **nothing**. Then it sends **frames**: the synchroniser must lock within a few milliseconds, find every frame, and the payload must be error free (all in the FPGA: framed transmitter -> hardware acquisition -> gated checker).
""")
code('''
FL = PAYLOAD + 64
p501_radio.loopback(ad, True)
rx.stop(); rx.configure(timing_bw=2 * np.pi / 100, phase_bw=2 * np.pi / 100); rx.configure_sync(fl=FL, pl=PAYLOAD)
rx.gate_enable(False); rx.start(); tx.start(amp=0.5); time.sleep(0.6)
s0 = rx.stats(); time.sleep(2.0); s1 = rx.stats(); y1 = rx.sync_status()
bits_off = s1["bits"] - s0["bits"]; err_off = s1["mismatches"] - s0["mismatches"]
rx.gate_enable(True); time.sleep(0.1); s2 = rx.stats(); time.sleep(1.0); s3 = rx.stats(); y3 = rx.sync_status()
tx.off(); rx.stop(); p501_radio.loopback(ad, False)

check("loopback, gate off: the checker counts", bits_off > 3_000_000, f"{bits_off:,} bits in 2 s")
check("loopback, gate off: no bit error", err_off == 0, f"{err_off} mismatches")
check("loopback: no frame in PRBS-only data", y1["locks"] == 0 and y3["locks"] == 0, f"peaks {y3['peaks']}, locks {y3['locks']} in about 4 s ({3.6 * SYMBOL_RATE / 1e6:.1f} M symbols)")
check("loopback, gate on, not locked: the checker is closed", s3["bits"] == s2["bits"], f"bits {s2['bits']:,} -> {s3['bits']:,}")
check("synchroniser keeps up with the symbols", y3["late"] == 0, f"late = {y3['late']}")
check("no overruns", s3["overruns"] == 0, f"overruns {s3['overruns']}")

# the frames of the FPGA transmitter
p501_radio.loopback(ad, True); ad.set_tx_atten_db(20.0)
rx.stop(); rx.configure(timing_bw=2 * np.pi / 400, phase_bw=2 * np.pi / 400); rx.configure_sync(fl=FL, pl=PAYLOAD); rx.configure_acquisition(load=1, nload=8, nsw=4); rx.gate_enable(True)
rx.start(); time.sleep(0.2); tx.start_frames(payload=PAYLOAD, amp=0.5); t0 = time.time(); ok = rx.wait_lock(1.0); t_lock = (time.time() - t0) * 1e3
time.sleep(0.5); s4 = rx.stats(); y4 = rx.sync_status(); time.sleep(2.0); s5 = rx.stats(); y5 = rx.sync_status(); f_hz, q, sd = rx.corr_freq_hz(n=50)
tx.off(); rx.configure_acquisition(load=0, nsw=0); rx.stop(); p501_radio.loopback(ad, False)
exp = 2.0 * SYMBOL_RATE / FL
check("FPGA frames: the frame sync locks", ok, f"locked after {t_lock:.1f} ms")
check("FPGA frames: every frame found", y5["hits"] - y4["hits"] >= exp - 2 and y5["misses"] == 0 and y5["false"] == 0, f"{y5['hits'] - y4['hits']} hits in 2 s (frames sent {exp:.0f}), misses {y5['misses']}, false {y5['false']}")
check("FPGA frames: payload without a bit error", s5["bits"] - s4["bits"] > 3_000_000 and s5["mismatches"] == s4["mismatches"], f"{s5['bits'] - s4['bits']:,} payload bits, {s5['mismatches'] - s4['mismatches']} mismatches")
check("FPGA frames: frequency from the preamble about 0", abs(f_hz) < 300 and q > 0.9, f"{f_hz:+.1f} Hz (consistency {q:.2f}), Costas {rx._omega_hz():+.1f} Hz")
''')

md("""
## The live machinery

* `render()` draws one picture with NumPy and Pillow: the **constellation** after the Costas loop, the **BER of the payload** (since the start and over the last 2 s: mismatches / 3 / bits, the checker counts 3 mismatches per isolated bit error), the **correlation vectors** `C` at the last peaks (each one has the length `|C|` normalised and the angle `2 pi f T`: a tight cluster at an angle means a steady frequency offset), the **status**
  (locked, gate, peaks, hits, misses, false peaks, losses, bit errors in the payload) and three strips: the **frequency** from the preamble (purple, one frame per picture) and from the Costas loop (blue), the **frames found per second** against the expected rate, and the **payload mismatches per second**.
* `Live` runs `read registers -> read capture RAM -> picture` in a background thread, so the controls stay responsive.
""")
code('''
import ipywidgets as widgets
from IPython.display import display, Image as IPImage
from PIL import Image as PILImage, ImageDraw, ImageFont

W, H = 840, 620
CX, CY, SC = 215, 200, 76                           # constellation centre and pixels per unit (axes +-2.5)
VX, VY, VR = 215, 520, 62                           # the circle of the correlation vectors
FONT = ImageFont.load_default()
HIST = 80
hist_f = [np.nan] * HIST; hist_c = [np.nan] * HIST; hist_h = [np.nan] * HIST; hist_m = [np.nan] * HIST; vec = []
# frequency from the preamble (Hz), Costas frequency (Hz), frames found per second, payload mismatches per second

def base_frame():
    img = PILImage.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(img)
    d.rectangle([CX - 2.5 * SC, CY - 2.5 * SC, CX + 2.5 * SC, CY + 2.5 * SC], outline=(90, 90, 90))
    for u in (-2, -1, 0, 1, 2):
        d.line([CX + u * SC, CY - 2.5 * SC, CX + u * SC, CY + 2.5 * SC], fill=(225, 225, 225)); d.line([CX - 2.5 * SC, CY - u * SC, CX + 2.5 * SC, CY - u * SC], fill=(225, 225, 225))
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = CX + sx * 1.24 * SC, CY - sy * 1.24 * SC
            d.line([x - 5, y, x + 5, y], fill=(200, 80, 80)); d.line([x, y - 5, x, y + 5], fill=(200, 80, 80))
    d.text((CX - 70, CY + 2.5 * SC + 6), "soft symbols after the Costas loop", fill=(60, 60, 60), font=FONT)
    d.ellipse([VX - VR, VY - VR, VX + VR, VY + VR], outline=(150, 150, 150)); d.line([VX - VR, VY, VX + VR, VY], fill=(225, 225, 225)); d.line([VX, VY - VR, VX, VY + VR], fill=(225, 225, 225))
    d.text((VX - 100, VY + VR + 6), "correlation C at the peaks (unit vectors): angle = 2 pi f T", fill=(60, 60, 60), font=FONT)
    return img
BASE = base_frame()

def strip(d, x0, y0, w, h, series, label, lo=None, hi=None):
    d.rectangle([x0, y0, x0 + w, y0 + h], outline=(150, 150, 150)); d.text((x0, y0 - 12), label, fill=(60, 60, 60), font=FONT)
    allv = np.concatenate([np.asarray(s, dtype=float) for s, _ in series]); allv = allv[~np.isnan(allv)]
    if lo is None:
        c = float(np.median(allv)) if len(allv) else 0.0; span = max(2000.0, 1.2 * (float(allv.max() - allv.min()) if len(allv) else 0.0))
        lo, hi = c - span / 2, c + span / 2
    for data, color in series:
        pts = [(x0 + i * w / (len(data) - 1), y0 + h - (min(max(v, lo), hi) - lo) / (hi - lo) * h) for i, v in enumerate(data) if not np.isnan(v)]
        if len(pts) > 1: d.line(pts, fill=color, width=1)
    d.text((x0 + w + 4, y0 - 2), f"{hi:.0f}", fill=(100, 100, 100), font=FONT); d.text((x0 + w + 4, y0 + h - 9), f"{lo:.0f}", fill=(100, 100, 100), font=FONT)

def render(z, st, y, mrate, hrate, expected, ber_recent=float('nan'), note=""):
    img = BASE.copy(); d = ImageDraw.Draw(img)
    zn = np.asarray(z) / UNIT
    for a, b in zip(zn.real, zn.imag):
        x, yy = CX + a * SC, CY - b * SC
        if abs(a) < 2.5 and abs(b) < 2.5: d.rectangle([x - 1, yy - 1, x + 1, yy + 1], fill=(31, 119, 180))
    for v in vec[-HIST:]:
        d.rectangle([VX + VR * v.real - 1, VY - VR * v.imag - 1, VX + VR * v.real + 1, VY - VR * v.imag + 1], fill=(130, 50, 170))
    mag, spread = soft_quality(z)
    X = 450
    d.text((X, 20), "FRAME SYNC LOCKED" if y["locked"] else "NOT LOCKED", fill=(30, 140, 50) if y["locked"] else (200, 40, 40), font=FONT)
    d.text((X, 36), note, fill=(110, 110, 110), font=FONT)
    lines = [f"gate {'OPEN (payload)' if y['gate'] else 'closed'}      expected {expected:.0f} frames/s, found {hrate:.0f}/s",
             f"peaks {y['peaks']:>8,}  hits {y['hits']:>8,}  misses {y['misses']:>5,}  false {y['false']:>4,}",
             f"locks {y['locks']}  lost {y['lost']}  late {y['late']}      quality |C|/sum|d| {y['quality']:.2f}",
             f"payload bits {st['bits']:>10,}  mismatches {st['mismatches']:>7,} (about {st['mismatches'] // 3:,} errors)",
             (f"BER (payload): no error in {st['bits'] / 1e6:.1f} Mbit (BER < {1.0 / max(st['bits'], 1):.0e})" if (st['bits'] and st['mismatches'] == 0) else f"BER (payload): {st['ber_estimate']:.1e} since start, " + ("-" if ber_recent != ber_recent else f"{ber_recent:.1e}") + " last 2 s"),
             f"frequency from the preamble {y['freq_hz']:+9.0f} Hz  (one frame)",
             f"Costas frequency            {st['carrier_offset_hz']:+9.0f} Hz",
             f"AGC gain {st['agc_gain']:.2f}   |z| {mag:.2f}   spread {spread:.1f} deg   overruns {st['overruns']}"]
    for i, l in enumerate(lines): d.text((X, 62 + 16 * i), l, fill=(0, 0, 0), font=FONT)
    strip(d, X, 200, 340, 80, [(hist_f, (130, 50, 170)), (hist_c, (31, 119, 180))], "frequency: preamble (purple), Costas (blue) (Hz)")
    strip(d, X, 320, 340, 80, [(hist_h, (30, 150, 60))], "frames found per second (0 .. 1200)", 0, 1200)
    strip(d, X, 440, 340, 80, [(hist_m, (180, 40, 40))], "payload mismatches per second, 0 .. 1000", 0, 1000)
    buf = io.BytesIO(); img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()

class Live:
    """Background thread: registers + capture RAM -> picture."""
    def __init__(self, image, status):
        self.image, self.status = image, status
        self.running, self.thread, self.frames = False, None, 0
        self.last, self.last_t = None, time.time()
        self.locked, self.y, self.st = False, None, None
        self.win = []                                            # (time, bits, mismatches) of the last 2 s, for the recent BER
        self.paused = False                                      # set while a start procedure or an experiment uses the registers
        self.fl = PAYLOAD + 64
    def _run(self):
        t_rate = time.time(); n_rate = 0; rate = 0.0
        while self.running:
            if self.paused:
                time.sleep(0.05); continue
            try:
                st = rx.stats(); y = rx.sync_status()
                z = rx.capture() if st["running"] else getattr(self, "z", np.zeros(1024, dtype=complex)); self.z = z
                now = time.time(); dt = max(now - self.last_t, 1e-3)
                if self.last is not None and y["hits"] >= self.last[0] and st["mismatches"] >= self.last[1]:
                    hrate = (y["hits"] - self.last[0]) / dt; mrate = (st["mismatches"] - self.last[1]) / dt
                else: hrate, mrate = 0.0, 0.0
                self.last, self.last_t = (y["hits"], st["mismatches"]), now
                self.locked = bool(y["locked"])
                if y["cre"] or y["cim"]:
                    c = complex(y["cre"], y["cim"]); vec.append(c / abs(c))
                    if len(vec) > 4 * HIST: del vec[:HIST]
                for h, v in ((hist_f, y["freq_hz"] if (y["cre"] or y["cim"]) else np.nan), (hist_c, st["carrier_offset_hz"]), (hist_h, hrate), (hist_m, mrate)): h.pop(0); h.append(v)
                self.y, self.st = y, st
                self.win.append((now, st["bits"], st["mismatches"])); self.win = [w for w in self.win if now - w[0] <= 2.0]
                ber_recent = float("nan")
                if len(self.win) > 1 and self.win[-1][1] > self.win[0][1] and self.win[-1][1] >= self.win[0][1] and self.win[-1][2] >= self.win[0][2]:
                    ber_recent = (self.win[-1][2] - self.win[0][2]) / 3.0 / (self.win[-1][1] - self.win[0][1])
                self.image.value = render(z, st, y, mrate, hrate, SYMBOL_RATE / self.fl, ber_recent, f"{rate:.1f} pictures/s")
                self.frames += 1; n_rate += 1
                if now - t_rate > 2: rate = n_rate / (now - t_rate); t_rate = now; n_rate = 0
            except TimeoutError:
                self.status.value = "capture timed out: is the receiver running?"; time.sleep(0.5)
            except Exception as e:
                self.status.value = f"{type(e).__name__}: {e}"; time.sleep(0.5)
        self.status.value = f"stopped after {self.frames} pictures"
    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.running = True; self.frames = 0
            self.thread = threading.Thread(target=self._run, daemon=True); self.thread.start()
            self.status.value = "running"
    def stop(self):
        self.running = False
        if self.thread is not None: self.thread.join(timeout=5)
''')

md("""
### Picture self-test

A few pictures of the digital loopback (PRBS only, no frames: the display must say *NOT LOCKED*), to check the machinery before a browser is involved.
""")
code('''
p501_radio.loopback(ad, True); rx.stop(); rx.configure(timing_bw=2 * np.pi / 100, phase_bw=2 * np.pi / 100); rx.configure_sync(fl=PAYLOAD + 64, pl=PAYLOAD); rx.gate_enable(True); rx.start(); tx.start(amp=0.5); time.sleep(0.5)
img_w, st_w = widgets.Image(format="png"), widgets.Label()
lv = Live(img_w, st_w)
lv.start(); time.sleep(3); lv.stop()
fps = lv.frames / 3.0
check("live pictures", lv.frames > 4 and len(img_w.value) > 2000, f"{lv.frames} pictures in 3 s ({fps:.1f}/s), status: {st_w.value}")
check("live: no frame in PRBS-only data", not lv.locked, f"locked = {lv.locked}")
display(IPImage(img_w.value))
tx.off(); rx.stop(); p501_radio.loopback(ad, False)
''')

md("""
## Controls

**Receiver**
* **Payload** and **Frame**: the payload symbols per frame (the same as `payload_syms` in the flowgraph; a multiple of 4); the frame is 64 + payload symbols. They are written to the synchroniser (`SY_PL`, `SY_FL`) when you press *Start receiver* or *Apply*.
* **Start mode**: *Hardware acquisition* (the default) starts the receiver cold with the tracking loops (`2 pi / 400`) and lets the frame synchroniser do the rest in the FPGA: it finds the preamble, **loads the Costas frequency** from `arg(C)` and, *Hits to narrow* frames after the lock, switches the Costas loop from the acquisition gains (*Acq. 2pi/N*) to the tracking gains.
  *Load*: *first N locks/hits* (N = 8: the acquisition), *every lock/hit* (the frequency is renewed every frame: it follows a drifting offset, but the loop's own integrator is replaced every frame, so the loop noise of the preamble's estimate, about 1 kHz, goes into the Costas frequency), or *off*.
  *Python carrier search + sync* is the old way (`rx.acquire()`: wide loops with initial-frequency hints, then narrow; the synchroniser only gates the checker).
  *Sync only (Costas unlocked)* starts with loops of `2 pi / 1600`, which cannot pull in the +9.7 kHz offset: the constellation spins, the bit errors are meaningless, **but the synchroniser finds the frames and measures the frequency just the same.**
* **Threshold** (`SY_THR`, 256 x |C| / E: 140 = 0.55), **Tolerance** (symbols), **Misses to lose the lock**, **Guard** (the first payload symbol that counts: 2 by default): written live (*Apply*).
* **Gate**: ticked, the bit error counters (`BITS`, `MISMATCH`) count only inside the payload of locked frames (and restart at its start); unticked, they count everything.
* **RX gain**: the AD9361's receive gain index (70 for the B210 at 80 dB). **Digital loopback**: the chip feeds the transmitter into the receiver without an antenna.
* **FPGA transmits**: *frames* (the P501's own transmitter sends the frames, payload = the *Payload* control; with *Digital loopback*, or over the air from TX1 to RX1 with **TX atten 20 to 30 dB**: weaker than 40 dB is too weak for this antenna spacing) or *PRBS-15, no frames* (for the false-alarm test). Start the transmitter first, then **Start receiver**.

**Start display / Stop display**: the live picture; stopping it does not stop the receiver.
""")
code('''
w_mode  = widgets.Dropdown(options=[("Hardware acquisition (the sync loads the Costas loop)", "hw"), ("Python carrier search + sync", "search"), ("Sync only (Costas unlocked)", "nocostas")], value="hw", description="Start mode", layout=widgets.Layout(width="520px"))
w_pl    = widgets.IntText(value=PAYLOAD, step=4, description="Payload", layout=widgets.Layout(width="180px"))
w_fl    = widgets.Label(value=f"Frame {PAYLOAD + 64}")
w_thr   = widgets.IntSlider(value=140, min=40, max=250, step=5, description="Threshold", continuous_update=False, layout=widgets.Layout(width="420px"))
w_tol   = widgets.IntSlider(value=1, min=0, max=4, description="Tolerance", continuous_update=False, layout=widgets.Layout(width="320px"))
w_mm    = widgets.IntSlider(value=3, min=1, max=10, description="Misses", continuous_update=False, layout=widgets.Layout(width="320px"))
w_gd    = widgets.IntSlider(value=2, min=0, max=8, description="Guard", continuous_update=False, layout=widgets.Layout(width="320px"))
w_ld    = widgets.Dropdown(options=[("first N locks/hits", 1), ("every lock/hit", 2), ("off", 0)], value=1, description="Load", layout=widgets.Layout(width="260px"))
w_nld   = widgets.IntText(value=8, description="N", layout=widgets.Layout(width="140px"))
w_nsw   = widgets.IntSlider(value=4, min=0, max=32, description="Hits to narrow", continuous_update=False, layout=widgets.Layout(width="380px"))
w_acqd  = widgets.Dropdown(options=[50, 100, 200], value=100, description="Acq. 2pi/N", layout=widgets.Layout(width="200px"))
w_gate  = widgets.Checkbox(value=True, description="Gate the bit error counters to the payload", layout=widgets.Layout(width="380px"))
w_rxg   = widgets.IntSlider(value=RX_GAIN, min=0, max=76, description="RX gain", continuous_update=False, layout=widgets.Layout(width="520px"))
w_loop  = widgets.Checkbox(value=False, description="Digital loopback")
w_tx    = widgets.Dropdown(options=[("off", 0), ("frames (the same as the B210's)", 1), ("PRBS-15, no frames", 2)], value=0, description="FPGA transmits", layout=widgets.Layout(width="380px"))
w_att   = widgets.FloatSlider(value=30.0, min=20.0, max=89.75, step=0.25, description="TX atten (dB)", continuous_update=False, layout=widgets.Layout(width="520px"))
w_amp   = widgets.FloatSlider(value=0.5, min=0.05, max=1.0, step=0.05, description="TX amplitude", continuous_update=False, layout=widgets.Layout(width="520px"))
b_rx    = widgets.Button(description="Start receiver", button_style="success")
b_apply = widgets.Button(description="Apply", button_style="primary")
b_rxoff = widgets.Button(description="Stop receiver", button_style="warning")
b_start = widgets.Button(description="Start display", button_style="info")
b_stop  = widgets.Button(description="Stop display")
status  = widgets.Label(value="idle", layout=widgets.Layout(width="auto"))
errout  = widgets.Output(layout=widgets.Layout(border="1px solid #c0392b", max_height="200px", overflow="auto"))
image   = widgets.Image(format="png", width=840)
live    = Live(image, status)

import traceback
def guard(fn):
    def h(change=None):
        try: fn(change)
        except Exception as e:
            status.value = f"{type(e).__name__}: {e}"
            with errout: print(traceback.format_exc())                          # the whole error, with the line, below the controls
    return h

def apply_sync(_=None):
    pl = max(4, (int(w_pl.value) // 4) * 4); w_pl.value = pl; fl = pl + 64
    w_fl.value = f"Frame {fl}"; live.fl = fl
    rx.configure_sync(fl=fl, pl=pl, thr=w_thr.value, tol=w_tol.value, missmax=w_mm.value, guard=w_gd.value); rx.gate_enable(w_gate.value)
    if w_mode.value == "hw": rx.configure_acquisition(load=w_ld.value, nload=w_nld.value, nsw=w_nsw.value, acq_div=w_acqd.value)
    else: rx.configure_acquisition(load=0, nsw=0)                                    # the hardware acquisition is only used by its own start mode
    status.value = f"synchroniser set: frame {fl}, payload {pl}, threshold {w_thr.value}, tolerance {w_tol.value}, misses {w_mm.value}, guard {w_gd.value}, gate {'on' if w_gate.value else 'off'}; acquisition {'load ' + str(w_ld.value) + ', N ' + str(w_nld.value) + ', narrow after ' + str(w_nsw.value) + ' hits' if w_mode.value == 'hw' else 'off'}"

def do_start_receiver(_=None):
    live.paused = True; time.sleep(0.15)                      # the live thread must not touch the registers meanwhile
    try:
        live.last = None
        for h in (hist_f, hist_c, hist_h, hist_m): h[:] = [np.nan] * HIST
        vec.clear()
        if w_mode.value == "hw":
            rx.stop(); time.sleep(0.05); rx.configure(timing_bw=2 * np.pi / 400, phase_bw=2 * np.pi / 400, init_freq_hz=0.0); apply_sync(); rx.start()
            t0 = time.time(); sync = rx.wait_lock(1.0); t_sync = (time.time() - t0) * 1e3; ok = False
            while sync and time.time() - t0 < 1.5:
                time.sleep(0.02)
                if rx.locked(0.02): ok = True; break
            y = rx.sync_status()
            status.value = (f"hardware acquisition: frame sync {'LOCKED after %.1f ms' % t_sync if sync else 'not locked'}; {rx.ip.read(REG['SY_NLD'])} loads, Costas {rx._omega_hz():+.0f} Hz; receiver {'LOCKED' if ok else 'not locked'} after {time.time() - t0:.2f} s"
                            + ("" if sync else " (is the flowgraph transmitting? same payload?)"))
        elif w_mode.value == "search":
            rx.stop(); apply_sync()
            r = rx.acquire(track_div=400)
            apply_sync()
            ok = rx.wait_lock(1.0)
            status.value = (f"carrier search: {'locked' if r['locked'] else 'NOT locked'} after {r['seconds']:.2f} s (hint {r['hint_hz']}); frame sync: {'LOCKED' if ok else 'not locked (is the flowgraph transmitting? same payload?)'}")
        else:
            rx.stop(); time.sleep(0.05); rx.configure(timing_bw=2 * np.pi / 1600, phase_bw=2 * np.pi / 1600, init_freq_hz=0.0); apply_sync(); rx.start()
            t0 = time.time(); ok = rx.wait_lock(1.0)
            status.value = f"Costas unlocked (2 pi/1600, W0 = 0): frame sync {'LOCKED after %.1f ms' % ((time.time() - t0) * 1e3) if ok else 'not locked (is the flowgraph transmitting? same payload?)'}"
    finally:
        live.paused = False

def do_tx(change=None):
    if w_tx.value == 1: ad.set_tx_atten_db(w_att.value); tx.start_frames(payload=max(4, (int(w_pl.value) // 4) * 4), amp=w_amp.value)       # the payload of the frames = the Payload control
    elif w_tx.value == 2: ad.set_tx_atten_db(w_att.value); tx.start(amp=w_amp.value)
    else: tx.off(); p501_radio.quiet(ad, TX_ATTEN0)

b_rx.on_click(guard(do_start_receiver)); b_apply.on_click(guard(apply_sync)); b_rxoff.on_click(guard(lambda b: rx.stop()))
b_start.on_click(guard(lambda b: live.start())); b_stop.on_click(guard(lambda b: live.stop()))
w_gate.observe(guard(lambda c: rx.gate_enable(c["new"])), names="value")
w_rxg.observe(guard(lambda c: ad.set_rx_manual_gain(c["new"])), names="value")
w_mode.observe(guard(lambda c: None), names="value")
w_loop.observe(guard(lambda c: p501_radio.loopback(ad, c["new"])), names="value")
w_tx.observe(guard(do_tx), names="value")
w_att.observe(guard(lambda c: ad.set_tx_atten_db(c["new"]) if w_tx.value else None), names="value")
w_amp.observe(guard(lambda c: tx.set(amp=c["new"]) if w_tx.value else None), names="value")

display(widgets.VBox([widgets.HBox([b_rx, b_apply, b_rxoff, b_start, b_stop, status]), widgets.HBox([w_mode, w_pl, w_fl]), widgets.HBox([w_ld, w_nld, w_nsw, w_acqd]), widgets.HBox([w_thr, w_tol]), widgets.HBox([w_mm, w_gd]), w_gate, w_rxg,
                      widgets.HBox([w_loop, w_tx]), w_att, w_amp, errout, image]))
''')

md("""
### Check the controls (optional)

Moves the controls from Python, the way clicks would, in the digital loopback (PRBS only, no frames): the synchroniser must not lock, the registers must follow the controls.
""")
code('''
w_loop.value = True; w_att.value = 20.0; w_tx.value = 2; time.sleep(0.5)
w_pl.value = 192; w_thr.value = 120; w_tol.value = 2; w_mm.value = 5; w_gd.value = 3; w_gate.value = True
b_apply.click(); time.sleep(0.2)
check("apply writes the registers", [rx.ip.read(REG[k]) for k in ("SY_FL", "SY_PL", "SY_THR", "SY_TOL", "SY_MISSMAX", "SY_GUARD")] == [256, 192, 120, 2, 5, 3], f"{[rx.ip.read(REG[k]) for k in ('SY_FL', 'SY_PL', 'SY_THR', 'SY_TOL', 'SY_MISSMAX', 'SY_GUARD')]}")
w_mode.value = "hw"; b_apply.click(); time.sleep(0.2)
check("hardware acquisition registers follow the controls", [rx.ip.read(REG[k]) for k in ("SY_LOAD", "SY_NLOAD", "SY_NSW")] == [1, 8, 4], f"{[rx.ip.read(REG[k]) for k in ('SY_LOAD', 'SY_NLOAD', 'SY_NSW')]}")
w_mode.value = "nocostas"; b_start.click(); b_rx.click(); time.sleep(1.0)
check("the other modes switch the hardware acquisition off", [rx.ip.read(REG[k]) for k in ("SY_LOAD", "SY_NSW")] == [0, 0], f"{[rx.ip.read(REG[k]) for k in ('SY_LOAD', 'SY_NSW')]}")
check("sync-only start runs, PRBS-only data: not locked", rx.ip.read(REG["SY_STATUS"]) & 1 == 0 and "not locked" in status.value, status.value)
check("gate closed: the checker does not count", rx.ip.read(REG["BITS"]) == 0, f"bits {rx.ip.read(REG['BITS'])}")
w_gate.value = False; time.sleep(0.5)
check("gate off: the checker counts everything", rx.ip.read(REG["BITS"]) > 100000, f"bits {rx.ip.read(REG['BITS']):,}")
w_gate.value = True
b_stop.click(); display(IPImage(image.value))
# the FPGA transmitter's frames, with the controls
w_tx.value = 0; time.sleep(0.2); w_pl.value = PAYLOAD; w_thr.value = 140; w_tol.value = 1; w_mm.value = 3; w_gd.value = 2; w_mode.value = "hw"; apply_sync(); w_tx.value = 1; time.sleep(0.3)
b_rx.click(); time.sleep(0.6)
check("FPGA frames with the controls: hardware acquisition locks", "frame sync LOCKED" in status.value and "receiver LOCKED" in status.value, status.value)
w_tx.value = 0; w_loop.value = False; b_rxoff.click()
w_pl.value = PAYLOAD; w_thr.value = 140; w_tol.value = 1; w_mm.value = 3; w_gd.value = 2; apply_sync()
check("transmitter off again", not tx.enabled, f"enabled = {tx.enabled}")
''')

md("""
## Try it: the B210 frames

1. Start the B210 flowgraph `qpsk_b210_frame_tx.grc` (`payload_syms` = the *Payload* control, TX gain 80), switch **Transmit** ON.
2. Press **Start receiver** (*Hardware acquisition*), then **Start display**: the display should say *FRAME SYNC LOCKED*, the frames found per second ~937 (for 960), misses 0, and the payload mismatches near 0.
3. Move the B210 carrier in the flowgraph (`freq` 915.03e6, 914.94e6, 915.1e6) and press *Start receiver* again: the hardware acquisition locks at every offset up to +-110 kHz, where the Python search often fails. Try *Sync only (Costas unlocked)*: the constellation spins but the sync still locks; the purple frequency is the offset from the preamble.
4. Lower the **B210 TX gain** in the flowgraph (80 -> 76 -> 72 -> 68): the data stop decoding first, the frames are still found down to about 72 dB. Or lower the **RX gain** here.
5. Change *Payload* in the flowgraph and here, and see the lock follow. Stop the flowgraph: after 3 missed frames the lock is lost.

**Without the B210:** tick *Digital loopback*, set *FPGA transmits* to *frames*, press *Start receiver* (hardware acquisition): the frame sync and the receiver lock in milliseconds and the payload BER is 0; for the air, untick *Digital loopback* and use TX atten 20 to 30 dB.

The cells below do the same measurements automatically (experiments 1 to 4 need the B210 transmitting frames at 80 dB; experiment 5 needs no B210).
""")

md("""
## Experiment 1: the frequency offset from the preamble, against the Costas loop (B210 frames)

The frequency from `arg(C)` over 300 frames, with the Costas loop locked (`rx.acquire()`) and with it unlocked (loops 2 pi/1600). Earlier results: the preamble reads 1 to 3.5 kHz below the Costas loop (0.7 to 9 %), with a scatter of about 1 kHz per frame.
""")
code('''
def freq_experiment(n=300):
    live.stop(); live.paused = True; rx.configure_acquisition(load=0, nsw=0)
    out = {}
    for mode in ("Costas locked", "Costas unlocked"):
        rx.stop(); time.sleep(0.05); rx.configure_sync(fl=PAYLOAD + 64, pl=PAYLOAD); rx.gate_enable(True)
        if mode == "Costas locked":
            r = rx.acquire(track_div=400); rx.configure_sync(fl=PAYLOAD + 64, pl=PAYLOAD); rx.gate_enable(True)
        else:
            rx.configure(timing_bw=2 * np.pi / 1600, phase_bw=2 * np.pi / 1600, init_freq_hz=0.0); rx.start()
        ok = rx.wait_lock(1.0)
        if not ok:
            print(f"{mode}: no frame sync (start the flowgraph with Transmit ON, same payload)"); continue
        time.sleep(0.2); f, q, sd = rx.corr_freq_hz(n=n, period_s=0.0013); om = rx._omega_hz(); y = rx.sync_status()
        out[mode] = (f, sd, om, y)
        print(f"{mode:<16} sync locked; frequency from the preamble {f:+8.0f} Hz (std of single frames {sd:5.0f} Hz); Costas frequency {om:+8.0f} Hz; peaks {y['peaks']:,}, hits {y['hits']:,}, misses {y['misses']}, false {y['false']}")
    rx.stop(); live.paused = False
    return out

fres = freq_experiment()
''')

md("""
## Experiment 2: detection against the receive gain (B210 frames at 80 dB)

Lowering the P501's RX gain index lowers the signal level at the ADC the way a lower B210 TX gain would (without touching the flowgraph). For each RX gain the cell starts the receiver with the Costas loop unlocked, waits for the lock and counts 2 s:
frames found against the expected number, misses, false peaks, losses. Earlier results (B210 TX gain instead): every frame found down to 72 dB, some misses at 68 dB, none at 60 dB.
""")
code('''
def gain_experiment(gains=(70, 60, 55, 50, 45, 40), seconds=2.0):
    live.stop(); live.paused = True; rx.configure_acquisition(load=0, nsw=0)
    fl = PAYLOAD + 64; print(f"{'RX gain':>8}{'locked after':>14}{'frames expected':>17}{'hits':>8}{'misses':>8}{'false':>7}{'lost':>6}{'quality':>9}")
    rows = []
    for g in gains:
        ad.set_rx_manual_gain(g); time.sleep(0.2)
        rx.stop(); time.sleep(0.05); rx.configure(timing_bw=2 * np.pi / 1600, phase_bw=2 * np.pi / 1600, init_freq_hz=0.0); rx.configure_sync(fl=fl, pl=PAYLOAD); rx.gate_enable(True); rx.start()
        t0 = time.time(); ok = rx.wait_lock(0.5); tl = (time.time() - t0) * 1e3
        y0 = rx.sync_status(); time.sleep(seconds); y1 = rx.sync_status(); exp = seconds * SYMBOL_RATE / fl
        rows.append((g, ok, y1["hits"] - y0["hits"], y1["misses"] - y0["misses"], y1["false"] - y0["false"], y1["lost"] - y0["lost"]))
        print(f"{g:>8}{(f'{tl:.1f} ms' if ok else 'no lock'):>14}{exp:>17.0f}{y1['hits'] - y0['hits']:>8}{y1['misses'] - y0['misses']:>8}{y1['false'] - y0['false']:>7}{y1['lost'] - y0['lost']:>6}{y1['quality']:>9.2f}")
    ad.set_rx_manual_gain(RX_GAIN); rx.stop(); live.paused = False
    return rows

grows = gain_experiment()
''')

md("""
## Experiment 3: lock time from a cold start

10 cold starts with the wide loops: the time until the tracker has locked (two preambles one frame apart), polled without a pause. Earlier: median 1.8 ms.
""")
code('''
def lock_time_experiment(n=10, div=100):
    live.stop(); live.paused = True; rx.configure_acquisition(load=0, nsw=0)
    ts = []
    for _ in range(n):
        rx.stop(); time.sleep(0.05); rx.configure(timing_bw=2 * np.pi / div, phase_bw=2 * np.pi / div); rx.configure_sync(fl=PAYLOAD + 64, pl=PAYLOAD); rx.gate_enable(True)
        rx.start(); t0 = time.time(); ok = False
        while time.time() - t0 < 0.3 and not ok: ok = bool(rx.ip.read(REG["SY_STATUS"]) & 1)
        ts.append((time.time() - t0) * 1e3 if ok else float("nan"))
    ts = np.array(ts)
    if np.isnan(ts).all(): print("no frame sync in any start (start the flowgraph with Transmit ON, same payload)")
    else: print(f"lock time: median {np.nanmedian(ts):.1f} ms, min {np.nanmin(ts):.1f}, max {np.nanmax(ts):.1f} ms; not locked in {int(np.isnan(ts).sum())} of {n} starts   (a frame is {(PAYLOAD + 64) / 960.0:.2f} ms)")
    rx.stop(); live.paused = False
    return ts

lts = lock_time_experiment()
''')
md("""
## Experiment 4: hardware acquisition against the Python carrier search (B210 frames)

`trials` cold starts each way, at the offset of the B210 carrier as it is now (change `freq` in the flowgraph and run the cell again: 915.03e6, 914.94e6, 915.07e6, 915.1e6). *H* = hardware acquisition (`rx.acquire_hw()`), *P* = the Python search (`rx.acquire()`); after each start the cell counts
1 s of payload (gated): bits, mismatches, the constellation spread and the Costas frequency. Earlier results (24 starts at six offsets from -91 to +110 kHz): hardware 24 of 24 locked, payload BER 1e-6 to 1e-4; Python search locked in about a third.
""")
code('''
def acq_experiment(trials=5):
    live.stop(); live.paused = True
    print(f"{'way':<4}{'locked':>8}{'seconds':>9}{'payload bits':>14}{'mismatches':>12}{'BER':>10}{'spread':>8}{'Costas':>12}")
    out = {"H": [], "P": []}
    for t in range(trials):
        for way in ("P", "H"):
            if way == "P":
                rx.configure_acquisition(load=0, nsw=0); rx.stop(); rx.configure(timing_bw=2 * np.pi / 100, phase_bw=2 * np.pi / 100); rx.configure_sync(fl=PAYLOAD + 64, pl=PAYLOAD); rx.gate_enable(True)
                t0 = time.time(); r = rx.acquire(track_div=400); sec = time.time() - t0; ok = r["locked"]
            else:
                r = rx.acquire_hw(fl=PAYLOAD + 64, pl=PAYLOAD); sec = r["seconds"]; ok = r["locked"]
            time.sleep(0.2); s0 = rx.stats(); time.sleep(1.0); s1 = rx.stats(); z = rx.capture()
            nb, nm = s1["bits"] - s0["bits"], s1["mismatches"] - s0["mismatches"]; out[way].append((ok, nm / 3.0 / max(nb, 1)))
            print(f"{way:<4}{str(ok):>8}{sec:>9.2f}{nb:>14,}{nm:>12,}{nm / 3.0 / max(nb, 1):>10.1e}{soft_quality(z)[1]:>7.1f}d{rx._omega_hz():>+10.0f}Hz")
    rx.configure_acquisition(load=0, nsw=0); rx.stop(); live.paused = False
    for way in ("H", "P"): print(f"{way}: locked {sum(o for o, _ in out[way])}/{trials}, median BER {np.median([b for _, b in out[way]]):.1e}")
    return out

acq = acq_experiment()
''')

md("""
## Experiment 5: all in the FPGA, over the air (no B210)

The P501's transmitter sends frames from TX1, the receiver at RX1 (antennas a few centimetres apart) finds them and counts the payload errors; the TX attenuation is stepped up (the signal gets weaker). **The B210 must not transmit.**
Earlier results (RX gain 70): 20 and 30 dB: every frame found, no bit error in 3.5 Mbit; 40 dB: frames found, BER 6e-2; 45 dB: frames lost; 50 dB and more: nothing.
""")
code('''
def air_experiment(attens=(20.0, 30.0, 40.0, 45.0, 50.0), seconds=2.0):
    live.stop(); live.paused = True; fl = PAYLOAD + 64
    ad.set_rx_manual_gain(70); p501_radio.loopback(ad, False)
    print(f"{'TX atten':>9}{'sync':>7}{'frames sent':>13}{'hits':>7}{'misses':>8}{'false':>7}{'lost':>6}{'payload bits':>14}{'mismatches':>12}{'BER':>10}{'spread':>8}")
    for att in attens:
        tx.off(); rx.stop(); ad.set_tx_atten_db(att); tx.start_frames(payload=PAYLOAD, amp=0.5); time.sleep(0.2)
        rx.configure(timing_bw=2 * np.pi / 400, phase_bw=2 * np.pi / 400); rx.configure_sync(fl=fl, pl=PAYLOAD); rx.configure_acquisition(load=1, nload=8, nsw=4); rx.gate_enable(True); rx.start()
        ok = rx.wait_lock(1.0); time.sleep(0.4); s0 = rx.stats(); y0 = rx.sync_status(); time.sleep(seconds); s1 = rx.stats(); y1 = rx.sync_status(); z = rx.capture()
        nb, nm = s1["bits"] - s0["bits"], s1["mismatches"] - s0["mismatches"]
        print(f"{att:>7.0f}dB{('locked' if ok else '-'):>7}{seconds * SYMBOL_RATE / fl:>13.0f}{y1['hits'] - y0['hits']:>7}{y1['misses'] - y0['misses']:>8}{y1['false'] - y0['false']:>7}{y1['lost'] - y0['lost']:>6}{nb:>14,}{nm:>12,}{nm / 3.0 / max(nb, 1):>10.1e}{soft_quality(z)[1]:>7.1f}d")
    tx.off(); rx.configure_acquisition(load=0, nsw=0); rx.stop(); p501_radio.quiet(ad, TX_ATTEN0); live.paused = False

air_experiment()
''')

md("""
## Stop and silence

Run this when you are done (or after an error): stops the display and the receiver, turns the transmitter off and the digital loopback off, and sets the maximum TX attenuation.
The AD9361 transmit chain stays powered (a weak LO carrier remains); loading another overlay or powering down gives complete silence.
""")
code('''
try:
    live.stop()
finally:
    rx.gate_enable(False); tx.off(); rx.stop()
    p501_radio.loopback(ad, False)
    p501_radio.quiet(ad, TX_ATTEN0)
    print("transmitter off, receiver stopped, loopback off, TX attenuation %.2f dB" % TX_ATTEN0)
''')

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open(OUT, "w"), indent=1)
print("wrote", OUT, "-", len(cells), "cells")
