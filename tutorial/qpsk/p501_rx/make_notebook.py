#!/usr/bin/env python3
"""Writes notebook/P501_QPSK_Link_Live.ipynb: the P501 side of the interactive QPSK link test (the B210 side is the GNU Radio flowgraph
tutorial/qpsk/gnuradio/qpsk_b210_tx.grc and qpsk_b210_rx.grc).     python3 make_notebook.py"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "notebook", "P501_QPSK_Link_Live.ipynb"))
cells = []


def md(text): cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)})
def code(text): cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip("\n").splitlines(True)})


md("""
# Live: the P501's FPGA QPSK modem against a B210 and GNU Radio

Two directions, one at a time, 915.0 MHz, 3.84 MSPS, 960 ksym/s differential QPSK, PRBS-15 data:

| direction | transmitter | receiver | what you watch |
|---|---|---|---|
| **A: B210 -> P501** | the B210 (GNU Radio flowgraph `qpsk_b210_tx.grc`, *Transmit ON*) | the **FPGA receiver** of this overlay | here: the constellation from the FPGA's capture RAM, bit errors counted *in the FPGA*, carrier and clock offset |
| **B: P501 -> B210** | the **FPGA transmitter** of this overlay (checkbox *Transmit*) | the B210 (flowgraph `qpsk_b210_rx.grc`) | in GNU Radio: constellation, BER box, spectrum |

There is no software in the signal path: Python starts and stops the FPGA blocks, sets the loop gains, and reads counters.

**Before you start**
* Overlay `p501_qpsk_trx` copied to `/home/xilinx/jupyter_notebooks/p501_qpsk_trx/` (with `p501_qpsk.py`, `p501_qpsk_rx.py`), and the notebooks of `p501_fft_dds` (for `p501_radio.py`).
* Antennas on TX1 / RX1 of the P501 and on the TX/RX and RX2 ports of the B210, a few centimetres apart. **Very low power.** Check the rules where you are before transmitting.
* **One direction at a time:** both radios use 915.0 MHz. The transmit flowgraph starts with *Transmit OFF*, this notebook with *Transmit* unticked.
* Everything ends quiet: the last cell (*Stop and silence*) turns the transmitter off and sets the TX attenuation to its maximum.

**Order matters for the narrow loops:** a receiver that runs on noise lets its loops drift, and a narrow loop (2 pi/800 or narrower) then needs a long time to pull in once the signal appears. Start the transmitter first, then press **Start receiver** (it can be pressed again at any time: it re-acquires with the wide loops).

**Steps:** run the cells down to *Self-test*; then *Controls*. Direction A: press **Start receiver** here, start `qpsk_b210_tx.grc`, set its *Transmit* to ON (TX gain 80), lower the gain to see where the receiver stops locking.
Direction B: stop the transmit flowgraph, start `qpsk_b210_rx.grc`, tick **P501 transmits** here and lower the attenuation step by step.
""")

md("## Configuration, overlay and bring-up")
code('''
BIT       = "/home/xilinx/jupyter_notebooks/p501_qpsk_trx/p501_qpsk_trx.bit"   # transmitter + receiver in one overlay (the .hwh next to it)
FS        = 3_840_000          # sample rate
LO        = 915_000_000        # carrier, Hz: the B210 flowgraph uses the same
RX_GAIN   = 70                 # P501 RX gain-table index 0..76: 70 for the B210's weak signal through the air (45 saturates the quantiser floor)
TX_ATTEN0 = 89.75              # TX attenuation (dB) at the start and at the end: the transmitter is silent
''')
code('''
import sys, time, os, io, threading
import numpy as np
from pynq import Overlay

sys.path.insert(0, '/home/xilinx/jupyter_notebooks')
sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds')        # p501_radio.py, p501_dds.py
sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx')       # p501_qpsk.py, p501_qpsk_rx.py
import p501_radio
from p501_qpsk import P501QpskTx
from p501_qpsk_rx import P501QpskRx, soft_quality, constellation_ok, UNIT

results = {}
def check(name, ok, detail):
    results[name] = (bool(ok), detail)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

ol = Overlay(BIT)                                  # programs the PL
tx = P501QpskTx(ol.qpsk_regs, FS)                  # transmitter registers at 0x9C460000: enable, amplitude
rx = P501QpskRx(ol.qpsk_rx)                        # receiver registers at 0x9C470000 (the constructor checks the ID)
ad = p501_radio.bring_up(ol, LO, 4_000_000, TX_ATTEN0, RX_GAIN)     # the AD9361 over SPI; TX attenuation at its maximum during the calibrations
tx.off(); rx.stop()

a_tx, a_rx = ol.ip_dict["qpsk_regs"]["phys_addr"], ol.ip_dict["qpsk_rx"]["phys_addr"]
check("both blocks in the overlay", a_tx == 0x9C460000 and a_rx == 0x9C470000, f"qpsk_regs at 0x{a_tx:08X}, qpsk_rx at 0x{a_rx:08X}")
check("AD9361 up", ad.info["ok"], f"LO locks {ad.info['rx_lock']}/{ad.info['tx_lock']}, ENSM 0x{ad.info['ensm']:X}, calibrations {ad.info['calibrations']}")
''')

md("""
## Helpers: what "locked" means (they live in `p501_qpsk_rx.py`: `soft_quality`, `constellation_ok`, `rx.locked()`, `rx.acquire()`)

