#!/usr/bin/env python3
"""Writes notebook/P501_QPSK_FE_Live.ipynb: the P501 side of the interactive QPSK link test with the receiver that has the FLL AND the 4th-power estimator (overlay p501_qpsk_trx_fe),
the counterpart of notebook/P501_QPSK_FLL_Live.ipynb (tutorial/qpsk/p501_rx_fll/make_notebook_fll.py). The B210 side is the same GNU Radio flowgraphs.     python3 make_notebook_fe.py"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "notebook", "P501_QPSK_FE_Live.ipynb"))
cells = []


def md(text): cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)})
def code(text): cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip("\n").splitlines(True)})


md("""
# Live: the P501's FPGA QPSK modem with the 4th-power frequency estimator against a B210 and GNU Radio

The same link test as `P501_QPSK_FLL_Live.ipynb`, with the receiver of the overlay **`p501_qpsk_trx_fe`**: FLL -> polyphase matched filter and timing loop -> Costas loop, **plus the differential 4th-power estimator**.
915.0 MHz, 3.84 MSPS, 960 ksym/s differential QPSK, PRBS-15 data.

| direction | transmitter | receiver | what you watch |
|---|---|---|---|
| **A: B210 -> P501** | the B210 (GNU Radio flowgraph `qpsk_b210_tx.grc`, *Transmit ON*) | the **FPGA receiver** | here: constellation, bit errors counted in the FPGA, and the carrier offset as seen by the Costas loop, the FLL and the **estimator** |
| **B: P501 -> B210** | the **FPGA transmitter** (checkbox *Transmit*) | the B210 (flowgraph `qpsk_b210_rx.grc`) | in GNU Radio: constellation, BER box, spectrum |

**The estimator in one paragraph.** For every symbol it forms `d = m x conj(m_previous)` (the phase step between two symbols: `2 pi f T` plus a multiple of 90 degrees of data), takes the angle of `d` with a CORDIC, multiplies it by 4
(the data steps become multiples of 360 degrees and vanish), turns it into a unit vector with the sine table and adds the vectors of N symbols. The angle of the sum is `4 x 2 pi f T`: `f = atan2(ACC_IM, ACC_RE) / (8 pi) x 960 kHz`,
unambiguous for |f| < 120 kHz. The vector length over N is the *quality* (1 = clean, towards 0 = noise). It is **open loop**: no jitter, but one measurement per request. It looks at the symbols *after the FLL*, so it measures what the
FLL has left (the whole offset if the FLL is held at 0 Hz); the offset at the antenna is `estimate - FLL frequency`.

**Four ways to start the receiver** (dropdown *Method*), all without a frequency hint:
* **FLL + Costas**: the closed-loop chain of GNU Radio (`rx.acquire_fll()`).
* **Estimator -> derotator**: settle 2000 symbols, one window, load the FLL's derotator with minus the estimate, FLL loop off; the Costas loop only follows the rest (`rx.acquire_fe(apply="fll")`).
* **Estimator -> W0**: the same, then restart with the estimate as the Costas loop's initial frequency (`apply="w0"`).
* **Costas only**: wide loop, nothing else (the receiver of chapter 4d).

