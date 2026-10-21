#!/usr/bin/env python3
"""Writes notebook/P501_QPSK_4P_Live.ipynb: the P501 side of the interactive QPSK link test for chain 3, polyphase -> 4th-power estimator -> Costas loop, with no software in the loop (overlay p501_qpsk_trx_4p),
the counterpart of notebook/P501_QPSK_Link_Live.ipynb (chain 1) and P501_QPSK_FLL_Live.ipynb (chain 2). The B210 side is the same GNU Radio flowgraphs.     python3 make_notebook_4p.py"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "notebook", "P501_QPSK_4P_Live.ipynb"))
cells = []


def md(text): cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)})
def code(text): cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip("\n").splitlines(True)})


md("""
# Live: chain 3, polyphase -> 4th power -> Costas, in the P501 FPGA against a B210 and GNU Radio

The same link test as the other two notebooks, with the receiver of the overlay **`p501_qpsk_trx_4p`**. 915.0 MHz, 3.84 MSPS, 960 ksym/s differential QPSK, PRBS-15 data.

| chain | overlay | notebook |
|---|---|---|
| 1. polyphase -> Costas | `p501_qpsk_trx` | `P501_QPSK_Link_Live.ipynb` |
| 2. FLL -> polyphase -> Costas | `p501_qpsk_trx_fll` | `P501_QPSK_FLL_Live.ipynb` |
| **3. polyphase -> 4th power -> Costas** | **`p501_qpsk_trx_4p`** | **this one** |

| direction | transmitter | receiver | what you watch |
|---|---|---|---|
| **A: B210 -> P501** | the B210 (GNU Radio flowgraph `qpsk_b210_tx.grc`, *Transmit ON*) | the **FPGA receiver** | here: constellation, bit errors counted in the FPGA, the Costas frequency and what the estimator measured and loaded |
| **B: P501 -> B210** | the **FPGA transmitter** (checkbox *Transmit*) | the B210 (flowgraph `qpsk_b210_rx.grc`) | in GNU Radio: constellation, BER box, spectrum |

**What chain 3 does, all in the FPGA.** For every symbol *after the polyphase matched filter, the timing loop and the AGC* the estimator forms `d = m x conj(m_previous)` (the phase step between two symbols: `2 pi f T` plus a multiple of 90 degrees of data),
takes the angle of `d` with a CORDIC, multiplies it by 4 (the data steps become multiples of 360 degrees and vanish), turns it into a unit vector with the sine table and adds the vectors of N symbols. A second CORDIC takes the
`atan2` of the sum, giving `f = atan2(ACC_IM, ACC_RE) / (8 pi) x 960 kHz` (unambiguous for |f| < 120 kHz). If the window is good enough (*quality* = length of the sum / N above the gate *q_min*; 1 = clean, 0 = noise),
**the hardware writes f into the Costas loop's frequency register**, and the Costas loop takes over. Python only enables it and reads the counters.
* **Once**: windows follow each other until one passes the gate; that one loads the frequency; then the Costas loop tracks alone. Press *Estimate again* to repeat.
* **Continuous**: every window that passes loads the frequency (the Costas integrator is replaced by the measurement once per window). Good for small offsets; **worse than once at large offsets** (the estimate is 1 to 3 % low at 80 to 90 kHz and the loads fight the Costas loop).
* **Costas only**: the estimator is off; the receiver of chapter 4d, for comparison.