The FPGA's PRBS checker alone can be fooled: a receiver that outputs only zeros (no signal at all) also follows the PRBS rule, with *no* mismatches. So *locked* here means two things:
**no new mismatches** in the last interval **and** a sane constellation from the capture RAM: mean symbol magnitude near 1.75 (the AGC target 2.0 times 0.88 for the decision points)
and an angular spread below 25 degrees.
""")
code('''
def restart_receiver(acq_div=100, track_div=None, acq_ms=30, init_freq_hz=0.0):
    """Stop, load the loop gains, start. With track_div the loops are switched live to 2 pi / track_div after acq_ms (acquire wide, track narrow); returns the time it was switched."""
    rx.stop()
    rx.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=init_freq_hz)
    rx.start()
    t0 = time.time()
    if track_div:
        time.sleep(acq_ms * 1e-3)
        rx.set_loops(2 * np.pi / track_div, 2 * np.pi / track_div)
    return t0
''')

md("""
## Self-test: FPGA transmitter -> FPGA receiver, inside the AD9361 (digital loopback)

No antennas, no B210: the chip routes the transmit data back to its receive port. If this passes, the overlay, the AD9361 clocks, the transmitter, the receiver and the PRBS checker work.
""")
code('''
p501_radio.loopback(ad, True)
restart_receiver(400)                                  # 2 pi/400 loops
tx.start(amp=0.5)                                      # PRBS-15 DQPSK from the FPGA transmitter
time.sleep(0.5); s0 = rx.stats()                       # the pull-in is over after a few milliseconds
time.sleep(2.0); s1 = rx.stats()
new_err = s1["mismatches"] - s0["mismatches"]; bits = s1["bits"] - s0["bits"]
f_hz, ppm = rx.offsets(n=200)
z = rx.capture(); mag, spread = soft_quality(z)
tx.off(); rx.stop(); p501_radio.loopback(ad, False)

check("loopback: bits checked", bits > 3_000_000, f"{bits:,} bits in 2 s ({bits / 2 / 1e6:.2f} Mbit/s)")
check("loopback: no bit error after the pull-in", new_err == 0, f"{new_err} mismatches in {bits:,} bits ({s0['mismatches']} during the pull-in = about {s0['mismatches'] // 3} bit errors)")
check("loopback: constellation", constellation_ok(z), f"mean |z| {mag:.2f}, angular spread {spread:.1f} degrees")
check("loopback: no offsets (same clock)", abs(f_hz) < 300 and abs(ppm) < 20, f"carrier {f_hz:+.1f} Hz, clock {ppm:+.2f} ppm")
check("loopback: no overruns", s1["overruns"] == 0, f"overruns {s1['overruns']}")
''')

md("""
## The live machinery