**Before you start**
* Overlay `p501_qpsk_trx_fe` copied to `/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fe/` (with `p501_qpsk.py`, `p501_qpsk_rx.py`, `p501_qpsk_rx_fll.py`, `p501_qpsk_rx_fe.py`), and the notebooks of `p501_fft_dds` (for `p501_radio.py`).
* Antennas on TX1 / RX1 of the P501 and on the TX/RX and RX2 ports of the B210, a few centimetres apart. **Very low power** (B210 TX gain 80 dB at most). Check the rules where you are before transmitting.
* **One direction at a time.** The transmit flowgraph starts with *Transmit OFF*, this notebook with *Transmit* unticked. **Start the transmitter first, then press Start receiver.**
* Everything ends quiet: the last cell (*Stop and silence*) turns the transmitter off and sets the TX attenuation to its maximum.
""")

md("## Configuration, overlay and bring-up")
code('''
BIT       = "/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fe/p501_qpsk_trx_fe.bit"   # transmitter + receiver with FLL and estimator in one overlay (the .hwh next to it)
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
sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fe')        # p501_qpsk.py, p501_qpsk_rx.py, p501_qpsk_rx_fll.py, p501_qpsk_rx_fe.py
import p501_radio
from p501_qpsk import P501QpskTx
from p501_qpsk_rx import soft_quality, constellation_ok, UNIT, REG
from p501_qpsk_rx_fe import P501QpskRxFe

results = {}
def check(name, ok, detail):
    results[name] = (bool(ok), detail)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

ol = Overlay(BIT)                                  # programs the PL
tx = P501QpskTx(ol.qpsk_regs, FS)                  # transmitter registers at 0x9C460000: enable, amplitude
rx = P501QpskRxFe(ol.qpsk_rx)                      # receiver registers at 0x9C470000 (the constructor checks the ID 0xDD520003: FLL AND estimator)
ad = p501_radio.bring_up(ol, LO, 4_000_000, TX_ATTEN0, RX_GAIN)     # the AD9361 over SPI; TX attenuation at its maximum during the calibrations
tx.off(); rx.stop()

a_tx, a_rx = ol.ip_dict["qpsk_regs"]["phys_addr"], ol.ip_dict["qpsk_rx"]["phys_addr"]
check("both blocks in the overlay", a_tx == 0x9C460000 and a_rx == 0x9C470000, f"qpsk_regs at 0x{a_tx:08X}, qpsk_rx at 0x{a_rx:08X}")
check("AD9361 up", ad.info["ok"], f"LO locks {ad.info['rx_lock']}/{ad.info['tx_lock']}, ENSM 0x{ad.info['ensm']:X}, calibrations {ad.info['calibrations']}")
''')

md("""
## Helpers

`restart_receiver()` stops, loads the gains and starts a cold receiver; with `use_fll=False` the FLL is held at 0 Hz, so the estimator sees the whole offset.
""")
code('''
def restart_receiver(acq_div=100, fll_gain=0.002, use_fll=True, f0_hz=0.0):
    """Stop, load the gains, start (cold start). use_fll=False holds the FLL at f0_hz."""
    rx.stop()
    rx.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=0.0)
    rx.ip.write(REG["FLL_F0"], int(round(f0_hz / FS * 2 ** 32)) & 0xFFFFFFFF)
    rx.set_fll(fll_gain); rx.fll_enable(use_fll)
    rx.start()
''')

md("""
## Self-test: FPGA transmitter -> FPGA receiver, inside the AD9361 (digital loopback)

No antennas, no B210. Same clock at both ends: no offset, so the FLL and the estimator must both read about 0 Hz, and the estimator's quality must be high (a clean signal).
""")
code('''
p501_radio.loopback(ad, True)
restart_receiver(400, use_fll=False)                   # FLL held at 0 Hz: the estimator sees the whole (zero) offset
tx.start(amp=0.5)                                      # PRBS-15 DQPSK from the FPGA transmitter
time.sleep(0.5); s0 = rx.stats()
time.sleep(2.0); s1 = rx.stats()
new_err = s1["mismatches"] - s0["mismatches"]; bits = s1["bits"] - s0["bits"]
e = rx.estimate_freq(n=2048, windows=8)
f_hz, ppm = rx.offsets(n=200)
z = rx.capture(); mag, spread = soft_quality(z)
tx.off(); rx.stop(); p501_radio.loopback(ad, False)

check("loopback: bits checked", bits > 3_000_000, f"{bits:,} bits in 2 s ({bits / 2 / 1e6:.2f} Mbit/s)")
check("loopback: no bit error after the pull-in", new_err == 0, f"{new_err} mismatches in {bits:,} bits ({s0['mismatches']} during the pull-in)")
check("loopback: constellation", constellation_ok(z), f"mean |z| {mag:.2f}, angular spread {spread:.1f} degrees")
check("loopback: estimator reads about 0 Hz", abs(e["f_hz"]) < 300, f"{e['f_hz']:+.1f} Hz (std over 8 windows {e['std_hz']:.1f} Hz), Costas {f_hz:+.1f} Hz")
check("loopback: estimator quality high", e["quality"] > 0.7, f"quality {e['quality']:.2f} (1 = clean, 0 = noise)")
check("loopback: no overruns", s1["overruns"] == 0, f"overruns {s1['overruns']}")
''')

md("""
## The live machinery