**Before you start**
* Overlay `p501_qpsk_trx_4p` copied to `/home/xilinx/jupyter_notebooks/p501_qpsk_trx_4p/` (with `p501_qpsk.py`, `p501_qpsk_rx.py`, `p501_qpsk_rx_4p.py`), and the notebooks of `p501_fft_dds` (for `p501_radio.py`).
* Antennas on TX1 / RX1 of the P501 and on the TX/RX and RX2 ports of the B210, a few centimetres apart. **Very low power** (B210 TX gain 80 dB at most). Check the rules where you are before transmitting.
* **One direction at a time.** The transmit flowgraph starts with *Transmit OFF*, this notebook with *Transmit* unticked. **Start the transmitter first, then press Start receiver.**
* Everything ends quiet: the last cell (*Stop and silence*) turns the transmitter off and sets the TX attenuation to its maximum.
""")

md("## Configuration, overlay and bring-up")
code('''
BIT       = "/home/xilinx/jupyter_notebooks/p501_qpsk_trx_4p/p501_qpsk_trx_4p.bit"   # transmitter + receiver of chain 3 in one overlay (the .hwh next to it)
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
sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_4p')        # p501_qpsk.py, p501_qpsk_rx.py, p501_qpsk_rx_4p.py
import p501_radio
from p501_qpsk import P501QpskTx
from p501_qpsk_rx import soft_quality, constellation_ok, UNIT, REG, _signed, SYMBOL_RATE
from p501_qpsk_rx_4p import P501QpskRx4p

results = {}
def check(name, ok, detail):
    results[name] = (bool(ok), detail)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

ol = Overlay(BIT)                                  # programs the PL
tx = P501QpskTx(ol.qpsk_regs, FS)                  # transmitter registers at 0x9C460000: enable, amplitude
rx = P501QpskRx4p(ol.qpsk_rx)                      # receiver registers at 0x9C470000 (the constructor checks the ID 0xDD520004: chain 3)
ad = p501_radio.bring_up(ol, LO, 4_000_000, TX_ATTEN0, RX_GAIN)     # the AD9361 over SPI; TX attenuation at its maximum during the calibrations
tx.off(); rx.stop()

a_tx, a_rx = ol.ip_dict["qpsk_regs"]["phys_addr"], ol.ip_dict["qpsk_rx"]["phys_addr"]
check("both blocks in the overlay", a_tx == 0x9C460000 and a_rx == 0x9C470000, f"qpsk_regs at 0x{a_tx:08X}, qpsk_rx at 0x{a_rx:08X}")
check("AD9361 up", ad.info["ok"], f"LO locks {ad.info['rx_lock']}/{ad.info['tx_lock']}, ENSM 0x{ad.info['ensm']:X}, calibrations {ad.info['calibrations']}")
''')

md("""
## Self-test: FPGA transmitter -> FPGA receiver, inside the AD9361 (digital loopback)

No antennas, no B210. Same clock at both ends: no offset, so the estimator must read about 0 Hz with a high quality, and the autonomous start must lock and load about 0 Hz.
""")
code('''
p501_radio.loopback(ad, True)
tx.start(amp=0.5)                                      # PRBS-15 DQPSK from the FPGA transmitter
time.sleep(0.2)
r1 = rx.acquire_4p(continuous=False)                   # chain 3, once: wide loops, the estimator loads OMEGA, then narrow loops
time.sleep(0.5); s0 = rx.stats()
time.sleep(2.0); s1 = rx.stats()
new_err = s1["mismatches"] - s0["mismatches"]; bits = s1["bits"] - s0["bits"]
e = rx.measure(2048)                                   # one manual window on the settled receiver
z = rx.capture(); mag, spread = soft_quality(z)
r2 = rx.acquire_4p(continuous=True); time.sleep(0.3); a2 = rx.auto_status()
tx.off(); rx.stop(); p501_radio.loopback(ad, False)

check("loopback: chain 3 (once) locked", r1["locked"], f"locked after {r1['tries']} try(ies), {r1['seconds']:.2f} s, loaded {r1['west_hz']:+.1f} Hz, Costas {r1['costas_hz']:+.1f} Hz")
check("loopback: bits checked", bits > 3_000_000, f"{bits:,} bits in 2 s ({bits / 2 / 1e6:.2f} Mbit/s)")
check("loopback: no bit error after the lock", new_err == 0, f"{new_err} mismatches in {bits:,} bits")
check("loopback: constellation", constellation_ok(z), f"mean |z| {mag:.2f}, angular spread {spread:.1f} degrees")
check("loopback: estimator reads about 0 Hz, quality high", abs(e["f_hz"]) < 300 and e["quality"] > 0.7, f"{e['f_hz']:+.1f} Hz, quality {e['quality']:.2f}")
check("loopback: chain 3 (continuous) locked and loads", r2["locked"] and a2["loads"] > 100, f"locked {r2['locked']}, {a2['loads']} loads in 0.3 s, last {a2['west_hz']:+.1f} Hz")
check("loopback: no overruns", s1["overruns"] == 0, f"overruns {s1['overruns']}")
''')

md("""
## The live machinery

