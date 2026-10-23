"""Board probe (run as root): the receiver on a steady B210 signal with different FLL settings: how much of the EVM is the residual carrier offset the FLL leaves to the PLL?
    python3 /tmp/p501_qam16_fllprobe.py <RX gain index> <seconds>"""
import sys, time
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qam16')
from pynq import Overlay
import p501_radio
from p501_qam16_rx import P501Qam16Rx, REG, FS
RX_GAIN = int(sys.argv[1]) if len(sys.argv) > 1 else 70
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qam16/p501_qam16_trx.bit')
rx = P501Qam16Rx(ol.qam16_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
rx.stop(); print("READY", flush=True)
import os
while not os.path.exists('/tmp/go_probe'): time.sleep(0.05)
os.remove('/tmp/go_probe')


def run(name, f0_hz=None, acq=0.002, trk=0.0001, hold=False, off=False, bw=0.02, fll_acq_s=0.02):
    rx.stop(); time.sleep(0.05); rx.configure(loop_bw=bw)
    rx.ip.write(REG["FLL_F0"], 0 if f0_hz is None else int(round(f0_hz / FS * 2 ** 32)) & 0xFFFFFFFF)
    c = rx.ip.read(REG["FLL_CTRL"]) & 1
    rx.fll_enable(not off); rx.set_fll(acq)
    if f0_hz is not None:                                   # the FLL starts at f0: reset loads F0 into the FLL frequency (fr <= r_f0 when the run starts)
        pass
    rx.start(); time.sleep(fll_acq_s); rx.set_fll(trk)
    ok = rx.wait_lock(1.5)
    if hold and ok: time.sleep(0.05); rx.hold_fll()
    time.sleep(0.3); a = rx.stats(); time.sleep(SECS); b = rx.stats()
    ns, ne = b["sym_cnt"] - a["sym_cnt"], b["sym_err"] - a["sym_err"]
    print("P %-44s locked=%s SER %.2e EVM %.1f dB AGC %.1f | FLL %+6.0f Hz PLL %+6.0f Hz offset %+6.0f Hz | misses %d lost %d" % (name, ok, ne / max(ns, 1), b["evm_db"], b["agc_gain"], b["fll_hz"], b["pll_hz"], b["pll_hz"] - b["fll_hz"], b["misses"], b["lost"]), flush=True)


try:
    run("default: acq 0.002 20 ms, track 0.0001")
    run("track 0.0003", trk=0.0003)
    run("track 0.001", trk=0.001)
    run("track 0.002 (never narrow)", trk=0.002)
    run("start at -9600 Hz, track 0.0001", f0_hz=-9600.0)
    run("start at -9600 Hz, hold", f0_hz=-9600.0, hold=True)
    run("FLL off, fixed at -9600 Hz", f0_hz=-9600.0, off=True)
    run("start at -9600 Hz, hold, PLL bw 0.04", f0_hz=-9600.0, hold=True, bw=0.04)
    run("default, PLL bw 0.04", bw=0.04)
finally:
    rx.stop(); p501_radio.quiet(ad, 89.75); print("DONE", flush=True)