* `render()` draws one picture with NumPy and Pillow: the **constellation** (1024 soft symbols from the capture RAM), the **status**, and three strips: the **offset at the antenna** as the Costas loop (orange, `Costas - FLL`) and as the estimator (purple, `estimate - FLL`) see it,
  the **FLL** (green) and **Costas** (blue) frequencies, and the **mismatches per second**.
* `Live` runs `read registers -> estimator window -> read capture RAM -> picture` in a background thread. With *Auto-handover* ticked it takes the residual offset out of the derotator once a second (see *Controls*).
""")
code('''
import ipywidgets as widgets
from IPython.display import display, Image as IPImage
from PIL import Image as PILImage, ImageDraw, ImageFont

W, H = 840, 580
CX, CY, SC = 215, 220, 76                           # constellation centre and pixels per unit (axes +-2.5)
FONT = ImageFont.load_default()
HIST = 80
hist_t = [np.nan] * HIST; hist_e = [np.nan] * HIST; hist_fl = [np.nan] * HIST; hist_co = [np.nan] * HIST; hist_m = [np.nan] * HIST
# offset (Costas - FLL), offset (estimate - FLL), FLL, Costas (Hz), mismatches per second

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

def render(z, st, est, locked, mrate, note=""):
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
             f"FLL     {st['fll_hz']:+9.1f} Hz   {'loop on' if st['enabled'] else 'frozen / off'}",
             f"Costas  {st['costas_hz']:+9.1f} Hz",
             f"offset, Costas - FLL    {st['carrier_offset_hz']:+9.1f} Hz",
             (f"offset, estimator      {est['f_hz'] - st['fll_hz']:+9.1f} Hz   (residual {est['f_hz']:+.0f}, N {est['count']}, quality {est['quality']:.2f})" if est else "offset, estimator      -"),
             f"clock offset {st['clock_offset_ppm']:+8.1f} ppm (instantaneous)   AGC gain {st['agc_gain']:.2f}",
             f"|z| {mag:.2f}   spread {spread:.1f} deg"]
    for i, l in enumerate(lines): d.text((X, 62 + 16 * i), l, fill=(0, 0, 0), font=FONT)
    strip(d, X, 215, 340, 80, [(hist_t, (200, 120, 20)), (hist_e, (130, 50, 170))], "offset at the antenna: Costas - FLL (orange), estimator (purple) (Hz)")
    strip(d, X, 335, 340, 80, [(hist_fl, (30, 150, 60)), (hist_co, (31, 119, 180))], "FLL (green) and Costas (blue) frequency (Hz)")
    strip(d, X, 455, 340, 80, [(hist_m, (180, 40, 40))], "mismatches per second, 0 .. 1000", 0, 1000)
    buf = io.BytesIO(); img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()

class Live:
    """Background thread: registers + estimator window + capture RAM -> picture. Optional auto-handover once a second."""
    def __init__(self, image, status):
        self.image, self.status = image, status
        self.running, self.thread, self.frames = False, None, 0
        self.last_m, self.last_t = 0, time.time()
        self.locked, self.st, self.est = False, None, None
        self.paused = False                                      # set while a start procedure or an experiment uses the registers
        self.nwin, self.auto, self.t_auto = 2048, False, time.time()
        self.handovers = 0
    def _run(self):
        t_rate = time.time(); n_rate = 0; rate = 0.0
        while self.running:
            if self.paused:
                time.sleep(0.05); continue
            try:
                st = rx.stats()
                est = None
                if st["running"]:
                    z = rx.capture(); self.z = z                                 # capture() arms with CTRL = 1, 3: not while the receiver is stopped
                    est = rx.measure(self.nwin)
                else: z = getattr(self, "z", np.zeros(1024, dtype=complex))
                now = time.time(); dt = max(now - self.last_t, 1e-3)
                mrate = (st["mismatches"] - self.last_m) / dt if st["mismatches"] >= self.last_m else 0.0
                self.last_m, self.last_t = st["mismatches"], now
                self.locked = bool(st["running"] and mrate == 0 and st["bits"] > 0 and constellation_ok(z))
                if self.auto and self.locked and est and est["quality"] > 0.4 and now - self.t_auto > 1.0:
                    rx.handover(n=4096, windows=2); self.handovers += 1; self.t_auto = now
                for h, v in ((hist_t, st["carrier_offset_hz"]), (hist_e, est["f_hz"] - st["fll_hz"] if est else np.nan), (hist_fl, st["fll_hz"]), (hist_co, st["costas_hz"]), (hist_m, mrate)): h.pop(0); h.append(v)
                self.st, self.est = st, est
                self.image.value = render(z, st, est, self.locked, mrate, f"{rate:.1f} pictures/s" + (f"   auto-handovers {self.handovers}" if self.auto else ""))
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
p501_radio.loopback(ad, True); restart_receiver(100); tx.start(amp=0.5); time.sleep(0.3)
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
* **Method** and **Start receiver**: the four ways listed at the top. *Acq. window* is the estimator's window for the two estimator methods (1024 symbols = 1.1 ms); the receiver settles 2000 symbols before it measures. The status line shows what was found.
* **Use the FLL** (loop on): untick it to hold the FLL's frequency (it keeps derotating). **Freeze FLL**: loads the FLL with its mean and stops its loop (as in the FLL notebook).
* **Handover now**: measures the offset the estimator still sees (window *Live window*, 3 windows), subtracts it from the derotator's frequency and stops the FLL loop. The Costas loop, which had been following that residual, then has about nothing to do.
  **Auto-handover** does this once a second while locked (and the estimator's quality is above 0.4): a slow, quiet closed loop made of estimator measurements instead of the noisy FLL. Try it with someone moving near the antennas.
* **Live window**: the estimator window of the live display (the purple curve): 256 .. 16384 symbols, the longer the quieter. **Live loop N**: the timing and Costas loops. **RX gain**, **Digital loopback**.

**Transmitter (direction B)**: **P501 transmits** (off at the start; do not tick it while the B210's *Transmit* is ON), **TX attenuation** (20 dB .. 89.75 dB; start at 40 dB), **Amplitude**.

**Start display / Stop display**: the live picture; stopping it does not stop the transmitter or the receiver.

To test a larger offset, set the frequency of the B210 flowgraph a few tens of kHz away from 915.0 MHz (for instance 915.03 MHz): the estimator follows it up to about 110 kHz.
""")
code('''
w_meth  = widgets.Dropdown(options=[("FLL + Costas", "fll"), ("Estimator -> derotator", "fe-fll"), ("Estimator -> W0", "fe-w0"), ("Costas only", "costas")], value="fe-fll", description="Method", layout=widgets.Layout(width="320px"))
w_acq   = widgets.Dropdown(options=[50, 100, 200, 400], value=100, description="Acquisition N", layout=widgets.Layout(width="200px"))
w_trk   = widgets.Dropdown(options=[("200", 200), ("400", 400), ("800", 800), ("1600", 1600)], value=400, description="Tracking M", layout=widgets.Layout(width="200px"))
w_awin  = widgets.Dropdown(options=[256, 512, 1024, 2048, 4096], value=1024, description="Acq. window", layout=widgets.Layout(width="200px"))
w_win   = widgets.Dropdown(options=[256, 512, 1024, 2048, 4096, 16384], value=2048, description="Live window", layout=widgets.Layout(width="200px"))
w_usefll = widgets.Checkbox(value=True, description="Use the FLL (loop on)", layout=widgets.Layout(width="300px"))
w_auto  = widgets.Checkbox(value=False, description="Auto-handover (estimator -> derotator, once a second)", layout=widgets.Layout(width="480px"))
w_live  = widgets.IntSlider(value=400, min=50, max=1600, step=10, description="Live loop N", continuous_update=False, layout=widgets.Layout(width="520px"))
w_rxg   = widgets.IntSlider(value=RX_GAIN, min=0, max=76, description="RX gain", continuous_update=False, layout=widgets.Layout(width="520px"))
w_tx    = widgets.Checkbox(value=False, description="P501 transmits (direction B)")
w_att   = widgets.FloatSlider(value=40.0, min=20.0, max=89.75, step=0.25, description="TX atten (dB)", continuous_update=False, layout=widgets.Layout(width="520px"))
w_amp   = widgets.FloatSlider(value=0.5, min=0.05, max=1.0, step=0.05, description="TX amplitude", continuous_update=False, layout=widgets.Layout(width="520px"))
w_loop  = widgets.Checkbox(value=False, description="Digital loopback")
b_rx    = widgets.Button(description="Start receiver", button_style="success")
b_rxoff = widgets.Button(description="Stop receiver", button_style="warning")
b_frz   = widgets.Button(description="Freeze FLL", button_style="primary")
b_hand  = widgets.Button(description="Handover now", button_style="primary")
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
        for h in (hist_t, hist_e, hist_fl, hist_co, hist_m): h[:] = [np.nan] * HIST
        m = w_meth.value
        if m == "fll":
            r = rx.acquire_fll(acq_div=w_acq.value, track_div=w_trk.value)
            msg = lambda r: f"FLL {r['fll_hz']:+.0f} Hz, Costas {r['costas_hz']:+.0f} Hz, offset {r['total_hz']:+.0f} Hz"
        elif m in ("fe-fll", "fe-w0"):
            r = rx.acquire_fe(n=w_awin.value, acq_div=w_acq.value, track_div=w_trk.value, apply="fll" if m == "fe-fll" else "w0")
            msg = lambda r: f"estimate {r['f_hz']:+.0f} Hz (quality {r['quality']:.2f}), Costas {r['costas_hz']:+.0f}, FLL {r['fll_hz']:+.0f}, offset {r['total_hz']:+.0f} Hz"
        else:
            rx.fll_enable(False); rx.ip.write(REG["FLL_F0"], 0)
            r = rx.acquire(hints_hz=(0.0,), track_div=w_trk.value, acq_div=w_acq.value)
            r.update(costas_hz=rx._omega_hz(), seconds=r["seconds"]); msg = lambda r: f"Costas {r['costas_hz']:+.0f} Hz"
        status.value = (f"locked after {r['tries']} try(ies), {r['seconds']:.2f} s: " + msg(r)) if r["locked"] else "NOT locked: no signal, or too weak (raise the B210 TX gain)"
        w_usefll.value = (m == "fll"); w_live.value = w_trk.value
    finally:
        live.paused = False

def do_freeze(_=None):
    live.paused = True; time.sleep(0.15)
    try:
        f = rx.freeze_fll(); w_usefll.value = False
        status.value = f"FLL frozen at {f:+.0f} Hz; the Costas loop follows the rest"
    finally:
        live.paused = False

def do_handover(_=None):
    live.paused = True; time.sleep(0.15)
    try:
        h = rx.handover(n=max(w_win.value, 1024), windows=3); w_usefll.value = False
        status.value = f"handover: residual {h['residual_hz']:+.0f} Hz taken out of the derotator (now {h['new_fll_hz']:+.0f} Hz), quality {h['quality']:.2f}"
    finally:
        live.paused = False

def do_tx(change=None):
    if w_tx.value:
        ad.set_tx_atten_db(w_att.value); tx.start(amp=w_amp.value)
    else:
        tx.off(); p501_radio.quiet(ad, TX_ATTEN0)

b_rx.on_click(guard(do_start_receiver)); b_rxoff.on_click(guard(lambda b: rx.stop())); b_frz.on_click(guard(do_freeze)); b_hand.on_click(guard(do_handover))
b_start.on_click(guard(lambda b: live.start())); b_stop.on_click(guard(lambda b: live.stop()))
w_win.observe(guard(lambda c: setattr(live, "nwin", c["new"])), names="value")
w_auto.observe(guard(lambda c: (setattr(live, "auto", c["new"]), setattr(live, "t_auto", time.time()))), names="value")
w_live.observe(guard(lambda c: rx.set_loops(2 * np.pi / c["new"], 2 * np.pi / c["new"])), names="value")
w_usefll.observe(guard(lambda c: rx.fll_enable(c["new"])), names="value")
w_rxg.observe(guard(lambda c: ad.set_rx_manual_gain(c["new"])), names="value")
w_loop.observe(guard(lambda c: p501_radio.loopback(ad, c["new"])), names="value")
w_tx.observe(guard(do_tx), names="value")
w_att.observe(guard(lambda c: ad.set_tx_atten_db(c["new"]) if w_tx.value else None), names="value")
w_amp.observe(guard(lambda c: tx.set(amp=c["new"]) if w_tx.value else None), names="value")

display(widgets.VBox([widgets.HBox([b_rx, b_frz, b_hand, b_rxoff, b_start, b_stop, status]), widgets.HBox([w_meth, w_awin, w_win]), widgets.HBox([w_acq, w_trk]), widgets.HBox([w_usefll, w_auto]),
                      w_live, w_rxg, widgets.HBox([w_tx, w_loop]), w_att, w_amp, image]))
''')

