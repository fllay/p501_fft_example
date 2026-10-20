#!/usr/bin/env python3
"""Writes notebook/P501_QPSK_FLL_Live.ipynb: the P501 side of the interactive QPSK link test with the FLL receiver (overlay p501_qpsk_trx_fll),
the counterpart of notebook/P501_QPSK_Link_Live.ipynb (tutorial/qpsk/p501_rx/make_notebook.py). The B210 side is the same GNU Radio flowgraphs.     python3 make_notebook_fll.py"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "notebook", "P501_QPSK_FLL_Live.ipynb"))
cells = []


def md(text): cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)})
def code(text): cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip("\n").splitlines(True)})


md("""
# Live: the P501's FPGA QPSK modem with the FLL receiver against a B210 and GNU Radio

The same link test as `P501_QPSK_Link_Live.ipynb`, with the receiver of the overlay **`p501_qpsk_trx_fll`**: the chain of the GNU Radio flowgraph,
**FLL band-edge -> polyphase matched filter and timing loop -> Costas loop**, all in the FPGA. 915.0 MHz, 3.84 MSPS, 960 ksym/s differential QPSK, PRBS-15 data.

| direction | transmitter | receiver | what you watch |
|---|---|---|---|
| **A: B210 -> P501** | the B210 (GNU Radio flowgraph `qpsk_b210_tx.grc`, *Transmit ON*) | the **FPGA receiver with the FLL** | here: constellation, bit errors counted in the FPGA, and the **three frequencies**: FLL, Costas, and their sum, the carrier offset of the signal |
| **B: P501 -> B210** | the **FPGA transmitter** of this overlay (checkbox *Transmit*) | the B210 (flowgraph `qpsk_b210_rx.grc`) | in GNU Radio: constellation, BER box, spectrum |

**What is new compared with the notebook without the FLL**
* The frequency is found by the **FLL** (coarse, wide) and followed by the **Costas loop** (fine). The carrier offset of the signal is `Costas - FLL` (the FLL derotates, so its frequency has the opposite sign).
* **Start receiver** calls `rx.acquire_fll()`: no frequency hints. FLL and Costas start wide at zero offset, then both are narrowed live.
* The FLL's frequency is noisy (data dependent, +-0.5 to 1 kHz), and the Costas loop follows it with the opposite sign. **Freeze FLL** loads the FLL with its mean and stops its loop (a handover): watch the two curves go quiet.
* The experiment at the end compares the pull-in time with and without the FLL.

**Before you start**
* Overlay `p501_qpsk_trx_fll` copied to `/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fll/` (with `p501_qpsk.py`, `p501_qpsk_rx.py`, `p501_qpsk_rx_fll.py`), and the notebooks of `p501_fft_dds` (for `p501_radio.py`).
* Antennas on TX1 / RX1 of the P501 and on the TX/RX and RX2 ports of the B210, a few centimetres apart. **Very low power** (B210 TX gain 80 dB at most). Check the rules where you are before transmitting.
* **One direction at a time.** The transmit flowgraph starts with *Transmit OFF*, this notebook with *Transmit* unticked. **Start the transmitter first, then press Start receiver.**
* Everything ends quiet: the last cell (*Stop and silence*) turns the transmitter off and sets the TX attenuation to its maximum.
""")

md("## Configuration, overlay and bring-up")
code('''
BIT       = "/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fll/p501_qpsk_trx_fll.bit"   # transmitter + receiver with the FLL in one overlay (the .hwh next to it)
FS        = 3_840_000          # sample rate
LO        = 915_000_000        # carrier, Hz: the B210 flowgraph uses the same
RX_GAIN   = 70                 # P501 RX gain-table index 0..76: 70 for the B210's weak signal through the air
TX_ATTEN0 = 89.75              # TX attenuation (dB) at the start and at the end: the transmitter is silent
''')
code('''
import sys, time, os, io, threading
import numpy as np
from pynq import Overlay

sys.path.insert(0, '/home/xilinx/jupyter_notebooks')
sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds')            # p501_radio.py, p501_dds.py
sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fll')       # p501_qpsk.py, p501_qpsk_rx.py, p501_qpsk_rx_fll.py
import p501_radio
from p501_qpsk import P501QpskTx
from p501_qpsk_rx import soft_quality, constellation_ok, UNIT
from p501_qpsk_rx_fll import P501QpskRxFll

results = {}
def check(name, ok, detail):
    results[name] = (bool(ok), detail)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

ol = Overlay(BIT)                                  # programs the PL
tx = P501QpskTx(ol.qpsk_regs, FS)                  # transmitter registers at 0x9C460000: enable, amplitude
rx = P501QpskRxFll(ol.qpsk_rx)                     # receiver registers at 0x9C470000 (the constructor checks the ID 0xDD520002: the receiver WITH the FLL)
ad = p501_radio.bring_up(ol, LO, 4_000_000, TX_ATTEN0, RX_GAIN)     # the AD9361 over SPI; TX attenuation at its maximum during the calibrations
tx.off(); rx.stop()

a_tx, a_rx = ol.ip_dict["qpsk_regs"]["phys_addr"], ol.ip_dict["qpsk_rx"]["phys_addr"]
check("both blocks in the overlay", a_tx == 0x9C460000 and a_rx == 0x9C470000, f"qpsk_regs at 0x{a_tx:08X}, qpsk_rx at 0x{a_rx:08X}")
check("AD9361 up", ad.info["ok"], f"LO locks {ad.info['rx_lock']}/{ad.info['tx_lock']}, ENSM 0x{ad.info['ensm']:X}, calibrations {ad.info['calibrations']}")
''')

md("""
## Helpers

