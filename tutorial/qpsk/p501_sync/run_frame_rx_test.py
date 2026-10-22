#!/usr/bin/env python3
"""Host side of the frame-receiver test: the P501's FPGA transmitter sends frames (m-sequence preamble + PRBS-15 payload), the B210 receives them with qpsk_b210_frame_rx.grc (run without a screen,
the same blocks) and prints, once a second, the payload bit error rate, the frames found, the frame lock and the carrier offset measured on the preamble.
--assist 0|1 switches the frame-sync assistance of the carrier loops (the preamble gives the Costas loop its frequency), --fll 0|1 the FLL band-edge: the four combinations are compared in the README.

    source tools/gnuradio_env.sh
    python3 run_frame_rx_test.py --p501-atten 40 --seconds 10 [--rx-gain 45] [--payload 960]       # the P501 board is started over ssh
    python3 run_frame_rx_test.py --no-board --seconds 10                                           # only the B210 receiver (the transmitter is started otherwise, e.g. from the notebook)

Very low power: the P501's TX attenuation is the knob (default 40 dB); check the rules where you are before radiating."""
import argparse, importlib, os, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser()
p.add_argument("--p501-atten", type=float, default=40); p.add_argument("--p501-amp", type=float, default=0.5); p.add_argument("--rx-gain", type=float, default=45)
p.add_argument("--bw-div", type=float, default=400); p.add_argument("--payload", type=int, default=960); p.add_argument("--seconds", type=float, default=10)
p.add_argument("--assist", type=int, default=1, help="1: the m-sequence preamble gives the carrier frequency to the Costas loop (frame-sync assistance), 0: off")
p.add_argument("--fll", type=int, default=1, help="1: FLL band-edge on, 0: off (zero loop gain)")
p.add_argument("--smooth", type=float, default=None, help="weight of a new preamble estimate in the assistance (default: the block's 0.5)")
p.add_argument("--dmax", type=int, default=None, help="largest Hamming distance of the preamble bits that still counts as a frame (default: the block's 16)")
p.add_argument("--no-board", action="store_true"); p.add_argument("--out", default="/tmp/p501_frame_rx_run")
a = p.parse_args()
os.makedirs(a.out, exist_ok=True)

board = None
if not a.no_board:
    subprocess.run(SSH + ["rm -f /tmp/go"])
    logf = os.path.join(a.out, "p501.log"); log = open(logf, "w")
    board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_frame_tx.py %s %s %s %d'" % (a.p501_atten, a.p501_amp, a.seconds + 8, a.payload)],
                             stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time()
    while "READY" not in open(logf).read():
        if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(logf).read()); sys.exit(1)
        time.sleep(0.5)
    print("P501 ready", flush=True)

tmp = tempfile.mkdtemp(prefix="qpsk_fg_")
subprocess.run(["grcc", "-o", tmp, os.path.join(HERE, "qpsk_b210_frame_rx.grc")], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, tmp)
from PyQt5 import Qt
fg = importlib.import_module("qpsk_b210_frame_rx")
app = Qt.QApplication(sys.argv)
tb = fg.qpsk_b210_frame_rx()
tb.set_rx_gain(a.rx_gain); tb.set_bw_div(a.bw_div); tb.set_payload_syms(a.payload); tb.set_assist_on(a.assist); tb.set_fll_on(a.fll)
chk = next(getattr(tb, n) for n in dir(tb) if n.startswith("epy_block") and hasattr(getattr(tb, n), "frames"))
ast = next(getattr(tb, n) for n in dir(tb) if n.startswith("epy_block") and hasattr(getattr(tb, n), "hits"))
if a.smooth is not None: ast.smooth = a.smooth
if a.dmax is not None: chk.dmax = a.dmax
tb.start()
if board is not None:
    subprocess.run(SSH + ["touch /tmp/go"])
    while "TX_ON" not in open(logf).read(): time.sleep(0.05)
    print("P501 transmitting frames", flush=True)
t0 = time.time(); f_prev = 0
try:
    while time.time() - t0 < a.seconds:
        time.sleep(1.0); app.processEvents()
        f = chk.frames
        print("t=%3.0f s  frames found %6d (+%4d/s of %.1f)  BER %.2e  lock %d   preamble offset %+7.0f Hz (%d preambles)" % (time.time() - t0, f, f - f_prev, 3.84e6 / 4 / (64 + a.payload), chk.ber, chk.locked_flag,
              ast.w_est / 6.283185307 * 960e3, ast.hits), flush=True); f_prev = f
finally:
    tb.stop(); tb.wait()
    if board is not None:
        t1 = time.time()
        while "DONE" not in open(logf).read() and time.time() - t1 < 40: time.sleep(0.2)     # the board script ends quiet ("DONE"); its Python process may linger on exit
        print("\n".join(l for l in open(logf).read().splitlines() if "TX_ON" in l or "DONE" in l))
        board.terminate()
        subprocess.run(SSH + ["echo xilinx | sudo -S pkill -f '[p]501_frame_tx.py'"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