md("""
### Check the controls (optional)

Moves the controls from Python, the way clicks would, with the digital loopback (no B210 needed): starts the receiver with each of the four methods, then the handover and the auto-handover.
""")
code('''
w_loop.value = True
w_att.value = 60.0
w_tx.value = True                                    # the transmitter first (digital loopback; the antenna sees only a very weak signal at 60 dB attenuation) ...
time.sleep(0.3)
b_start.click()
for meth in ("fll", "fe-fll", "fe-w0", "costas"):
    w_meth.value = meth
    b_rx.click()                                     # ... then the receiver
    time.sleep(0.5)
    check(f"start receiver, method {meth}", status.value.startswith("locked"), status.value)
w_meth.value = "fe-fll"; b_rx.click(); time.sleep(0.3)
b_hand.click(); time.sleep(0.5)
check("handover now", status.value.startswith("handover") and not rx.fll_status()["enabled"], status.value)
w_auto.value = True; time.sleep(3.0)
check("auto-handover ran, still locked", live.handovers >= 1 and live.locked, f"{live.handovers} handovers in 3 s, locked = {live.locked}")
w_auto.value = False
w_win.value = 4096; time.sleep(0.5)
check("live window", live.nwin == 4096 and live.est is not None and live.est["count"] == 4096, f"window {live.nwin}, last count {live.est['count'] if live.est else None}")
w_live.value = 100; time.sleep(0.3)
check("live loop slider", rx.ip.read(0x0C) > 10000, f"TB register now {rx.ip.read(0x0C)}")
w_amp.value = 0.3; check("amplitude slider", abs(tx.amp - 0.3) < 0.01, f"transmitter amplitude {tx.amp:.2f}")
b_stop.click(); display(IPImage(image.value))
w_tx.value = False; w_loop.value = False; w_usefll.value = True; b_rxoff.click()
check("transmitter off again", not tx.enabled, f"enabled = {tx.enabled}")
''')