`restart_receiver()` stops, loads the loop gains of the timing and Costas loops and of the FLL, and starts. `rx.acquire_fll()` (in `p501_qpsk_rx_fll.py`) does it in the robust way:
FLL gain 0.002 rad per symbol and Costas / timing loops 2 pi/100 until the Costas frequency has settled and the receiver is locked (no new mismatch and a sane constellation), then the FLL gain 0.0003 and the loops 2 pi/400.
""")
code('''
def restart_receiver(acq_div=100, fll_gain=0.002, use_fll=True, f0_hz=0.0):
    """Stop, load the gains, start (cold start). use_fll=False holds the FLL at f0_hz: the receiver of the notebook without the FLL."""
    rx.stop()
    rx.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=0.0)
    rx.ip.write(0x60, int(round(f0_hz / FS * 2 ** 32)) & 0xFFFFFFFF)               # FLL_F0: the starting frequency of the FLL
    rx.set_fll(fll_gain); rx.fll_enable(use_fll)
    rx.start()
''')

md("""
## Self-test: FPGA transmitter -> FPGA receiver, inside the AD9361 (digital loopback)

No antennas, no B210. Both ends use the same clock, so there is no offset: the FLL must stay near 0 Hz. If this passes, the overlay, the AD9361 clocks, the transmitter, the FLL receiver and the PRBS checker work.
""")
code('''
p501_radio.loopback(ad, True)
restart_receiver(400)                                  # 2 pi/400 loops, FLL gain 0.002
tx.start(amp=0.5)                                      # PRBS-15 DQPSK from the FPGA transmitter
time.sleep(0.5); s0 = rx.stats()                       # the pull-in is over after a few milliseconds
time.sleep(2.0); s1 = rx.stats()
new_err = s1["mismatches"] - s0["mismatches"]; bits = s1["bits"] - s0["bits"]
f_hz, ppm = rx.offsets(n=200)
fl = rx.fll_status(); z = rx.capture(); mag, spread = soft_quality(z)
tx.off(); rx.stop(); p501_radio.loopback(ad, False)

check("loopback: bits checked", bits > 3_000_000, f"{bits:,} bits in 2 s ({bits / 2 / 1e6:.2f} Mbit/s)")
check("loopback: no bit error after the pull-in", new_err == 0, f"{new_err} mismatches in {bits:,} bits ({s0['mismatches']} during the pull-in = about {s0['mismatches'] // 3} bit errors)")
check("loopback: constellation", constellation_ok(z), f"mean |z| {mag:.2f}, angular spread {spread:.1f} degrees")
check("loopback: no offsets (same clock)", abs(f_hz) < 600 and abs(ppm) < 20, f"total carrier offset {f_hz:+.1f} Hz (FLL {fl['fll_hz']:+.0f} Hz now), clock {ppm:+.2f} ppm")
check("loopback: FLL ran, never late", fl["blocks"] > 1_000_000 and fl["late"] == 0, f"{fl['blocks']:,} blocks measured, late {fl['late']}")
check("loopback: no overruns", s1["overruns"] == 0, f"overruns {s1['overruns']}")
''')

md("""
## The live machinery

