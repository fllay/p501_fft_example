#!/usr/bin/env python3
"""Chapter 4d, host side: the B210 (GNU Radio) transmits the PRBS-15 DQPSK signal, the P501's FPGA receiver locks to it and counts the bit errors itself.

    source tools/gnuradio_env.sh
    python3 run_rx_test_4d.py --out /tmp/p501_rx_run --tx-gain 75 --seconds 8 --div 400 --init-freq 0

The B210 starts first, then the P501 starts its receiver (it only receives: its TX is fully attenuated). The log of the P501 (statistics once per second) is in <out>/p501.log.
Very low power: B210 TX gain 75 dB at most, antennas a few centimetres apart; check the rules where you are before radiating."""
import argparse, os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gnuradio"))
import numpy as np
from qpsk_b210_loop import Tx

SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser()
p.add_argument("--out", default="/tmp/p501_rx_run"); p.add_argument("--tx-gain", type=float, default=75); p.add_argument("--tx-amp", type=float, default=0.25)
p.add_argument("--rx-gain", type=int, default=70, help="P501 RX gain index"); p.add_argument("--seconds", type=float, default=8); p.add_argument("--freq", type=float, default=915.0e6)
p.add_argument("--div", type=float, default=400, help="loop bandwidths of the FPGA receiver: 2 pi / div"); p.add_argument("--init-freq", type=float, default=0.0, help="initial Costas frequency (Hz)")
p.add_argument("--track-div", type=float, default=0, help="switch both loops to 2 pi / track-div after --acq-ms (acquire wide, track narrow)"); p.add_argument("--acq-ms", type=float, default=30)
p.add_argument("--tx-delay", type=float, default=2.0, help="seconds the B210 transmits alone before the P501 starts")
a = p.parse_args()
os.makedirs(a.out, exist_ok=True)
a.samp_rate, a.sps, a.excess_bw, a.pattern = 3.84e6, 4, 0.35, "prbs15"
a.dev_args = "num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360"
subprocess.run(SSH + ["rm -f /tmp/go"])
logf = os.path.join(a.out, "p501.log"); log = open(logf, "w")
board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_qpsk_link.py rx 89.75 %g %d %g %g %g %g'" % (a.seconds, a.rx_gain, a.div, a.init_freq, a.track_div, a.acq_ms)], stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while "WAITING" not in open(logf).read():
    if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(logf).read()); sys.exit(1)
    time.sleep(0.5)
tx = Tx(a); tx.start(); print("B210 transmitting (gain %g dB)" % a.tx_gain, flush=True); time.sleep(a.tx_delay)
subprocess.run(SSH + ["touch /tmp/go"])
board.wait(timeout=a.seconds + 90)
tx.stop(); tx.wait()
print("\n".join(l for l in open(logf).read().splitlines() if l.startswith(("RX_ON", "PULLIN", "averaged", "soft", "DONE"))))