md("""
## Experiment 1: accuracy of the estimator against the window, and the FLL's scatter (direction A)

Needs the B210 flowgraph transmitting (*Transmit* ON, TX gain 80). The FLL is held at 0 Hz and the Costas loop locks; its long-run mean is the reference. Then the estimator measures 20 windows for each N:
mean minus reference (the bias) and the standard deviation. For comparison the FLL (loop on, narrow gain) is run for a second and the scatter of its frequency is printed.
Earlier results: std 117 Hz at N = 1024, 58 Hz at 2048, 19 Hz at 16384, bias below 70 Hz; the FLL about 1000 Hz.
""")
code('''
def accuracy_experiment(ns=(128, 256, 512, 1024, 2048, 4096, 16384), windows=20):
    live.stop(); live.paused = True
    rx.fll_enable(False); rx.ip.write(REG["FLL_F0"], 0)
    r = rx.acquire(hints_hz=(0.0,))
    if not r["locked"]:
        print("No B210 signal found (the receiver does not lock): start the flowgraph, set Transmit to ON (TX gain 80), and run this cell again."); live.paused = False; return None
    from p501_qpsk_rx import _signed, SYMBOL_RATE
    co = np.array([_signed(rx.ip.read(REG["OMEGA"])) / 2 ** 32 * SYMBOL_RATE for _ in range(400) if not time.sleep(0.003)])
    print(f"reference: Costas mean {co.mean():+.1f} Hz (std of the readings {co.std():.0f} Hz), AGC gain {rx.stats()['agc_gain']:.2f}")
    print(f"{'N':>7}{'time':>10}{'mean':>12}{'bias':>9}{'std':>9}{'quality':>9}")
    rows = []
    for n in ns:
        es = [rx.measure(n) for _ in range(windows)]
        f = np.array([e["f_hz"] for e in es]); q = np.mean([e["quality"] for e in es]); rows.append((n, f.mean(), f.std(), q))
        print(f"{n:>7}{n / 960.0:>8.1f}ms{f.mean():>10.1f}Hz{f.mean() - co.mean():>7.1f}Hz{f.std():>7.1f}Hz{q:>9.2f}")
    r = rx.acquire_fll()
    fl = np.array([rx.fll_status()["fll_hz"] for _ in range(400) if not time.sleep(0.003)])
    print(f"FLL (loop on, narrow gain): locked {r['locked']}, frequency mean {fl.mean():+.1f} Hz, std {fl.std():.1f} Hz (instantaneous readings)")
    live.paused = False
    return rows

acc = accuracy_experiment()
''')