* `render()` draws one picture with NumPy and Pillow: the **constellation** (1024 soft symbols from the capture RAM), the **status** and three strips: the **total carrier offset** (`Costas - FLL`), the **FLL** (green) and **Costas** (blue) frequencies on one scale, and the **mismatches per second**.
* `Live` runs `read registers -> read capture RAM -> picture` in a background thread and puts the PNG into an image widget, so the controls stay responsive.
""")
code('''
import ipywidgets as widgets
from IPython.display import display, Image as IPImage
from PIL import Image as PILImage, ImageDraw, ImageFont

W, H = 840, 560
CX, CY, SC = 215, 220, 76                           # constellation centre and pixels per unit (axes +-2.5)
FONT = ImageFont.load_default()
HIST = 80
hist_t = [np.nan] * HIST; hist_fl = [np.nan] * HIST; hist_co = [np.nan] * HIST; hist_m = [np.nan] * HIST   # total offset, FLL, Costas (Hz), mismatches per second

def base_frame():
    img = PILImage.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(img)
    d.rectangle([CX - 2.5 * SC, CY - 2.5 * SC, CX + 2.5 * SC, CY + 2.5 * SC], outline=(90, 90, 90))
    for u in (-2, -1, 0, 1, 2):
        d.line([CX + u * SC, CY - 2.5 * SC, CX + u * SC, CY + 2.5 * SC], fill=(225, 225, 225)); d.line([CX - 2.5 * SC, CY - u * SC, CX + 2.5 * SC, CY - u * SC], fill=(225, 225, 225))
    for sx in (-1, 1):
        for sy in (-1, 1):                                                   # the four decision points
            x, y = CX + sx * 1.24 * SC, CY - sy * 1.24 * SC
            d.line([x - 5, y, x + 5, y], fill=(200, 80, 80)); d.line([x, y - 5, x, y + 5], fill=(200, 80, 80))
    d.text((CX - 70, CY + 2.5 * SC + 6), "soft symbols after the Costas loop", fill=(60, 60, 60), font=FONT)
    return img
BASE = base_frame()

def strip(d, x0, y0, w, h, series, label, lo=None, hi=None):
    """series: list of (data, colour). Without lo/hi the scale follows the data (at least 2 kHz span)."""
    d.rectangle([x0, y0, x0 + w, y0 + h], outline=(150, 150, 150)); d.text((x0, y0 - 12), label, fill=(60, 60, 60), font=FONT)
    allv = np.concatenate([np.asarray(s, dtype=float) for s, _ in series]); allv = allv[~np.isnan(allv)]
    if lo is None:
        c = float(np.median(allv)) if len(allv) else 0.0; span = max(2000.0, 1.2 * (float(allv.max() - allv.min()) if len(allv) else 0.0))
        lo, hi = c - span / 2, c + span / 2
    for data, color in series:
        pts = [(x0 + i * w / (len(data) - 1), y0 + h - (min(max(v, lo), hi) - lo) / (hi - lo) * h) for i, v in enumerate(data) if not np.isnan(v)]
        if len(pts) > 1: d.line(pts, fill=color, width=1)
    d.text((x0 + w + 4, y0 - 2), f"{hi:.0f}", fill=(100, 100, 100), font=FONT); d.text((x0 + w + 4, y0 + h - 9), f"{lo:.0f}", fill=(100, 100, 100), font=FONT)

def render(z, st, locked, mrate, note=""):
    img = BASE.copy(); d = ImageDraw.Draw(img)
    zn = np.asarray(z) / UNIT
    for a, b in zip(zn.real, zn.imag):
        x, y = CX + a * SC, CY - b * SC
        if abs(a) < 2.5 and abs(b) < 2.5: d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=(31, 119, 180))
    mag, spread = soft_quality(z)
    X = 450
    d.text((X, 20), "LOCKED" if locked else "NOT LOCKED", fill=(30, 140, 50) if locked else (200, 40, 40), font=FONT)
    d.text((X, 36), note, fill=(110, 110, 110), font=FONT)
    lines = [f"bits checked {st['bits']:>9,}   mismatches {st['mismatches']:>9,} (about {st['mismatches'] // 3:,} errors)",
             f"BER estimate {st['ber_estimate']:.1e}   overruns {st['overruns']}   FLL late {st['late']}",
             f"FLL     {st['fll_hz']:+9.1f} Hz   {'loop on' if st['enabled'] else 'frozen'}   error {st['err']:+.2f}",
             f"Costas  {st['costas_hz']:+9.1f} Hz",
             f"carrier offset (Costas - FLL) {st['carrier_offset_hz']:+9.1f} Hz",
             f"clock offset {st['clock_offset_ppm']:+8.1f} ppm (instantaneous)",
             f"AGC gain {st['agc_gain']:.2f}   |z| {mag:.2f}   spread {spread:.1f} deg"]
    for i, l in enumerate(lines): d.text((X, 62 + 16 * i), l, fill=(0, 0, 0), font=FONT)
    strip(d, X, 205, 340, 80, [(hist_t, (200, 120, 20))], "carrier offset = Costas - FLL (Hz)")
    strip(d, X, 325, 340, 80, [(hist_fl, (30, 150, 60)), (hist_co, (31, 119, 180))], "FLL (green) and Costas (blue) frequency (Hz)")
    strip(d, X, 445, 340, 80, [(hist_m, (180, 40, 40))], "mismatches per second, 0 .. 1000", 0, 1000)
    buf = io.BytesIO(); img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()

class Live:
    """Background thread: registers + capture RAM -> picture."""
    def __init__(self, image, status):
        self.image, self.status = image, status
        self.running, self.thread, self.frames = False, None, 0
        self.last_m, self.last_t = 0, time.time()
        self.locked, self.st = False, None
        self.paused = False                                      # set while acquire_fll() or an experiment uses the registers
    def _run(self):
        t_rate = time.time(); n_rate = 0; rate = 0.0
        while self.running:
            if self.paused:
                time.sleep(0.05); continue
            try:
                st = rx.stats()
                if st["running"]: z = rx.capture(); self.z = z                  # capture() arms with CTRL = 1, 3: not while the receiver is stopped
                else: z = getattr(self, "z", np.zeros(1024, dtype=complex))
                now = time.time(); dt = max(now - self.last_t, 1e-3)
                mrate = (st["mismatches"] - self.last_m) / dt if st["mismatches"] >= self.last_m else 0.0
                self.last_m, self.last_t = st["mismatches"], now
                self.locked = bool(st["running"] and mrate == 0 and st["bits"] > 0 and constellation_ok(z))
                for h, v in ((hist_t, st["carrier_offset_hz"]), (hist_fl, st["fll_hz"]), (hist_co, st["costas_hz"]), (hist_m, mrate)): h.pop(0); h.append(v)
                self.st = st
                self.image.value = render(z, st, self.locked, mrate, f"{rate:.1f} pictures/s")
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

A few pictures of the digital loopback, to check the machinery before a browser is involved.
""")
code('''
p501_radio.loopback(ad, True); restart_receiver(100); tx.start(amp=0.5); time.sleep(0.3)
img_w, st_w = widgets.Image(format="png"), widgets.Label()
lv = Live(img_w, st_w)
lv.start(); time.sleep(3); lv.stop()
fps = lv.frames / 3.0
check("live pictures", lv.frames > 4 and len(img_w.value) > 2000, f"{lv.frames} pictures in 3 s ({fps:.1f}/s), status: {st_w.value}")
check("live: locked in the loopback", lv.locked, f"locked = {lv.locked}")
display(IPImage(img_w.value))
tx.off(); rx.stop(); p501_radio.loopback(ad, False)
''')