* `render()` draws one picture with NumPy and Pillow (matplotlib needs about 0.4 s per figure on the Zynq's ARM cores): the **constellation** (1024 soft symbols from the capture RAM), the **status** (locked or not, counters, offsets, AGC gain) and two strips: the **carrier offset** and the **mismatches per second**.
* `Live` runs `read registers -> read capture RAM -> picture` in a background thread and puts the PNG into an image widget, so the controls stay responsive. It also performs the *acquire wide, track narrow* switch.
""")
code('''
import ipywidgets as widgets
from IPython.display import display, Image as IPImage
from PIL import Image as PILImage, ImageDraw, ImageFont

W, H = 840, 440
CX, CY, SC = 215, 220, 76                           # constellation centre and pixels per unit (axes +-2.5)
FONT = ImageFont.load_default()
HIST = 80
hist_f = [np.nan] * HIST; hist_m = [np.nan] * HIST; hist_c = [np.nan] * HIST   # carrier offset (Hz), mismatches per second, clock offset (ppm)

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

def strip(d, x0, y0, w, h, data, label, lo, hi, color):
    d.rectangle([x0, y0, x0 + w, y0 + h], outline=(150, 150, 150)); d.text((x0, y0 - 12), label, fill=(60, 60, 60), font=FONT)
    pts = [(x0 + i * w / (len(data) - 1), y0 + h - (min(max(v, lo), hi) - lo) / (hi - lo) * h) for i, v in enumerate(data) if not np.isnan(v)]
    if len(pts) > 1: d.line(pts, fill=color, width=1)
    d.text((x0 + w + 4, y0 - 2), f"{hi:g}", fill=(100, 100, 100), font=FONT); d.text((x0 + w + 4, y0 + h - 9), f"{lo:g}", fill=(100, 100, 100), font=FONT)

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
    lines = [f"symbols {st['symbols']:>12,}", f"bits checked {st['bits']:>9,}", f"mismatches {st['mismatches']:>11,}   (about {st['mismatches'] // 3:,} bit errors)",
             f"BER estimate {st['ber_estimate']:.1e}", f"carrier offset {st['carrier_offset_hz']:+9.1f} Hz", f"clock offset {st['clock_offset_ppm']:+8.1f} ppm (instantaneous)",
             f"AGC gain {st['agc_gain']:.2f}   |z| {mag:.2f}   spread {spread:.1f} deg", f"overruns {st['overruns']}"]
    for i, l in enumerate(lines): d.text((X, 62 + 16 * i), l, fill=(0, 0, 0), font=FONT)
    strip(d, X, 230, 340, 70, hist_f, "carrier offset (Hz), 0 .. +12000", 0, 12000, (200, 120, 20))
    strip(d, X, 335, 340, 70, hist_m, "mismatches per second, 0 .. 1000", 0, 1000, (180, 40, 40))
    buf = io.BytesIO(); img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()

class Live:
    """Background thread: registers + capture RAM -> picture. Also switches the loops from the acquisition to the tracking bandwidth after acq_ms."""
    def __init__(self, image, status):
        self.image, self.status = image, status
        self.running, self.thread, self.frames = False, None, 0
        self.t_switch, self.track_div = None, None
        self.last_m, self.last_t = 0, time.time()
        self.locked, self.st = False, None
        self.paused = False                                      # set while acquire() or an experiment uses the registers
    def arm_switch(self, t_start, acq_ms, track_div):
        self.t_switch, self.track_div = (t_start + acq_ms * 1e-3 if track_div else None), track_div
    def _run(self):
        t_rate = time.time(); n_rate = 0; rate = 0.0
        while self.running:
            if self.paused:
                time.sleep(0.05); continue
            try:
                if self.t_switch is not None and time.time() >= self.t_switch:
                    rx.set_loops(2 * np.pi / self.track_div, 2 * np.pi / self.track_div); self.t_switch = None
                st = rx.stats()
                if st["running"]: z = rx.capture(); self.z = z                  # capture() arms with CTRL = 1, 3: not while the receiver is stopped
                else: z = getattr(self, "z", np.zeros(1024, dtype=complex))
                now = time.time(); dt = max(now - self.last_t, 1e-3)
                mrate = (st["mismatches"] - self.last_m) / dt if st["mismatches"] >= self.last_m else 0.0
                self.last_m, self.last_t = st["mismatches"], now
                self.locked = bool(st["running"] and mrate == 0 and st["bits"] > 0 and constellation_ok(z))
                for h, v in ((hist_f, st["carrier_offset_hz"]), (hist_m, mrate), (hist_c, st["clock_offset_ppm"])): h.pop(0); h.append(v)
                self.st = st
                self.image.value = render(z, st, self.locked, mrate, f"{rate:.1f} pictures/s" + ("  (loops: acquiring)" if self.t_switch is not None else ""))
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
check("live pictures", lv.frames > 6 and len(img_w.value) > 2000, f"{lv.frames} pictures in 3 s ({fps:.1f}/s), status: {st_w.value}")
check("live: locked in the loopback", lv.locked, f"locked = {lv.locked}")
display(IPImage(img_w.value))
tx.off(); rx.stop(); p501_radio.loopback(ad, False)
''')

md("""
## Controls

**Receiver (direction A)**
* **Start receiver**: with *Search for the carrier* ticked it calls `rx.acquire()`: the loops start wide (`2 pi / N`, *Acquisition*) with an initial-frequency hint of 0, +6, -6, +12, -12 kHz in turn, until the receiver is locked and its frequency estimate has settled, then both loops are narrowed live to `2 pi / M` (*Tracking*, **acquire wide, track narrow**). Without the search it starts once with the wide loops and switches after *acq. ms*: the 9.7 kHz offset of the B210 is at the edge of what 2 pi/100 can pull in, so this sometimes ends with the receiver at 0 Hz and 2 % errors, which is instructive.
* **Live loop bandwidth N**: changes both loops at once, while the receiver runs: try 50, 100, 400, 1600 and watch the constellation and the mismatch strip.
* **RX gain**: the AD9361's receive gain index (70 is right for the B210 at 80 dB).
* **Digital loopback**: the chip feeds its own transmitter back: the FPGA transmitter into the FPGA receiver without antennas.

**Transmitter (direction B)**
* **P501 transmits**: the FPGA transmitter (PRBS-15, DQPSK). **Off at the start.** Do not tick it while the B210 transmit flowgraph's *Transmit* is ON.
* **TX attenuation**: 20 dB (strongest, still very low power) to 89.75 dB. Start at 40 dB and go down in steps while you watch the flowgraph's BER box.
* **Amplitude**: the digital amplitude of the transmitter (0.5 default).

**Start display / Stop display**: the live picture; stopping it does not stop the transmitter or the receiver.
""")
code('''
w_acq   = widgets.Dropdown(options=[50, 100, 200, 400, 800], value=100, description="Acquisition N", layout=widgets.Layout(width="200px"))
w_trk   = widgets.Dropdown(options=[("off", 0), ("200", 200), ("400", 400), ("800", 800), ("1600", 1600)], value=400, description="Tracking M", layout=widgets.Layout(width="200px"))
w_ams   = widgets.IntText(value=30, description="acq. ms", layout=widgets.Layout(width="160px"))
w_srch  = widgets.Checkbox(value=True, description="Search for the carrier (initial-frequency hints)", layout=widgets.Layout(width="420px"))
w_live  = widgets.IntSlider(value=400, min=50, max=1600, step=10, description="Live loop N", continuous_update=False, layout=widgets.Layout(width="520px"))
w_rxg   = widgets.IntSlider(value=RX_GAIN, min=0, max=76, description="RX gain", continuous_update=False, layout=widgets.Layout(width="520px"))
w_tx    = widgets.Checkbox(value=False, description="P501 transmits (direction B)")
w_att   = widgets.FloatSlider(value=40.0, min=20.0, max=89.75, step=0.25, description="TX atten (dB)", continuous_update=False, layout=widgets.Layout(width="520px"))
w_amp   = widgets.FloatSlider(value=0.5, min=0.05, max=1.0, step=0.05, description="TX amplitude", continuous_update=False, layout=widgets.Layout(width="520px"))
w_loop  = widgets.Checkbox(value=False, description="Digital loopback")
b_rx    = widgets.Button(description="Start receiver", button_style="success")
b_rxoff = widgets.Button(description="Stop receiver", button_style="warning")
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
        live.last_m, live.last_t = 0, time.time(); hist_f[:] = [np.nan] * HIST; hist_m[:] = [np.nan] * HIST; hist_c[:] = [np.nan] * HIST
        if w_srch.value:
            r = rx.acquire(track_div=w_trk.value or None, acq_div=w_acq.value)
            live.t_switch = None
            status.value = (f"locked after {r['tries']} try(ies), hint {r['hint_hz']:+.0f} Hz, {r['seconds']:.2f} s" if r["locked"] else f"NOT locked after {r['tries']} tries: no signal, or too weak (raise the B210 TX gain)")
        else:
            rx.stop(); rx.configure(timing_bw=2 * np.pi / w_acq.value, phase_bw=2 * np.pi / w_acq.value); rx.start()
            live.arm_switch(time.time(), w_ams.value, w_trk.value or None)
            status.value = f"receiver started without search: acquisition 2 pi/{w_acq.value}" + (f", then 2 pi/{w_trk.value} after {w_ams.value} ms" if w_trk.value else "")
        w_live.value = w_trk.value or w_acq.value
    finally:
        live.paused = False

def do_tx(change=None):
    if w_tx.value:
        ad.set_tx_atten_db(w_att.value); tx.start(amp=w_amp.value)
    else:
        tx.off(); p501_radio.quiet(ad, TX_ATTEN0)

b_rx.on_click(guard(do_start_receiver)); b_rxoff.on_click(guard(lambda b: rx.stop()))
b_start.on_click(guard(lambda b: live.start())); b_stop.on_click(guard(lambda b: live.stop()))
w_live.observe(guard(lambda c: rx.set_loops(2 * np.pi / c["new"], 2 * np.pi / c["new"])), names="value")
w_rxg.observe(guard(lambda c: ad.set_rx_manual_gain(c["new"])), names="value")
w_loop.observe(guard(lambda c: p501_radio.loopback(ad, c["new"])), names="value")
w_tx.observe(guard(do_tx), names="value")
w_att.observe(guard(lambda c: ad.set_tx_atten_db(c["new"]) if w_tx.value else None), names="value")
w_amp.observe(guard(lambda c: tx.set(amp=c["new"]) if w_tx.value else None), names="value")

display(widgets.VBox([widgets.HBox([b_rx, b_rxoff, b_start, b_stop, status]), widgets.HBox([w_acq, w_trk, w_ams]), w_srch, w_live, w_rxg,
                      widgets.HBox([w_tx, w_loop]), w_att, w_amp, image]))
''')

md("""
### Check the controls (optional)

Moves the controls from Python, the way clicks would, with the digital loopback (no B210 needed), and checks that the registers and the display follow.
""")
code('''
w_loop.value = True
w_trk.value, w_acq.value = 1600, 100
w_att.value = 60.0
w_tx.value = True                                    # the transmitter first (digital loopback; the antenna sees only a very weak signal at 60 dB attenuation) ...
time.sleep(0.3)
b_rx.click()                                         # ... then the receiver: acquire() with the wide loops, then narrow
acq_status = status.value
b_start.click(); time.sleep(3.0)
r = rx.ip.read(0x08), rx.ip.read(0x0C)
check("receiver switched to the tracking loops", r[1] < 2000, f"TB register {r[1]} (2 pi/100 would be about 242000)")
check("display locked in the loopback", live.locked and live.frames > 5, f"{live.frames} pictures, locked = {live.locked}, status: {status.value}")
check("acquire() reported a lock", acq_status.startswith("locked"), acq_status)
w_live.value = 100; time.sleep(0.3)
check("live loop slider", rx.ip.read(0x0C) > 10000, f"TB register now {rx.ip.read(0x0C)}")
w_amp.value = 0.3; check("amplitude slider", abs(tx.amp - 0.3) < 0.01, f"transmitter amplitude {tx.amp:.2f}")
b_stop.click(); display(IPImage(image.value))
w_tx.value = False; w_loop.value = False; b_rxoff.click()
check("transmitter off again", not tx.enabled, f"enabled = {tx.enabled}")
''')

md("""
## Experiment: loop bandwidths against the B210 (direction A)

For each setting the receiver restarts **without** the carrier search (the plain cold start), and the cell measures the **pull-in time** (the moment of the last new mismatch, polled every 100 microseconds at the start), the bit errors, and the carrier and clock offsets.
It needs the B210 flowgraph transmitting (*Transmit* ON, TX gain 75 or more): the cell first checks that a signal is there. Expect a mixed picture: the offset is at the edge of the wide loop's pull-in range, narrow loops alone do not pull in (carrier reads about 0 Hz, 2 % errors),
and the last rows, `acquire()` (the carrier search of `p501_qpsk_rx.py`), lock every time.
""")
code('''
def run_case(acq_div, track_div, seconds=3.0, acq_ms=30):
    live.stop()
    rx.stop(); rx.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div); rx.start()
    t0 = time.time(); switched = not track_div; last_m, last_t = 0, 0.0; m_mid = None
    while time.time() - t0 < seconds:
        if not switched and time.time() - t0 >= acq_ms * 1e-3:
            rx.set_loops(2 * np.pi / track_div, 2 * np.pi / track_div); switched = True
        if time.time() - t0 > 0.3: time.sleep(0.005)
        m = rx.ip.read(0x3C); now = time.time() - t0
        if m != last_m: last_m, last_t = m, now
        if m_mid is None and now > 0.6 * seconds: m_mid = m
    st = rx.stats(); f_hz, ppm = rx.offsets(n=100); z = rx.capture()
    ok = constellation_ok(z) and last_m == m_mid                       # no new mismatch in the last 40 % of the run, and a sane constellation
    return dict(case=f"2pi/{acq_div}" + (f" -> 2pi/{track_div}" if track_div else ""), locked=ok, pullin_ms=1e3 * last_t, errors=last_m // 3, bits=st["bits"], ber=(last_m / 3.0 / max(st["bits"], 1)),
                carrier_hz=f_hz, clock_ppm=ppm, spread=soft_quality(z)[1])

def loop_experiment(cases=((100, None), (400, None), (800, None), (100, 400), (100, 1600)), seconds=3.0):
    probe = run_case(100, 400, seconds=2.0)
    if not probe["locked"]:
        print("No B210 signal found (the receiver does not lock): start the flowgraph, set Transmit to ON (TX gain 80), and run this cell again.")
        return None
    print(f"{'loops':<18}{'locked':<8}{'pull-in':>10}{'bit errors':>12}{'BER':>10}{'carrier':>11}{'clock':>10}{'spread':>8}")
    rows = []
    for acq, trk in cases:
        r = run_case(acq, trk, seconds=seconds); rows.append(r)
        print(f"{r['case']:<18}{('yes' if r['locked'] else 'NO'):<8}{r['pullin_ms']:>8.2f}ms{r['errors']:>12,}{r['ber']:>10.1e}{r['carrier_hz']:>9.0f}Hz{r['clock_ppm']:>8.1f}ppm{r['spread']:>7.1f}d")
    live.paused = True
    for k in range(3):                                                         # the robust start: wide loops with frequency hints, then narrow
        t0 = time.time(); r = rx.acquire(track_div=400); time.sleep(1.0); s0 = rx.stats(); time.sleep(1.0); s1 = rx.stats(); f_hz, ppm = rx.offsets(n=100)
        print(f"{'acquire() -> 400':<18}{('yes' if r['locked'] else 'NO'):<8}{r['seconds'] * 1e3:>8.0f}ms{(s1['mismatches'] - s0['mismatches']) // 3:>12,}{'':>10}{f_hz:>9.0f}Hz{ppm:>8.1f}ppm   (try {r['tries']}, hint {r['hint_hz']})")
    live.paused = False
    return rows

rows = loop_experiment()
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