md("""
## Experiment 2: lock from a cold start with the four methods (direction A)

Each method starts the receiver cold, with no hint, and the cell polls the mismatch counter without a pause: the time of the last change is the time to lock. Needs the B210 transmitting. Try it at the natural +9.7 kHz offset
and with the B210 frequency moved by +30 kHz, -60 kHz or +100 kHz (flowgraph frequency 915.03, 914.94 or 915.1 MHz); the Costas loop alone becomes slow and unreliable above about 80 kHz.
Earlier results at +9.7 kHz: Costas 0.5 ms, FLL 0.2 ms, estimator 3.5 ms (2000 symbols settling + 1024 window), all 10/10.
""")
code('''
def lock_experiment(trials=6, methods=("costas", "fll", "fe-fll", "fe-w0")):
    live.stop(); live.paused = True
    restart_receiver(100, use_fll=False); time.sleep(0.01)                  # is there a signal? the estimator's quality says so (about 0.8 for the B210, 1.0 in the loopback, below 0.1 for noise)
    probe = rx.measure(2048)
    if probe["quality"] < 0.3:
        print(f"No B210 signal found (estimator quality {probe['quality']:.2f}): start the flowgraph, set Transmit to ON (TX gain 80), and run this cell again."); rx.stop(); live.paused = False; return None
    print(f"offset of the signal about {probe['f_hz']:+.0f} Hz (estimator quality {probe['quality']:.2f})")
    out = {}
    for m in methods:
        rs = [rx.timed_lock(m) for _ in range(trials)]
        ok = [r for r in rs if r["locked"]]; out[m] = rs
        tot = [r["costas_hz"] - r["fll_hz"] for r in ok]
        print(f"{m:<8} locked {len(ok):2d}/{trials}   lock time median {np.median([r['ms'] for r in ok]) if ok else float('nan'):6.1f} ms (max {max([r['ms'] for r in ok]) if ok else float('nan'):6.1f})"
              f"   offset mean {np.mean(tot) if tot else float('nan'):+9.1f} Hz, std {np.std(tot) if len(tot) > 1 else 0:6.1f} Hz")
    rx.stop(); live.paused = False
    return out

locks = lock_experiment()
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