md("""
## Controls

**Receiver (direction A)**
* **Start receiver**: `rx.acquire_fll()`. FLL gain *FLL wide* and loops `2 pi / N` (*Acquisition N*) from zero offset, no hints; after the lock the FLL gain goes to *FLL narrow* and the loops to `2 pi / M` (*Tracking M*). Status line: tries, time, and the three frequencies.
* **Use the FLL** (loop on): untick it to hold the FLL at 0 Hz: the receiver is then the one of the notebook without the FLL (Costas pull-in only). Press **Start receiver** again to see the difference at the start.
* **Freeze FLL**: loads the FLL with the mean of its frequency and stops its loop (handover). The Costas loop keeps tracking: the offset stays right, the FLL/Costas curves go quiet.
* **Live loop N**, **Live FLL gain**: change the timing/Costas loops and the FLL's integral gain while the receiver runs.
* **RX gain**: the AD9361's receive gain index (70 is right for the B210 at 80 dB). **Digital loopback**: the FPGA transmitter into the FPGA receiver without antennas.

**Transmitter (direction B)**: **P501 transmits** (off at the start; do not tick it while the B210's *Transmit* is ON), **TX attenuation** (20 dB .. 89.75 dB; start at 40 dB), **Amplitude**.

**Start display / Stop display**: the live picture; stopping it does not stop the transmitter or the receiver.

To test a larger offset, set the frequency of the B210 flowgraph a few tens of kHz away from 915.0 MHz (for instance 915.03 MHz): the FLL takes it out, the Costas frequency stays small.
""")
code('''
w_acq   = widgets.Dropdown(options=[50, 100, 200, 400], value=100, description="Acquisition N", layout=widgets.Layout(width="200px"))
w_trk   = widgets.Dropdown(options=[("200", 200), ("400", 400), ("800", 800), ("1600", 1600)], value=400, description="Tracking M", layout=widgets.Layout(width="200px"))
w_fw    = widgets.Dropdown(options=[0.001, 0.002, 0.004], value=0.002, description="FLL wide", layout=widgets.Layout(width="200px"))
w_fn    = widgets.Dropdown(options=[0.0001, 0.0003, 0.001], value=0.0003, description="FLL narrow", layout=widgets.Layout(width="200px"))
w_usefll = widgets.Checkbox(value=True, description="Use the FLL (loop on)", layout=widgets.Layout(width="300px"))
w_live  = widgets.IntSlider(value=400, min=50, max=1600, step=10, description="Live loop N", continuous_update=False, layout=widgets.Layout(width="520px"))
w_lfll  = widgets.FloatLogSlider(value=0.0003, base=10, min=-4.5, max=-2, step=0.05, description="Live FLL gain", continuous_update=False, readout_format=".5f", layout=widgets.Layout(width="520px"))
w_rxg   = widgets.IntSlider(value=RX_GAIN, min=0, max=76, description="RX gain", continuous_update=False, layout=widgets.Layout(width="520px"))
w_tx    = widgets.Checkbox(value=False, description="P501 transmits (direction B)")
w_att   = widgets.FloatSlider(value=40.0, min=20.0, max=89.75, step=0.25, description="TX atten (dB)", continuous_update=False, layout=widgets.Layout(width="520px"))
w_amp   = widgets.FloatSlider(value=0.5, min=0.05, max=1.0, step=0.05, description="TX amplitude", continuous_update=False, layout=widgets.Layout(width="520px"))
w_loop  = widgets.Checkbox(value=False, description="Digital loopback")
b_rx    = widgets.Button(description="Start receiver", button_style="success")
b_rxoff = widgets.Button(description="Stop receiver", button_style="warning")
b_frz   = widgets.Button(description="Freeze FLL", button_style="primary")
b_start = widgets.Button(description="Start display", button_style="info")
b_stop  = widgets.Button(description="Stop display")
status  = widgets.Label(value="idle")
image   = widgets.Image(format="png", width=840)
live    = Live(image, status)

def guard(fn):
    def h(change=None):
        try: fn(change)
        except Exception as e: status.value = f"{type(e).__name__}: {e}"
    return h

def do_start_receiver(_=None):
    live.paused = True; time.sleep(0.15)                      # the live thread must not touch the registers meanwhile
    try:
        live.last_m, live.last_t = 0, time.time()
        for h in (hist_t, hist_fl, hist_co, hist_m): h[:] = [np.nan] * HIST
        if w_usefll.value:
            r = rx.acquire_fll(wide_fll=w_fw.value, narrow_fll=w_fn.value, acq_div=w_acq.value, track_div=w_trk.value)
            status.value = (f"locked after {r['tries']} try(ies), {r['seconds']:.2f} s: FLL {r['fll_hz']:+.0f} Hz, Costas {r['costas_hz']:+.0f} Hz, offset {r['total_hz']:+.0f} Hz" if r["locked"]
                            else "NOT locked: no signal, or too weak (raise the B210 TX gain)")
        else:
            rx.stop(); rx.configure(timing_bw=2 * np.pi / w_acq.value, phase_bw=2 * np.pi / w_acq.value); rx.ip.write(0x60, 0); rx.fll_enable(False); rx.start()
            time.sleep(0.15); rx.set_loops(2 * np.pi / w_trk.value, 2 * np.pi / w_trk.value)
            status.value = f"FLL held at 0 Hz, Costas only: acquisition 2 pi/{w_acq.value}, then 2 pi/{w_trk.value}"
        w_live.value = w_trk.value; w_lfll.value = w_fn.value
    finally:
        live.paused = False

def do_freeze(_=None):
    live.paused = True; time.sleep(0.15)
    try:
        f = rx.freeze_fll(); w_usefll.value = False
        status.value = f"FLL frozen at {f:+.0f} Hz; the Costas loop follows the rest"
    finally:
        live.paused = False

def do_tx(change=None):
    if w_tx.value:
        ad.set_tx_atten_db(w_att.value); tx.start(amp=w_amp.value)
    else:
        tx.off(); p501_radio.quiet(ad, TX_ATTEN0)

b_rx.on_click(guard(do_start_receiver)); b_rxoff.on_click(guard(lambda b: rx.stop())); b_frz.on_click(guard(do_freeze))
b_start.on_click(guard(lambda b: live.start())); b_stop.on_click(guard(lambda b: live.stop()))
w_live.observe(guard(lambda c: rx.set_loops(2 * np.pi / c["new"], 2 * np.pi / c["new"])), names="value")
w_lfll.observe(guard(lambda c: rx.set_fll(c["new"])), names="value")
w_usefll.observe(guard(lambda c: rx.fll_enable(c["new"])), names="value")
w_rxg.observe(guard(lambda c: ad.set_rx_manual_gain(c["new"])), names="value")
w_loop.observe(guard(lambda c: p501_radio.loopback(ad, c["new"])), names="value")
w_tx.observe(guard(do_tx), names="value")
w_att.observe(guard(lambda c: ad.set_tx_atten_db(c["new"]) if w_tx.value else None), names="value")
w_amp.observe(guard(lambda c: tx.set(amp=c["new"]) if w_tx.value else None), names="value")

display(widgets.VBox([widgets.HBox([b_rx, b_frz, b_rxoff, b_start, b_stop, status]), widgets.HBox([w_acq, w_trk, w_fw, w_fn]), w_usefll, w_live, w_lfll, w_rxg,
                      widgets.HBox([w_tx, w_loop]), w_att, w_amp, image]))
''')