* `render()` draws one picture with NumPy and Pillow: the **constellation** (1024 soft symbols from the capture RAM), the **status**, and three strips: the **frequencies** (Costas in blue, the estimator in purple), the **constellation spread** in degrees and the **mismatches per second**.
* `Live` runs `read registers -> estimator window -> read capture RAM -> picture` in a background thread. The purple curve is a manual window of the estimator, taken when the autonomous estimator is idle (off, or in *once* after its load);
  in *continuous* mode (the estimator is busy) it shows the last window's frequency instead.
""")
code('''
import ipywidgets as widgets
from IPython.display import display, Image as IPImage
from PIL import Image as PILImage, ImageDraw, ImageFont

W, H = 840, 580
CX, CY, SC = 215, 220, 76                           # constellation centre and pixels per unit (axes +-2.5)
FONT = ImageFont.load_default()
HIST = 80
hist_co = [np.nan] * HIST; hist_e = [np.nan] * HIST; hist_sp = [np.nan] * HIST; hist_m = [np.nan] * HIST
# Costas frequency (Hz), estimator (Hz), constellation spread (degrees), mismatches per second

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

def render(z, st, ast, est, locked, mrate, note=""):
    img = BASE.copy(); d = ImageDraw.Draw(img)
    zn = np.asarray(z) / UNIT
    for a, b in zip(zn.real, zn.imag):
        x, y = CX + a * SC, CY - b * SC
        if abs(a) < 2.5 and abs(b) < 2.5: d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=(31, 119, 180))
    mag, spread = soft_quality(z)
    X = 450
    d.text((X, 20), "LOCKED" if locked else "NOT LOCKED", fill=(30, 140, 50) if locked else (200, 40, 40), font=FONT)
    d.text((X, 36), note, fill=(110, 110, 110), font=FONT)
    mode = {0: "off (Costas only)", 1: "once", 3: "continuous"}.get(ast["auto"], str(ast["auto"]))
    lines = [f"bits checked {st['bits']:>9,}   mismatches {st['mismatches']:>9,} (about {st['mismatches'] // 3:,} errors)",
             f"BER estimate {st['ber_estimate']:.1e}   overruns {st['overruns']}",
             f"Costas frequency  {st['carrier_offset_hz']:+9.1f} Hz",
             (f"estimator window  {est['f_hz']:+9.1f} Hz   (N {est['count']}, quality {est['quality']:.2f})" if est else f"estimator (busy)    last window {ast['wlast_hz']:+9.1f} Hz"),
             f"autonomous: {mode},  N {ast['n']},  loads {ast['loads']},  windows {ast['windows']},  last loaded {ast['west_hz']:+.1f} Hz",
             f"clock offset {st['clock_offset_ppm']:+8.1f} ppm (instantaneous)   AGC gain {st['agc_gain']:.2f}",
             f"|z| {mag:.2f}   spread {spread:.1f} deg"]
    for i, l in enumerate(lines): d.text((X, 62 + 16 * i), l, fill=(0, 0, 0), font=FONT)
    strip(d, X, 205, 340, 80, [(hist_co, (31, 119, 180)), (hist_e, (130, 50, 170))], "Costas (blue) and estimator (purple) frequency (Hz)")
    strip(d, X, 325, 340, 80, [(hist_sp, (200, 120, 20))], "constellation spread (degrees), 0 .. 30", 0, 30)
    strip(d, X, 445, 340, 80, [(hist_m, (180, 40, 40))], "mismatches per second, 0 .. 1000", 0, 1000)
    buf = io.BytesIO(); img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()

class Live:
    """Background thread: registers + (idle) estimator window + capture RAM -> picture."""
    def __init__(self, image, status):
        self.image, self.status = image, status
        self.running, self.thread, self.frames = False, None, 0
        self.last_m, self.last_t = 0, time.time()
        self.locked, self.st, self.est, self.ast = False, None, None, None
        self.paused = False                                      # set while a start procedure or an experiment uses the registers
        self.nwin = 2048
    def _run(self):
        t_rate = time.time(); n_rate = 0; rate = 0.0
        while self.running:
            if self.paused:
                time.sleep(0.05); continue
            try:
                st = rx.stats(); ast = rx.auto_status(); est = None
                if st["running"]:
                    z = rx.capture(); self.z = z                                 # capture() arms with CTRL = 1, 3: not while the receiver is stopped
                    if ast["auto"] == 0 or (ast["auto"] == 1 and ast["loads"] > 0):      # the estimator's accumulators are free
                        est = rx.measure(self.nwin)
                else: z = getattr(self, "z", np.zeros(1024, dtype=complex))
                now = time.time(); dt = max(now - self.last_t, 1e-3)
                mrate = (st["mismatches"] - self.last_m) / dt if st["mismatches"] >= self.last_m else 0.0
                self.last_m, self.last_t = st["mismatches"], now
                self.locked = bool(st["running"] and mrate == 0 and st["bits"] > 0 and constellation_ok(z))
                ef = est["f_hz"] if est else (ast["wlast_hz"] if ast["windows"] else np.nan)
                for h, v in ((hist_co, st["carrier_offset_hz"]), (hist_e, ef), (hist_sp, soft_quality(z)[1]), (hist_m, mrate)): h.pop(0); h.append(v)
                self.st, self.est, self.ast = st, est, ast
                self.image.value = render(z, st, ast, est, self.locked, mrate, f"{rate:.1f} pictures/s")
                self.frames += 1; n_rate += 1
                if now - t_rate > 2: rate = n_rate / (now - t_rate); t_rate = now; n_rate = 0
            except TimeoutError:
                self.status.value = "capture or estimator timed out: is the receiver running?"; time.sleep(0.5)
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
p501_radio.loopback(ad, True); tx.start(amp=0.5); time.sleep(0.2); rx.acquire_4p(); time.sleep(0.3)
img_w, st_w = widgets.Image(format="png"), widgets.Label()
lv = Live(img_w, st_w)
lv.start(); time.sleep(3); lv.stop()
fps = lv.frames / 3.0
check("live pictures", lv.frames > 4 and len(img_w.value) > 2000, f"{lv.frames} pictures in 3 s ({fps:.1f}/s), status: {st_w.value}")
check("live: locked in the loopback", lv.locked, f"locked = {lv.locked}")
check("live: estimator window read", lv.est is not None and lv.est["count"] >= 2048, f"{lv.est}")
display(IPImage(img_w.value))
tx.off(); rx.stop(); p501_radio.loopback(ad, False)
''')

md("""
## Controls

