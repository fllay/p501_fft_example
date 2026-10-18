#!/usr/bin/env python3
"""Runs one of the B210 flowgraphs (qpsk_b210_tx.grc, qpsk_b210_rx.grc) without a screen (Qt 'offscreen'): the same blocks, settings from the command line.

    source tools/gnuradio_env.sh
    python3 run_flowgraph_headless.py tx --on --tx-gain 80 --seconds 60       # direction A: the B210 transmits PRBS-15 for the P501's FPGA receiver
    python3 run_flowgraph_headless.py rx --rx-gain 45 --seconds 60            # direction B: the B210 receives the P501's transmitter, PRBS-15 bit error rate once a second

Compiles the .grc with grcc into a temporary folder first. The transmitter is switched off again at the end, also after Ctrl-C.
Very low power; check the rules where you are before transmitting."""
import argparse, os, subprocess, sys, tempfile, time

p = argparse.ArgumentParser()
p.add_argument("mode", choices=["tx", "rx"])
p.add_argument("--on", action="store_true", help="tx: switch the transmitter ON (default OFF)")
p.add_argument("--tx-gain", type=float, default=80); p.add_argument("--tx-amp", type=float, default=0.25)
p.add_argument("--rx-gain", type=float, default=45); p.add_argument("--bw-div", type=float, default=400)
p.add_argument("--seconds", type=float, default=30)
a = p.parse_args()

here = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp(prefix="qpsk_fg_")
name = "qpsk_b210_" + a.mode
subprocess.run(["grcc", "-o", tmp, os.path.join(here, name + ".grc")], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, tmp)
from PyQt5 import Qt
import importlib
fg = importlib.import_module(name)

app = Qt.QApplication(sys.argv)
tb = getattr(fg, name)()
if a.mode == "tx":
    tb.set_tx_gain(a.tx_gain); tb.set_tx_amp(a.tx_amp)
    if a.on: tb.set_tx_on(1)
else:
    tb.set_rx_gain(a.rx_gain); tb.set_bw_div(a.bw_div)
checker = next((getattr(tb, n) for n in dir(tb) if n.startswith("epy_block") and hasattr(getattr(tb, n), "ber")), None)
tb.start(); t0 = time.time()
try:
    while time.time() - t0 < a.seconds:
        time.sleep(1.0); app.processEvents()
        if a.mode == "tx":
            print("t=%3.0f s  transmit %-3s  TX gain %.0f dB" % (time.time() - t0, "ON" if tb.tx_on else "OFF", tb.tx_gain), flush=True)
        else:
            ber = checker.ber
            print("t=%3.0f s  BER (last second or so) %.2e%s" % (time.time() - t0, ber, "   (0.17 = not locked, 0.5 = no valid stream)" if ber > 0.1 else ""), flush=True)
finally:
    if a.mode == "tx": tb.set_tx_on(0)
    tb.stop(); tb.wait()
    print("done" + (": transmitter off" if a.mode == "tx" else ""))