md("""
### Check the controls (optional)

Moves the controls from Python, the way clicks would, with the digital loopback (no B210 needed), and checks that the registers and the display follow.
""")
code('''
w_loop.value = True
w_att.value = 60.0
w_tx.value = True                                    # the transmitter first (digital loopback; the antenna sees only a very weak signal at 60 dB attenuation) ...
time.sleep(0.3)
b_rx.click()                                         # ... then the receiver: acquire_fll() with the wide gains, then narrow
acq_status = status.value
b_start.click(); time.sleep(3.0)
gi = rx.ip.read(0x58); tb = rx.ip.read(0x0C)
check("acquire_fll() reported a lock", acq_status.startswith("locked"), acq_status)
check("receiver switched to the narrow gains", gi < 400000 and tb < 2000000, f"FLL_GI {gi} (wide 0.002 would be 1367131), TB {tb}")
check("display locked in the loopback", live.locked and live.frames > 4, f"{live.frames} pictures, locked = {live.locked}, status: {status.value}")
w_lfll.value = 0.001; time.sleep(0.3)
check("live FLL gain slider", abs(rx.ip.read(0x58) - 683566) < 20000, f"FLL_GI now {rx.ip.read(0x58)} (0.001 rad = 683566)")
b_frz.click(); time.sleep(0.5)
check("freeze FLL", not rx.fll_status()["enabled"] and abs(rx.fll_status()["fll_hz"]) < 600, f"{rx.fll_status()}")
w_live.value = 100; time.sleep(0.3)
check("live loop slider", rx.ip.read(0x0C) > 10000, f"TB register now {rx.ip.read(0x0C)}")
w_amp.value = 0.3; check("amplitude slider", abs(tx.amp - 0.3) < 0.01, f"transmitter amplitude {tx.amp:.2f}")
b_stop.click(); display(IPImage(image.value))
w_tx.value = False; w_loop.value = False; w_usefll.value = True; b_rxoff.click()
check("transmitter off again", not tx.enabled, f"enabled = {tx.enabled}")
''')