**Receiver (direction A)**
* **Method** and **Start receiver**: *Autonomous, once*, *Autonomous, continuous* or *Costas only (reference)*. The loops start wide (*Acquisition N*, `2 pi / N`); after 2000 symbols (the AGC and the timing loop must converge first) the estimator is enabled; when it has loaded the frequency the loops are
  narrowed to `2 pi / M` (*Tracking M*). *Est. window* is the estimator's window N (symbols; 1024 = 1.1 ms) and *q min* the quality gate. The status line shows the result.
* **Estimate again**: restarts the estimator (once or continuous, as chosen) without restarting the receiver: use it after the offset has changed (for instance when you retune the B210 flowgraph) to load the new frequency into the Costas loop.
* **Stop estimator**: disables the estimator; the Costas loop continues alone with the frequency it has.
* **Live window**: the estimator window of the live display (the purple curve), 256 .. 16384 symbols. **Live loop N**: the timing and Costas loops. **RX gain**, **Digital loopback**.

**Transmitter (direction B)**: **P501 transmits** (off at the start; do not tick it while the B210's *Transmit* is ON), **TX attenuation** (20 dB .. 89.75 dB; start at 40 dB), **Amplitude**.

**Start display / Stop display**: the live picture; stopping it does not stop the transmitter or the receiver.

To test a larger offset, set the frequency of the B210 flowgraph a few tens of kHz away from 915.0 MHz (for instance 915.03 MHz or 914.9 MHz) and press *Estimate again*; the estimator follows it up to about 110 kHz. The Costas loop alone (method *Costas only*) cannot pull in much more than 80 kHz.
""")
code('''
w_meth  = widgets.Dropdown(options=[("Autonomous, once", "once"), ("Autonomous, continuous", "continuous"), ("Costas only (reference)", "costas")], value="once", description="Method", layout=widgets.Layout(width="320px"))
w_acq   = widgets.Dropdown(options=[50, 100, 200, 400], value=100, description="Acquisition N", layout=widgets.Layout(width="200px"))
w_trk   = widgets.Dropdown(options=[("200", 200), ("400", 400), ("800", 800), ("1600", 1600)], value=400, description="Tracking M", layout=widgets.Layout(width="200px"))
w_awin  = widgets.Dropdown(options=[256, 512, 1024, 2048, 4096], value=1024, description="Est. window", layout=widgets.Layout(width="200px"))
w_qmin  = widgets.FloatSlider(value=0.3, min=0.05, max=0.9, step=0.05, description="q min", continuous_update=False, layout=widgets.Layout(width="320px"))
w_win   = widgets.Dropdown(options=[256, 512, 1024, 2048, 4096, 16384], value=2048, description="Live window", layout=widgets.Layout(width="200px"))
w_live  = widgets.IntSlider(value=400, min=50, max=1600, step=10, description="Live loop N", continuous_update=False, layout=widgets.Layout(width="520px"))
w_rxg   = widgets.IntSlider(value=RX_GAIN, min=0, max=76, description="RX gain", continuous_update=False, layout=widgets.Layout(width="520px"))
w_tx    = widgets.Checkbox(value=False, description="P501 transmits (direction B)")
w_att   = widgets.FloatSlider(value=40.0, min=20.0, max=89.75, step=0.25, description="TX atten (dB)", continuous_update=False, layout=widgets.Layout(width="520px"))
w_amp   = widgets.FloatSlider(value=0.5, min=0.05, max=1.0, step=0.05, description="TX amplitude", continuous_update=False, layout=widgets.Layout(width="520px"))
w_loop  = widgets.Checkbox(value=False, description="Digital loopback")
b_rx    = widgets.Button(description="Start receiver", button_style="success")
b_rxoff = widgets.Button(description="Stop receiver", button_style="warning")
b_again = widgets.Button(description="Estimate again", button_style="primary")
b_fe0   = widgets.Button(description="Stop estimator", button_style="primary")
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
        for h in (hist_co, hist_e, hist_sp, hist_m): h[:] = [np.nan] * HIST
        m = w_meth.value
        if m == "costas":
            rx.disable_auto()
            r = rx.acquire(hints_hz=(0.0,), track_div=w_trk.value, acq_div=w_acq.value)
            status.value = (f"Costas only: locked after {r['seconds']:.2f} s, frequency {rx._omega_hz():+.0f} Hz" if r["locked"] else "Costas only: NOT locked (the offset is probably too large for the Costas loop alone)")
        else:
            r = rx.acquire_4p(n=w_awin.value, q_min=w_qmin.value, continuous=(m == "continuous"), acq_div=w_acq.value, track_div=w_trk.value)
            status.value = (f"locked after {r['tries']} try(ies), {r['seconds']:.2f} s: loaded {r['west_hz']:+.0f} Hz ({r['loads']} loads, {r['windows']} windows), Costas {r['costas_hz']:+.0f} Hz"
                            if r["locked"] else "NOT locked: no signal, or too weak (raise the B210 TX gain)")
        w_live.value = w_trk.value
    finally:
        live.paused = False

def do_again(_=None):
    live.paused = True; time.sleep(0.15)
    try:
        rx.set_auto(w_awin.value, w_qmin.value); rx.enable_auto(w_meth.value == "continuous"); t1 = time.time()
        while rx.ip.read(REG["FE_NLOAD"]) == 0 and time.time() - t1 < 0.5: time.sleep(0.0005)
        a = rx.auto_status()
        status.value = f"estimator restarted: {a['loads']} load(s), last loaded {a['west_hz']:+.0f} Hz, Costas {rx._omega_hz():+.0f} Hz" if a["loads"] else "estimator restarted: no window passed the gate yet (signal too weak? lower q min)"
    finally:
        live.paused = False

def do_fe0(_=None):
    live.paused = True; time.sleep(0.15)
    try:
        rx.disable_auto(); status.value = "estimator stopped; the Costas loop continues alone"
    finally:
        live.paused = False

def do_tx(change=None):
    if w_tx.value:
        ad.set_tx_atten_db(w_att.value); tx.start(amp=w_amp.value)
    else:
        tx.off(); p501_radio.quiet(ad, TX_ATTEN0)

b_rx.on_click(guard(do_start_receiver)); b_rxoff.on_click(guard(lambda b: (rx.disable_auto(), rx.stop()))); b_again.on_click(guard(do_again)); b_fe0.on_click(guard(do_fe0))
b_start.on_click(guard(lambda b: live.start())); b_stop.on_click(guard(lambda b: live.stop()))
w_win.observe(guard(lambda c: setattr(live, "nwin", c["new"])), names="value")
w_live.observe(guard(lambda c: rx.set_loops(2 * np.pi / c["new"], 2 * np.pi / c["new"])), names="value")
w_rxg.observe(guard(lambda c: ad.set_rx_manual_gain(c["new"])), names="value")
w_loop.observe(guard(lambda c: p501_radio.loopback(ad, c["new"])), names="value")
w_tx.observe(guard(do_tx), names="value")
w_att.observe(guard(lambda c: ad.set_tx_atten_db(c["new"]) if w_tx.value else None), names="value")
w_amp.observe(guard(lambda c: tx.set(amp=c["new"]) if w_tx.value else None), names="value")

display(widgets.VBox([widgets.HBox([b_rx, b_again, b_fe0, b_rxoff, b_start, b_stop, status]), widgets.HBox([w_meth, w_awin, w_qmin]), widgets.HBox([w_acq, w_trk, w_win]),
                      w_live, w_rxg, widgets.HBox([w_tx, w_loop]), w_att, w_amp, image]))
''')

md("""
### Check the controls (optional)

Moves the controls from Python, the way clicks would, with the digital loopback (no B210 needed): starts the receiver with each of the three methods, restarts and stops the estimator.
""")
code('''
w_loop.value = True
w_att.value = 60.0
w_tx.value = True                                    # the transmitter first (digital loopback; the antenna sees only a very weak signal at 60 dB attenuation) ...
time.sleep(0.3)
b_start.click()
for meth in ("once", "continuous", "costas"):
    w_meth.value = meth
    b_rx.click()                                     # ... then the receiver
    time.sleep(0.5)
    check(f"start receiver, method {meth}", ("locked" in status.value.lower()) and "NOT" not in status.value, status.value)
w_meth.value = "once"; b_rx.click(); time.sleep(0.3)
b_again.click(); time.sleep(0.3)
check("estimate again", "restarted" in status.value and rx.auto_status()["loads"] >= 1, status.value)
b_fe0.click(); time.sleep(0.3)
check("stop estimator", rx.auto_status()["auto"] == 0 and live.locked, f"FE_AUTO {rx.auto_status()['auto']}, locked {live.locked}")
w_win.value = 4096; time.sleep(0.5)
check("live window", live.nwin == 4096 and live.est is not None and live.est["count"] == 4096, f"window {live.nwin}, last count {live.est['count'] if live.est else None}")
w_live.value = 100; time.sleep(0.3)
check("live loop slider", rx.ip.read(0x0C) > 10000, f"TB register now {rx.ip.read(0x0C)}")
w_amp.value = 0.3; check("amplitude slider", abs(tx.amp - 0.3) < 0.01, f"transmitter amplitude {tx.amp:.2f}")
b_stop.click(); display(IPImage(image.value))
w_tx.value = False; w_loop.value = False; b_rxoff.click()
check("transmitter off again", not tx.enabled, f"enabled = {tx.enabled}")
''')

md("""
## Experiment 1: accuracy of the estimator, and the first value the hardware loads (direction A)

Needs the B210 flowgraph transmitting (*Transmit* ON, TX gain 80). The receiver locks (Costas only) and its long-run mean frequency is the reference. Part 1: the estimator measures 20 manual windows for each N: mean minus reference (the bias) and the standard deviation.
Part 2: the autonomous estimator, cold start, 10 times for N = 256, 1024, 4096: the value it loaded first. Earlier results at +9.5 kHz: std 54 Hz at N = 1024 and 13 Hz at 16384 (manual); the first loaded value had a std of 378, 150 and 29 Hz.
""")
code('''
def accuracy_experiment(ns=(128, 256, 512, 1024, 2048, 4096, 16384), windows=20, starts=10):
    live.stop(); live.paused = True
    rx.disable_auto()
    r = rx.acquire(hints_hz=(0.0,))
    if not r["locked"]:
        print("No B210 signal found (the receiver does not lock): start the flowgraph, set Transmit to ON (TX gain 80), and run this cell again."); live.paused = False; return None
    co = np.array([_signed(rx.ip.read(REG["OMEGA"])) / 2 ** 32 * SYMBOL_RATE for _ in range(400) if not time.sleep(0.003)])
    print(f"reference: Costas mean {co.mean():+.1f} Hz (std of the readings {co.std():.0f} Hz), AGC gain {rx.stats()['agc_gain']:.2f}")
    print(f"{'N':>7}{'time':>10}{'mean':>12}{'bias':>9}{'std':>9}{'quality':>9}")
    for n in ns:
        es = [rx.measure(n) for _ in range(windows)]
        f = np.array([e["f_hz"] for e in es]); q = np.mean([e["quality"] for e in es])
        print(f"{n:>7}{n / 960.0:>8.1f}ms{f.mean():>10.1f}Hz{f.mean() - co.mean():>7.1f}Hz{f.std():>7.1f}Hz{q:>9.2f}")
    print("autonomous estimator, cold starts (the first value it loads):")
    for n in (256, 1024, 4096):
        v = []
        for _ in range(starts):
            rx.disable_auto(); rx.stop(); time.sleep(0.03); rx.configure(); rx.set_auto(n, 0.3); rx.start(); time.sleep(2000 / SYMBOL_RATE); rx.enable_auto(False)
            t1 = time.time()
            while rx.ip.read(REG["FE_NLOAD"]) == 0 and time.time() - t1 < 0.5: time.sleep(0.0005)
            v.append(rx.auto_status()["west_hz"])
        v = np.array(v)
        print(f"  N {n:>5}: loaded {v.mean():+9.1f} Hz mean, std {v.std():6.1f} Hz (min {v.min():+.0f}, max {v.max():+.0f}) over {starts} cold starts")
    rx.disable_auto(); live.paused = False

accuracy_experiment()
''')

md("""
## Experiment 2: lock from a cold start, Costas alone against the autonomous estimator (direction A)

Each mode starts the receiver cold with the same wide loops and no hint, and the cell polls the mismatch counter without a pause: the time of the last change is the time to lock. Then the loops are narrowed and the cell watches 1 s:
new mismatches, the Costas frequency (mean, std) and the constellation spread. Needs the B210 transmitting. Try it at the natural +9.7 kHz offset and with the B210 frequency moved by +30 kHz, -60 kHz or -90 kHz (915.03, 914.94 or 914.9 MHz).
Earlier results: +9.5 kHz all three lock at once and equally well; at -90 kHz *once* locked (64 mismatches in 2 s) and the Costas loop alone did not; *continuous* was worse than *once* at large offsets.
""")
code('''
def lock_experiment(trials=6, modes=("costas", "once", "continuous")):
    live.stop(); live.paused = True
    restart = rx.timed_lock("once")
    if not restart["locked"] and restart["loads"] == 0:
        print("No B210 signal found (the estimator loaded nothing): start the flowgraph, set Transmit to ON (TX gain 80), and run this cell again."); rx.disable_auto(); rx.stop(); live.paused = False; return None
    print(f"{'mode':<11}{'locked':>8}{'lock time median (max)':>26}{'  after the lock, 1 s: new mismatches':>40}{'Costas mean':>14}{'std':>7}{'spread':>8}")
    for mode in modes:
        rs = [rx.timed_lock(mode) for _ in range(trials)]
        ok = [r for r in rs if r["locked"]]
        rx.timed_lock(mode); rx.set_loops(2 * np.pi / 400, 2 * np.pi / 400); time.sleep(0.2)
        s0 = rx.stats(); om = []; sp = []; t0 = time.time()
        while time.time() - t0 < 1.0:
            om.append(_signed(rx.ip.read(REG["OMEGA"])) / 2 ** 32 * SYMBOL_RATE); time.sleep(0.004)
            if len(om) % 50 == 0: sp.append(soft_quality(rx.capture())[1])
        s1 = rx.stats(); om = np.array(om)
        print(f"{mode:<11}{len(ok):>5}/{trials:<2}{(np.median([r['ms'] for r in ok]) if ok else float('nan')):>14.1f} ms ({(max([r['ms'] for r in ok]) if ok else float('nan')):.1f}){s1['mismatches'] - s0['mismatches']:>30,}{om.mean():>12.1f}Hz{om.std():>6.0f}{np.mean(sp):>7.1f}d")
    rx.disable_auto(); rx.stop(); live.paused = False

lock_experiment()
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
    rx.disable_auto(); tx.off(); rx.stop()
    p501_radio.loopback(ad, False)
    p501_radio.quiet(ad, TX_ATTEN0)
    print("transmitter off, receiver stopped, loopback off, TX attenuation %.2f dB" % TX_ATTEN0)
''')

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open(OUT, "w"), indent=1)
print("wrote", OUT, "-", len(cells), "cells")
