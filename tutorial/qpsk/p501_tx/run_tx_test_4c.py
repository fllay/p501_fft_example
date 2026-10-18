#!/usr/bin/env python3
"""Chapter 4c, host side: the P501 transmits the PRBS-15 QPSK signal generated in its FPGA, the B210 (RX2) receives and decodes it live with the
GNU Radio chain of chapter 4a; the bit errors are counted against the PRBS-15.

    source tools/gnuradio_env.sh
    python3 run_tx_test_4c.py --out /tmp/p501_tx_run --p501-atten 40 --seconds 6

Very low power: the P501's TX attenuation is the knob (default 40 dB); check the rules where you are before radiating."""
import argparse, os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gnuradio"))
import numpy as np
from qpsk_b210_loop import Rx

SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser()
p.add_argument("--out", default="/tmp/p501_tx_run"); p.add_argument("--p501-atten", type=float, default=40); p.add_argument("--p501-amp", type=float, default=0.5)
p.add_argument("--rx-gain", type=float, default=45); p.add_argument("--seconds", type=float, default=6); p.add_argument("--freq", type=float, default=915.0e6)
p.add_argument("--bw", type=float, default=2 * np.pi / 400, help="loop bandwidths of the receiver (FLL, timing, Costas)")
a = p.parse_args()
os.makedirs(a.out, exist_ok=True)
a.samp_rate, a.sps, a.excess_bw, a.rx_offset_hz = 3.84e6, 4, 0.35, 0.0
a.freq_bw = a.timing_bw = a.phase_bw = a.bw; a.max_rate_dev = 0.05; a.save_raw = True; a.tap_every_s = 1.0
a.dev_args = "num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360"
subprocess.run(SSH + ["rm -f /tmp/go"])
logf = os.path.join(a.out, "p501.log"); log = open(logf, "w")
board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_qpsk_tx.py %s %s %s'" % (a.p501_atten, a.p501_amp, a.seconds + 6)], stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while "READY" not in open(logf).read():
    if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(logf).read()); sys.exit(1)
    time.sleep(0.5)
print("P501 ready; starting its transmitter", flush=True)
subprocess.run(SSH + ["touch /tmp/go"])
while "TX_ON" not in open(logf).read(): time.sleep(0.05)
time.sleep(2.0)                                   # the receiver's loops must not run on the start-up of the link
rx = Rx(a); rx.start(); time.sleep(a.seconds); rx.stop(); rx.wait()
board.wait(timeout=60)
print("\n".join(l for l in open(logf).read().splitlines() if "TX_ON" in l or "DONE" in l))
print("decoded in", a.out, " -> python3 ../gnuradio/qpsk_analyze.py", a.out, "prbs15")