md("""
## Experiment 1: pull-in time with and without the FLL (direction A)

Needs the B210 flowgraph transmitting (*Transmit* ON, TX gain 80). For each case the receiver starts cold with the wide loops (FLL gain 0.002, Costas and timing 2 pi/100) and the cell measures
the **pull-in time**: the moment of the last new mismatch, polling the counter without a pause (about 20 microseconds per reading). At the +9.7 kHz offset of the two radios both pull in within a fraction of a millisecond;
with the B210 moved by +30 kHz (flowgraph frequency 915.03 MHz) or +70 kHz the Costas loop alone needs 3 to 7 times longer.
""")
code('''
def pullin_experiment(trials=6):
    live.stop(); live.paused = True
    probe = rx.acquire_fll()
    if not probe["locked"]:
        print("No B210 signal found (the receiver does not lock): start the flowgraph, set Transmit to ON (TX gain 80), and run this cell again.")
        live.paused = False
        return None
    print(f"offset of the signal about {probe['total_hz']:+.0f} Hz")
    out = {}
    for use_fll, name in ((True, "FLL + Costas"), (False, "Costas only")):
        t, ok = [], 0
        for _ in range(trials):
            ms, mm, locked = rx.pullin_time(use_fll); t.append(ms); ok += bool(locked)
        out[name] = t
        print(f"{name:<14} pull-in {np.median(t):5.2f} ms median  ({min(t):.2f} .. {max(t):.2f} ms)   locked afterwards {ok}/{trials}")
    live.paused = False
    return out

pull = pullin_experiment()
''')

