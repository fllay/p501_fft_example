#!/usr/bin/env python3
"""Host side of the P501 -> B210 16-QAM test: the P501's FPGA transmitter sends the frames, the B210 receives them with the compiled qam16_b210_frame_rx.grc (headless, Qt offscreen) and prints once a second
the lock, the frames decoded, the symbol error rate against the PRBS-15, the EVM and the carrier offset the PLL still had to take (the FLL of the flowgraph takes the rest of the +9.6 kHz).

    source tools/gnuradio_env.sh
    python3 run_qam16_grc_rx.py --p501-atten 20 --rx-gain 45 --seconds 10 [--fll-div 1600]
Very low power: the P501's TX attenuation is the knob (20 dB is the strongest); antennas a few centimetres apart; check the rules where you are before radiating."""
import argparse, importlib, os, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser()
p.add_argument("--p501-atten", type=float, default=20); p.add_argument("--p501-amp", type=float, default=0.25); p.add_argument("--rx-gain", type=float, default=45)
p.add_argument("--bw-div", type=float, default=400); p.add_argument("--fll-div", type=float, default=1600); p.add_argument("--seconds", type=float, default=10); p.add_argument("--no-board", action="store_true"); p.add_argument("--out", default="/tmp/qam16_grc_rx")
a = p.parse_args()
os.makedirs(a.out, exist_ok=True)
board = None
if not a.no_board:
    subprocess.run(SSH + ["rm -f /tmp/go"])
    logf = os.path.join(a.out, "p501.log"); log = open(logf, "w")
    board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_qam16_tx_only.py %s %s %s'" % (a.p501_atten, a.p501_amp, a.seconds + 10)], stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time()
    while "READY" not in open(logf).read():
        if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(logf).read()); sys.exit(1)
        time.sleep(0.5)
    print("P501 ready", flush=True)
tmp = tempfile.mkdtemp(prefix="qam16_fg_")
subprocess.run(["grcc", "-o", tmp, os.path.join(HERE, "qam16_b210_frame_rx.grc")], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, tmp)
from PyQt5 import Qt
app = Qt.QApplication(sys.argv)
tb = importlib.import_module("qam16_b210_frame_rx").qam16_b210_frame_rx()
tb.set_rx_gain(a.rx_gain); tb.set_bw_div(a.bw_div); tb.set_fll_div(a.fll_div)
rxb = next(getattr(tb, n) for n in dir(tb) if n.startswith("epy_block") and hasattr(getattr(tb, n), "core"))
tb.start()
if board is not None:
    subprocess.run(SSH + ["touch /tmp/go"])
    while "TX_ON" not in open(logf).read(): time.sleep(0.05)
    print("P501 transmitting 16-QAM frames", flush=True)
t0 = time.time(); f_prev = 0; e_prev = 0; n_prev = 0
try:
    while time.time() - t0 < a.seconds:
        time.sleep(1.0); app.processEvents()
        c = rxb.core
        print("t=%3.0f s locked %d frames %6d (+%4d/s of 992.8) SER %.2e total, %.2e last s (%d of %d)  EVM %.1f dB  carrier offset left %+6.0f Hz | locks %d hits %d misses %d lost %d" %
              (time.time() - t0, rxb.locked, c.frames, c.frames - f_prev, c.sym_err / max(c.sym_cnt, 1), (c.sym_err - e_prev) / max(c.sym_cnt - n_prev, 1), c.sym_err - e_prev, c.sym_cnt - n_prev,
               rxb.evm_db, rxb.cfo_hz, c.locks, c.hits, c.misses, c.lost), flush=True)
        f_prev, e_prev, n_prev = c.frames, c.sym_err, c.sym_cnt
finally:
    tb.stop(); tb.wait()
    if board is not None:
        t1 = time.time()
        while "DONE" not in open(logf).read() and time.time() - t1 < 40: time.sleep(0.2)
        print("\n".join(l for l in open(logf).read().splitlines() if "TX_ON" in l or "DONE" in l))
        board.terminate()
        subprocess.run(SSH + ["echo xilinx | sudo -S pkill -f '[p]501_qam16_tx_only.py'"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
