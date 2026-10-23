#!/usr/bin/env python3
"""Writes notebook/P501_QAM16_Live.ipynb: the interactive test of the 16-QAM link with the Zadoff-Chu frame synchroniser in the P501 FPGA (overlay p501_qam16_trx), against the FPGA's own
transmitter (digital loopback or over the air) or the B210 (tutorial/qam16/qam16_frame_tx.py).     python3 make_notebook_qam16.py"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "notebook", "P501_QAM16_Live.ipynb"))
cells = []


def md(text): cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)})
def code(text): cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip("\n").splitlines(True)})


md("""
# Live: 16-QAM with a Zadoff-Chu frame sync word, in the P501 FPGA, against its own transmitter or a B210

The receiver of the overlay **`p501_qam16_trx`** decodes a continuous 16-QAM stream, 915.0 MHz, 3.84 MSPS, 960 ksym/s, root-raised-cosine 0.35, **all in the FPGA**:
band-edge **FLL** -> polyphase matched filter and **timing loop** -> power **AGC** -> **Zadoff-Chu frame synchroniser** -> carrier **PLL** (pilot and decision directed) -> 16-QAM slicer -> PRBS-15 symbol and bit error counters.

**The frame** (967 symbols = 1.007 ms, 992.8 frames per second, sent by the FPGA's own transmitter `qam16_tx_fr` or by the B210): `CP 8 | ZC word 63 | 14 x (63 16-QAM symbols + 1 pilot)`:
the **Zadoff-Chu word** (root 1, constant amplitude, the 8-symbol cyclic prefix before it) is found by a 63-tap correlator with an energy normalisation (|C| / sum|x|, threshold 0.6 to search, 0.45 inside the +-4 symbol window of the next frame);
**two words one frame apart lock** the tracker (a miss is dead-reckoned, 3 misses in a row search again). The word gives **the frequency** (arg of the two half-word correlations, +-15 kHz) **and the phase** of the carrier to the PLL at the lock, the known word, CP and **pilots** (+-1, every 64th symbol) keep it on the carrier, the payload is the PRBS-15 restarted in every frame (882 data symbols).
* The synchroniser needs the frequency error below +-6 kHz (the word is unambiguous within Rs/2N = 7.6 kHz). The natural offset of the P501 and the B210 is **+9.6 kHz**: the **FLL** takes most of it away first. Its *tracking gain* matters: 0.0003 puts 1 to 4 kHz of jitter into the signal and the PLL loses the carrier below 14 dB SNR; **0.0001 (the default here)** keeps it down to about 12 dB.
* **Lock and quality**: *LOCKED* = the synchroniser has locked and the PLL runs on the frames. **EVM** and the **symbol / bit error rate** are measured on the 882 data symbols of every frame against the PRBS-15. 16-QAM needs about -16 dB EVM for a symbol error rate of 1e-3.

**Before you start**
* Overlay `p501_qam16_trx` in `/home/xilinx/jupyter_notebooks/p501_qam16/` (with `p501_qam16_rx.py`) and the notebooks of `p501_fft_dds` (for `p501_radio.py`, `p501_dds.py`).
* Transmitter: **the P501's own** (the *FPGA transmits* control: digital loopback, or over the air from TX1 to RX1 with **TX atten 20 to 30 dB**) **or the B210**: `python3 tutorial/qam16/qam16_frame_tx.py --tx-gain 80 --rms 0.35 --seconds 600` on the host (antennas a few centimetres apart; check the rules where you are before transmitting).
* **Start the transmitter first, then press Start receiver.**
* Everything ends quiet: the last cell (*Stop and silence*) turns the transmitter off and sets the TX attenuation to its maximum.
""")

md("## Configuration, overlay and bring-up")
code('''
BIT       = "/home/xilinx/jupyter_notebooks/p501_qam16/p501_qam16_trx.bit"   # FPGA 16-QAM frame transmitter + receiver with the FLL and the ZC synchroniser (the .hwh next to it)
FS        = 3_840_000          # sample rate
LO        = 915_000_000        # carrier, Hz
RX_GAIN   = 70                 # P501 RX gain-table index 0..76 (70 for the weak signal through the air)
TX_ATTEN0 = 89.75              # TX attenuation (dB) at the start and at the end: the transmitter is silent
FRAME     = 967                # symbols per frame
''')
code('''
import sys, time, os, io, threading
import numpy as np
from pynq import Overlay

sys.path.insert(0, '/home/xilinx/jupyter_notebooks')
sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds')            # p501_radio.py, p501_dds.py
sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qam16')              # p501_qam16_rx.py
import p501_radio
import importlib, p501_qam16_rx
importlib.reload(p501_qam16_rx)                                              # a module that is already imported is not re-read: reload, so that a newer file is used without restarting the kernel
from p501_qam16_rx import P501Qam16Rx, P501Qam16Tx, REG, SYMBOL_RATE, R_UNIT, _signed
print('driver:', p501_qam16_rx.__file__)
_need = [m for m in ("acquire", "set_pll", "set_sync", "hold_fll", "stats", "capture", "set_fll") if not hasattr(P501Qam16Rx, m)]
assert not _need, f"p501_qam16_rx.py is older than this notebook (missing {_need}): copy notebook/p501_qam16_rx.py again to /home/xilinx/jupyter_notebooks/p501_qam16/ and RESTART THE KERNEL (a module that is already imported is not re-read)"

results = {}
def check(name, ok, detail):
    results[name] = (bool(ok), detail)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

ol = Overlay(BIT)                                  # programs the PL
tx = P501Qam16Tx(ol.qpsk_regs, FS)                 # transmitter registers at 0x9C460000: enable, amplitude (the frame transmitter qam16_tx_fr sits behind them)
rx = P501Qam16Rx(ol.qam16_rx)                      # receiver registers at 0x9C470000 (the constructor checks the ID 0xDD520006)
ad = p501_radio.bring_up(ol, LO, 4_000_000, TX_ATTEN0, RX_GAIN)     # the AD9361 over SPI; TX attenuation at its maximum during the calibrations
tx.off(); rx.stop()

a_tx, a_rx = ol.ip_dict["qpsk_regs"]["phys_addr"], ol.ip_dict["qam16_rx"]["phys_addr"]
check("both blocks in the overlay", a_tx == 0x9C460000 and a_rx == 0x9C470000, f"qpsk_regs at 0x{a_tx:08X}, qam16_rx at 0x{a_rx:08X}")
check("AD9361 up", ad.info["ok"], f"LO locks {ad.info['rx_lock']}/{ad.info['tx_lock']}, ENSM 0x{ad.info['ensm']:X}, calibrations {ad.info['calibrations']}")
''')

md("""
## Self-test: the FPGA transmitter into the FPGA receiver, inside the AD9361 (digital loopback)

No antennas, no B210. First the **transmitter is off**: the receiver must not find a frame in the noise (no false lock). Then the FPGA sends **frames** at three amplitudes: the receiver must lock within a few tens of milliseconds, find every frame (992.8 per second),
decode the 882 data symbols of every frame **without an error**, with an EVM better than -25 dB, and without lateness anywhere (synchroniser, events, FLL, engine overruns).
""")
code('''
p501_radio.loopback(ad, True); ad.set_tx_atten_db(20.0)
tx.off(); rx.stop(); time.sleep(0.05)
r0 = rx.acquire(timeout_s=0.6); time.sleep(0.4); s0 = rx.stats(); rx.stop()
check("no transmitter: no false lock", (not r0["locked"]) and s0["locks"] == 0, f"locked = {r0['locked']}, peaks {s0['peaks']}, locks {s0['locks']}")

for amp in (0.15, 0.25, 0.4):
    tx.off(); rx.stop(); time.sleep(0.05); tx.start(amp=amp); time.sleep(0.05)
    r = rx.acquire(); time.sleep(0.2)
    a = rx.stats(); time.sleep(1.5); b = rx.stats()
    nf = b["frames"] - a["frames"]; ns = b["sym_cnt"] - a["sym_cnt"]; ne = b["sym_err"] - a["sym_err"]
    check(f"loopback amp {amp}: locks", r["locked"], f"{r['seconds'] * 1e3:.0f} ms (FLL {r['fll_hz']:+.0f} Hz, lock estimate {b['lock_w_hz']:+.0f} Hz)")
    check(f"loopback amp {amp}: every frame found", abs(nf - 1.5 * SYMBOL_RATE / FRAME) < 3 and b["misses"] == 0 and b["lost"] == 0, f"{nf} frames in 1.5 s (expected {1.5 * SYMBOL_RATE / FRAME:.0f}), misses {b['misses']}, lost {b['lost']}")
    check(f"loopback amp {amp}: payload without an error", ne == 0 and ns > 1_000_000, f"{ne} symbol errors in {ns:,} symbols, BER {b['ber']:.1e}")
    check(f"loopback amp {amp}: EVM", b["evm_db"] < -25, f"{b['evm_db']:.1f} dB, AGC gain {b['agc_gain']:.2f}, clock {b['clock_offset_ppm']:+.1f} ppm")
    check(f"loopback amp {amp}: nothing late", b["sy_late"] == 0 and b["ev_late"] == 0 and b["ev_over"] == 0 and b["fll_late"] == 0 and b["engine_overruns"] == 0 and not b["overrun"],
          f"sync {b['sy_late']}, events {b['ev_late']}/{b['ev_over']}, FLL {b['fll_late']}, overruns {b['engine_overruns']}")
tx.off(); rx.stop(); p501_radio.loopback(ad, False)
''')

md("""
## The live machinery

* `render()` draws one picture with NumPy and Pillow: the **constellation** of the 882 data symbols (the last 1024 soft symbols after the PLL; the red crosses are the 16 ideal points), the **status** (lock, frames, symbol and bit error rate since the start and over the last 2 s, EVM of the last frame and of the picture, AGC gain, clock offset in ppm,
  the frequencies of the FLL, of the PLL and the carrier offset they add up to, the synchroniser's counters) and three strips: the **frequencies** (FLL blue, PLL purple, offset green), the **frames per second** (expected 992.8) and the **symbol errors per second**.
* `Live` runs `read registers -> read capture RAM -> picture` in a background thread, so the controls stay responsive.
""")
code('''
import ipywidgets as widgets
from IPython.display import display, Image as IPImage
from PIL import Image as PILImage, ImageDraw, ImageFont

W, H = 860, 620
CX, CY, SC = 215, 230, 125                          # constellation centre and pixels per unit (axes +-1.6)
FONT = ImageFont.load_default()
HIST = 80
LEV = np.array([-3, -1, 1, 3]) / np.sqrt(10)
hist_fll = [np.nan] * HIST; hist_pll = [np.nan] * HIST; hist_off = [np.nan] * HIST; hist_fr = [np.nan] * HIST; hist_er = [np.nan] * HIST

def base_frame():
    img = PILImage.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(img)
    d.rectangle([CX - 1.6 * SC, CY - 1.6 * SC, CX + 1.6 * SC, CY + 1.6 * SC], outline=(90, 90, 90))
    for u in (-1, 0, 1):
        d.line([CX + u * SC, CY - 1.6 * SC, CX + u * SC, CY + 1.6 * SC], fill=(225, 225, 225)); d.line([CX - 1.6 * SC, CY - u * SC, CX + 1.6 * SC, CY - u * SC], fill=(225, 225, 225))
    d.text((CX - 90, CY + 1.6 * SC + 6), "soft symbols after the PLL (data of the payload)", fill=(60, 60, 60), font=FONT)
    return img
BASE = base_frame()

def strip(d, x0, y0, w, h, series, label, lo=None, hi=None, fmt="{:.0f}"):
    d.rectangle([x0, y0, x0 + w, y0 + h], outline=(150, 150, 150)); d.text((x0, y0 - 12), label, fill=(60, 60, 60), font=FONT)
    allv = np.concatenate([np.asarray(s, dtype=float) for s, _ in series]); allv = allv[~np.isnan(allv)]
    if lo is None:
        c = float(np.median(allv)) if len(allv) else 0.0; span = max(2000.0, 1.2 * (float(allv.max() - allv.min()) if len(allv) else 0.0))
        lo, hi = c - span / 2, c + span / 2
    for data, color in series:
        pts = [(x0 + i * w / (len(data) - 1), y0 + h - (min(max(v, lo), hi) - lo) / (hi - lo) * h) for i, v in enumerate(data) if not np.isnan(v)]
        if len(pts) > 1: d.line(pts, fill=color, width=1)
    d.text((x0 + w + 4, y0 - 2), fmt.format(hi), fill=(100, 100, 100), font=FONT); d.text((x0 + w + 4, y0 + h - 9), fmt.format(lo), fill=(100, 100, 100), font=FONT)

def soft_evm_db(z):
    """EVM of the soft symbols against the nearest ideal point"""
    z = np.asarray(z)
    e = np.min(np.abs(z.real[:, None] - LEV[None, :]), axis=1) ** 2 + np.min(np.abs(z.imag[:, None] - LEV[None, :]), axis=1) ** 2
    return 10 * np.log10(max(float(np.mean(e)), 1e-12))

def render(z, st, frate, erate, ser_recent, note=""):
    img = BASE.copy(); d = ImageDraw.Draw(img)
    for a, b in zip(np.asarray(z).real, np.asarray(z).imag):
        x, yy = CX + a * SC, CY - b * SC
        if abs(a) < 1.6 and abs(b) < 1.6: d.rectangle([x - 1, yy - 1, x + 1, yy + 1], fill=(31, 119, 180))
    for a in LEV:                                                                   # the 16 ideal points, on top of the symbols
        for b in LEV:
            x, y = CX + a * SC, CY - b * SC
            d.line([x - 7, y, x + 7, y], fill=(220, 40, 40)); d.line([x, y - 7, x, y + 7], fill=(220, 40, 40))
    X = 470
    ok = st["locked"] and st["run_active"]
    d.text((X, 20), "LOCKED: frames decoded" if ok else ("frame sync locked, waiting" if st["locked"] else "NOT LOCKED"), fill=(30, 140, 50) if ok else (200, 40, 40), font=FONT)
    d.text((X, 36), note, fill=(110, 110, 110), font=FONT)
    fmt = lambda v: "-" if v != v else (f"{v:.1e}" if v else "0")
    lines = [f"frames {st['frames']:>9,}  ({frate:.0f}/s of 992.8)   bad frames {st['bad_frames']}",
             f"symbols checked {st['sym_cnt']:>11,}   errors {st['sym_err']:>8,}",
             f"SER {fmt(st['ser'])} since start,  {fmt(ser_recent)} last 2 s",
             f"BER {fmt(st['ber'])} since start   (4 bits per symbol)",
             f"EVM {st['evm_db']:.1f} dB (last frame)  {soft_evm_db(z):.1f} dB (this picture)",
             f"AGC gain {st['agc_gain']:.2f}   clock {st['clock_offset_ppm']:+.1f} ppm",
             f"FLL {st['fll_hz']:+8.0f} Hz   PLL {st['pll_hz']:+8.0f} Hz   carrier offset {st['pll_hz'] - st['fll_hz']:+8.0f} Hz",
             f"sync: peaks {st['peaks']}  locks {st['locks']}  hits {st['hits']:,}  misses {st['misses']}  lost {st['lost']}",
             f"late: sync {st['sy_late']}  events {st['ev_late']}/{st['ev_over']}  FLL {st['fll_late']}  engine overruns {st['engine_overruns']}"]
    for i, l in enumerate(lines): d.text((X, 62 + 16 * i), l, fill=(0, 0, 0), font=FONT)
    strip(d, X, 230, 340, 80, [(hist_fll, (31, 119, 180)), (hist_pll, (130, 50, 170)), (hist_off, (30, 150, 60))], "FLL (blue), PLL (purple), carrier offset (green) in Hz")
    strip(d, X, 350, 340, 80, [(hist_fr, (30, 150, 60))], "frames per second (0 .. 1200)", 0, 1200)
    strip(d, X, 470, 340, 80, [(hist_er, (180, 40, 40))], "symbol errors per second (0 .. 20,000)", 0, 20000)
    buf = io.BytesIO(); img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()

class Live:
    """Background thread: registers + capture RAM -> picture."""
    def __init__(self, image, status):
        self.image, self.status = image, status
        self.running, self.thread, self.frames = False, None, 0
        self.last, self.last_t = None, time.time()
        self.st = None
        self.z = np.zeros(1024, dtype=complex)
        self.win = []                                            # (time, symbols, errors) of the last 2 s
        self.paused = False                                      # set while a start procedure or an experiment uses the registers
    def _run(self):
        t_rate = time.time(); n_rate = 0; rate = 0.0
        while self.running:
            if self.paused:
                time.sleep(0.05); continue
            try:
                st = rx.stats()
                if st["running"] and st["run_active"]:
                    try: self.z = rx.capture()
                    except TimeoutError: pass
                z = self.z
                now = time.time(); dt = max(now - self.last_t, 1e-3)
                if self.last is not None and st["frames"] >= self.last[0] and st["sym_err"] >= self.last[1]:
                    frate = (st["frames"] - self.last[0]) / dt; erate = (st["sym_err"] - self.last[1]) / dt
                else: frate, erate = 0.0, 0.0
                self.last, self.last_t = (st["frames"], st["sym_err"]), now
                for h, v in ((hist_fll, st["fll_hz"]), (hist_pll, st["pll_hz"]), (hist_off, st["pll_hz"] - st["fll_hz"]), (hist_fr, frate), (hist_er, erate)): h.pop(0); h.append(v)
                self.st = st
                self.win.append((now, st["sym_cnt"], st["sym_err"])); self.win = [w for w in self.win if now - w[0] <= 2.0]
                ser_recent = float("nan")
                if len(self.win) > 1 and self.win[-1][1] > self.win[0][1] and self.win[-1][2] >= self.win[0][2]:
                    ser_recent = (self.win[-1][2] - self.win[0][2]) / (self.win[-1][1] - self.win[0][1])
                self.image.value = render(z, st, frate, erate, ser_recent, f"{rate:.1f} pictures/s")
                self.frames += 1; n_rate += 1
                if now - t_rate > 2: rate = n_rate / (now - t_rate); t_rate = now; n_rate = 0
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

A few pictures of the digital loopback with the FPGA frames: the display must say *LOCKED* and show 16 clusters.
""")
code('''
p501_radio.loopback(ad, True); ad.set_tx_atten_db(20.0); tx.start(amp=0.25); time.sleep(0.05); rx.acquire(); time.sleep(0.3)
img_w, st_w = widgets.Image(format="png"), widgets.Label()
lv = Live(img_w, st_w)
lv.start(); time.sleep(3); lv.stop()
fps = lv.frames / 3.0
check("live pictures", lv.frames > 4 and len(img_w.value) > 2000, f"{lv.frames} pictures in 3 s ({fps:.1f}/s), status: {st_w.value}")
check("live: locked, 16 clusters", lv.st is not None and lv.st["locked"] and soft_evm_db(lv.z) < -22, f"locked = {lv.st['locked']}, soft EVM {soft_evm_db(lv.z):.1f} dB")
display(IPImage(img_w.value))
tx.off(); rx.stop(); p501_radio.loopback(ad, False)
''')

md("""
## Controls

**Receiver**
* **Start receiver** (cold start): the registers are written, the FLL runs with its **acquiring gain** for 20 ms and then with its **tracking gain**, the receiver waits for the lock. *FLL mode* **track**: the FLL keeps tracking (quiet at 0.0001); **hold**: after the lock the FLL is loaded with its mean frequency and stopped (a constant derotation, the PLL tracks the rest, +-4 kHz); **off**: no FLL (the natural +9.6 kHz of the B210 is then too much for the frame sync: try it).
* **FLL tracking gain**: 0.00003 to 0.001 (live, *Apply*). **Hold FLL now** freezes it at its present mean frequency, whatever the mode.
* **PLL bandwidth** (rad per symbol, 0.005 to 0.06), **known CP / word symbols in the loop** (aided), **pilot weight** (1, 3, 5) and **timing loop 2 pi / N** (200, 400, 800): live (*Apply*). Narrower than 0.015 cannot follow the FLL's residual jitter, wider than 0.04 adds noise.
* **Sync threshold** (search 154 = 0.60 of 256, lock 115 = 0.45), **frames after a lock before the acquisition mode ends** (4: the timing loop and the AGC are wide and fast until then).
* **RX gain**: the AD9361's receive gain index. **Digital loopback**: the chip feeds the transmitter into the receiver without an antenna.
* **FPGA transmits**: *frames* (with *Digital loopback*, or over the air from TX1 to RX1 with **TX atten 20 to 30 dB**) or *off*. **TX amplitude** 0.05 to 0.6 (digital: 0.25 gives a DAC peak of about 12,800 counts; the digital loopback works from 0.15 to 0.4 at an EVM of -30 dB). Start the transmitter first, then **Start receiver**.

**Start display / Stop display**: the live picture; stopping it does not stop the receiver.
""")
code('''
w_fmode = widgets.Dropdown(options=[("track: the FLL keeps tracking", "track"), ("hold: freeze the FLL after the lock", "hold"), ("off: no FLL", "off")], value="track", description="FLL mode", layout=widgets.Layout(width="420px"))
w_agi   = widgets.Dropdown(options=[0.001, 0.002, 0.004], value=0.002, description="FLL acq. gain", layout=widgets.Layout(width="240px"))
w_tgi   = widgets.Dropdown(options=[0.00003, 0.0001, 0.0003, 0.001], value=0.0001, description="FLL track gain", layout=widgets.Layout(width="260px"))
w_bw    = widgets.FloatSlider(value=0.02, min=0.005, max=0.06, step=0.005, readout_format=".3f", description="PLL bandwidth", continuous_update=False, layout=widgets.Layout(width="520px"))
w_aid   = widgets.Checkbox(value=True, description="Known CP / word symbols in the PLL (aided)", layout=widgets.Layout(width="380px"))
w_pw    = widgets.Dropdown(options=[1, 3, 5], value=3, description="Pilot weight", layout=widgets.Layout(width="200px"))
w_tbw   = widgets.Dropdown(options=[200, 400, 800], value=400, description="Timing 2pi/N", layout=widgets.Layout(width="220px"))
w_ths   = widgets.IntSlider(value=154, min=100, max=230, step=2, description="Search thr.", continuous_update=False, layout=widgets.Layout(width="420px"))
w_thl   = widgets.IntSlider(value=115, min=60, max=200, step=2, description="Lock thr.", continuous_update=False, layout=widgets.Layout(width="420px"))
w_nsw   = widgets.IntSlider(value=4, min=0, max=10, description="Frames to narrow", continuous_update=False, layout=widgets.Layout(width="380px"))
w_rxg   = widgets.IntSlider(value=RX_GAIN, min=0, max=76, description="RX gain", continuous_update=False, layout=widgets.Layout(width="520px"))
w_loop  = widgets.Checkbox(value=False, description="Digital loopback")
w_tx    = widgets.Dropdown(options=[("off", 0), ("frames", 1)], value=0, description="FPGA transmits", layout=widgets.Layout(width="260px"))
w_att   = widgets.FloatSlider(value=25.0, min=20.0, max=89.75, step=0.25, description="TX atten (dB)", continuous_update=False, layout=widgets.Layout(width="520px"))
w_amp   = widgets.FloatSlider(value=0.25, min=0.05, max=0.6, step=0.05, description="TX amplitude", continuous_update=False, layout=widgets.Layout(width="520px"))
b_rx    = widgets.Button(description="Start receiver", button_style="success")
b_apply = widgets.Button(description="Apply", button_style="primary")
b_hold  = widgets.Button(description="Hold FLL now")
b_rxoff = widgets.Button(description="Stop receiver", button_style="warning")
b_start = widgets.Button(description="Start display", button_style="info")
b_stop  = widgets.Button(description="Stop display")
status  = widgets.Label(value="idle", layout=widgets.Layout(width="auto"))
errout  = widgets.Output(layout=widgets.Layout(border="1px solid #c0392b", max_height="200px", overflow="auto"))
image   = widgets.Image(format="png", width=860)
live    = Live(image, status)

import traceback
def guard(fn):
    def h(change=None):
        try: fn(change)
        except Exception as e:
            status.value = f"{type(e).__name__}: {e}"
            with errout: print(traceback.format_exc())                          # the whole error, with the line, below the controls
    return h

def apply_live(_=None):
    """the live controls into the registers (the receiver may be running)"""
    rx.set_pll(loop_bw=w_bw.value, aided=w_aid.value, pilot_weight=w_pw.value)
    rx.set_timing(timing_bw=2 * np.pi / w_tbw.value)
    rx.set_sync(thr_s=w_ths.value, thr_l=w_thl.value, nsw=w_nsw.value)
    if w_fmode.value != "off" and rx.r("FLL_CTRL") & 1: rx.set_fll(w_tgi.value)
    status.value = f"set: PLL bandwidth {w_bw.value:.3f}, {'aided' if w_aid.value else 'not aided'}, pilot weight {w_pw.value}, timing 2pi/{w_tbw.value}, sync thresholds {w_ths.value}/{w_thl.value}, narrow after {w_nsw.value} frames, FLL track gain {w_tgi.value}"

def do_start_receiver(_=None):
    live.paused = True; time.sleep(0.15)                      # the live thread must not touch the registers meanwhile
    try:
        live.last = None
        for h in (hist_fll, hist_pll, hist_off, hist_fr, hist_er): h[:] = [np.nan] * HIST
        kw = dict(loop_bw=w_bw.value, aided=w_aid.value, pilot_weight=w_pw.value, timing_bw=2 * np.pi / w_tbw.value, thr_s=w_ths.value, thr_l=w_thl.value, nsw=w_nsw.value)
        if w_fmode.value == "off":
            rx.stop(); time.sleep(0.05); rx.configure(**kw); rx.ip.write(REG["FLL_F0"], 0); rx.fll_enable(False); rx.start(); t0 = time.time(); ok = rx.wait_lock(1.5)
            status.value = f"FLL off: {'LOCKED' if ok else 'not locked (the natural offset of the B210 is too big without the FLL)'} after {time.time() - t0:.2f} s"
        else:
            r = rx.acquire(acq_gi=w_agi.value, trk_gi=w_tgi.value, hold=(w_fmode.value == "hold"), **kw)
            status.value = (f"cold start: {'LOCKED' if r['locked'] else 'not locked (is the transmitter on?)'} after {r['seconds'] * 1e3:.0f} ms, FLL {r['fll_hz']:+.0f} Hz"
                            + (" (held)" if w_fmode.value == "hold" and r["locked"] else ""))
    finally:
        live.paused = False

def do_tx(change=None):
    if w_tx.value == 1: ad.set_tx_atten_db(w_att.value); tx.start(amp=w_amp.value)
    else: tx.off(); p501_radio.quiet(ad, TX_ATTEN0)

b_rx.on_click(guard(do_start_receiver)); b_apply.on_click(guard(apply_live)); b_rxoff.on_click(guard(lambda b: rx.stop()))
b_hold.on_click(guard(lambda b: setattr(status, "value", f"FLL held at {rx.hold_fll():+.0f} Hz")))
b_start.on_click(guard(lambda b: live.start())); b_stop.on_click(guard(lambda b: live.stop()))
w_rxg.observe(guard(lambda c: ad.set_rx_manual_gain(c["new"])), names="value")
w_loop.observe(guard(lambda c: p501_radio.loopback(ad, c["new"])), names="value")
w_tx.observe(guard(do_tx), names="value")
w_att.observe(guard(lambda c: ad.set_tx_atten_db(c["new"]) if w_tx.value else None), names="value")
w_amp.observe(guard(lambda c: tx.set(amp=c["new"]) if w_tx.value else None), names="value")

display(widgets.VBox([widgets.HBox([b_rx, b_apply, b_hold, b_rxoff, b_start, b_stop, status]), widgets.HBox([w_fmode, w_agi, w_tgi]), w_bw, widgets.HBox([w_aid, w_pw, w_tbw]), widgets.HBox([w_ths, w_thl, w_nsw]), w_rxg,
                      widgets.HBox([w_loop, w_tx]), w_att, w_amp, errout, image]))
''')

md("""
### Check the controls (optional)

Moves the controls from Python, the way clicks would, in the digital loopback with the FPGA frames: the registers must follow the controls, the receiver must lock, and *FLL mode* hold must stop the FLL.
""")
code('''
w_loop.value = True; w_att.value = 20.0; w_amp.value = 0.25; w_tx.value = 1; time.sleep(0.3)
w_bw.value = 0.03; w_aid.value = False; w_pw.value = 5; w_tbw.value = 800; w_ths.value = 160; w_thl.value = 100; w_nsw.value = 3
b_apply.click(); time.sleep(0.2)
r = lambda k: rx.ip.read(REG[k])
check("apply writes the PLL and sync registers", r("PCFG") == (15 << 8) and r("THR") == ((100 << 8) | 160) and r("NSW") == 3, f"PCFG 0x{r('PCFG'):X}, THR 0x{r('THR'):X}, NSW {r('NSW')}")
from p501_qam16_rx import regs16
want = regs16(loop_bw=0.03, timing_bw=2 * np.pi / 800)
check("PLL and timing gains follow the controls", r("CA") == want["CA"] and r("CB") == want["CB"] and r("TA") == want["TA"] and r("TB") == want["TB"], f"CA {r('CA')} CB {r('CB')} TA {r('TA')} TB {r('TB')}")
w_bw.value = 0.02; w_aid.value = True; w_pw.value = 3; w_tbw.value = 400; w_ths.value = 154; w_thl.value = 115; w_nsw.value = 4; w_fmode.value = "hold"; w_tgi.value = 0.0001
b_rx.click(); time.sleep(0.5)
check("start receiver (FLL hold): locked", "LOCKED" in status.value and rx.stats()["locked"], status.value)
check("FLL held: its loop is stopped", r("FLL_CTRL") & 1 == 0, f"FLL_CTRL {r('FLL_CTRL')}")
f1 = _signed(r("FLL_FREQ")); time.sleep(0.3); f2 = _signed(r("FLL_FREQ"))
check("FLL held: constant frequency", f1 == f2, f"{f1 / 2**32 * FS:+.1f} Hz")
a = rx.stats(); time.sleep(1.0); b = rx.stats()
check("decoding with the held FLL", b["sym_err"] == a["sym_err"] and b["frames"] - a["frames"] > 900, f"{b['frames'] - a['frames']} frames, {b['sym_err'] - a['sym_err']} symbol errors")
w_fmode.value = "off"; b_rx.click(); time.sleep(0.3)
check("FLL off starts too (digital loopback has no offset)", rx.stats()["locked"], status.value)
w_fmode.value = "track"; b_rx.click(); time.sleep(0.3)
check("track: the FLL loop runs", r("FLL_CTRL") & 1 == 1 and rx.stats()["locked"], f"FLL_CTRL {r('FLL_CTRL')}, FLL_GI {r('FLL_GI')}; " + status.value)
w_rxg.value = 60; time.sleep(0.1); w_rxg.value = RX_GAIN
b_start.click(); time.sleep(1.0); b_stop.click(); display(IPImage(image.value))
w_tx.value = 0; w_loop.value = False; b_rxoff.click()
check("transmitter off again", not tx.enabled, f"enabled = {tx.enabled}")
''')

md("""
## Try it: the B210 frames, and the air

1. Start the B210 transmitter on the host: `python3 tutorial/qam16/qam16_frame_tx.py --tx-gain 80 --rms 0.35 --seconds 600` (the digital level `--rms 0.35`, the gain 80 to 86 dB; antennas a few centimetres apart).
2. Press **Start receiver** (*FLL mode* track), then **Start display**: *LOCKED*, 992 frames per second, the carrier offset about **+9.6 kHz** (the FLL takes -6 to -8 kHz, the PLL the rest), 16 clusters. With the B210 at 80 to 86 dB and RMS 0.35 the symbol errors were 0 in 2.6 million symbols in the strong session, SER 0.06 to 0.3 in the weak one (EVM -13 dB).
3. *FLL mode* **off**: the +9.6 kHz is more than the Zadoff-Chu word and the PLL can stand: no lock (or a lock with errors). **hold**: the same decoding as *track* with a flat frequency strip.
4. Change **FLL track gain** to 0.0003 and press Apply at a weak signal (lower the B210 gain, or *TX atten* 28 to 30 dB with the FPGA transmitter): the carrier is lost at an EVM of about -13 dB; at 0.0001 it holds to about -12 dB (`tutorial/qam16/PLAN_QAM16.md`, step 8).
5. **Without the B210**: tick *Digital loopback*, set *FPGA transmits* to *frames*, press *Start receiver*: it locks in tens of milliseconds, no symbol error, EVM -30 dB. Over the air from TX1 to RX1: untick the loopback, *TX atten* 20 to 26 dB.

The next cell sweeps the TX attenuation over the air with the FPGA transmitter (a few seconds per step). It radiates, so it only runs when `RUN_AIR = True`.
""")
code('''
RUN_AIR = False                      # True: the FPGA transmits over the air (TX1 -> RX1, antennas a few cm apart) at the attenuations below, weakest last
def air_experiment(attens=(20.0, 24.0, 28.0, 32.0), seconds=2.0):
    live.stop(); live.paused = True
    ad.set_rx_manual_gain(70); p501_radio.loopback(ad, False)
    print(f"{'TX atten':>9}{'locked':>8}{'frames':>8}{'sym errors':>12}{'of symbols':>12}{'SER':>10}{'EVM dB':>8}{'AGC':>7}{'FLL Hz':>8}{'PLL Hz':>8}")
    for att in attens:
        tx.off(); rx.stop(); ad.set_tx_atten_db(att); tx.start(amp=0.25); time.sleep(0.1)
        r = rx.acquire(); time.sleep(0.3); a = rx.stats(); time.sleep(seconds); b = rx.stats()
        ns, ne = b["sym_cnt"] - a["sym_cnt"], b["sym_err"] - a["sym_err"]
        print(f"{att:>7.0f}dB{str(r['locked']):>8}{b['frames'] - a['frames']:>8}{ne:>12,}{ns:>12,}{ne / max(ns, 1):>10.1e}{b['evm_db']:>8.1f}{b['agc_gain']:>7.1f}{b['fll_hz']:>8.0f}{b['pll_hz']:>8.0f}")
    tx.off(); rx.stop(); p501_radio.quiet(ad, TX_ATTEN0); live.paused = False

if RUN_AIR: air_experiment()
else: print("RUN_AIR is False: nothing is transmitted. Set it to True to sweep the TX attenuation over the air.")
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