md("""
## Experiment 2: the FLL's jitter and the handover (direction A)

With the loops running, the FLL frequency scatters by about a kilohertz around its mean because the band-edge power depends on the data; the Costas loop compensates, so the sum stays right.
*Freeze* loads the FLL with its mean and stops it. The cell measures the scatter of the FLL, the Costas frequency and the total over 400 readings, the constellation spread, and the bit errors, before and after.
""")
code('''
def scatter(n=400, dt=0.004):
    fl, co = [], []
    for _ in range(n):
        st = rx.fll_status(); fl.append(st["fll_hz"]); co.append(rx._omega_hz(n=1, dt=0)); time.sleep(dt)
    fl, co = np.array(fl), np.array(co)
    return fl.mean(), fl.std(), co.mean(), co.std(), (co - fl).mean(), (co - fl).std()

def handover_experiment():
    live.stop(); live.paused = True
    r = rx.acquire_fll()
    if not r["locked"]:
        print("No B210 signal found: start the flowgraph (Transmit ON, TX gain 80) and run this cell again."); live.paused = False; return None
    rows = []
    for name in ("loop running", "frozen"):
        if name == "frozen": rx.freeze_fll()
        s0 = rx.stats(); m = scatter(); z = rx.capture(); s1 = rx.stats()
        rows.append((name, m, soft_quality(z)[1], (s1["mismatches"] - s0["mismatches"]) // 3, s1["bits"] - s0["bits"]))
    print(f"{'FLL':<14}{'FLL mean':>10}{'std':>7}{'Costas mean':>13}{'std':>7}{'total mean':>12}{'std':>7}{'spread':>8}{'bit errors':>12}")
    for name, m, sp, e, b in rows:
        print(f"{name:<14}{m[0]:>8.0f}Hz{m[1]:>6.0f} {m[2]:>11.0f}Hz{m[3]:>6.0f} {m[4]:>10.0f}Hz{m[5]:>6.0f}{sp:>7.1f}d{e:>8,} in {b / 1e6:.1f} Mbit")
    rx.fll_enable(True)
    live.paused = False
    return rows

rows = handover_experiment()
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
    tx.off(); rx.stop()
    p501_radio.loopback(ad, False)
    p501_radio.quiet(ad, TX_ATTEN0)
    print("transmitter off, receiver stopped, loopback off, TX attenuation %.2f dB" % TX_ATTEN0)
''')

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open(OUT, "w"), indent=1)
print("wrote", OUT, "-", len(cells), "cells")
