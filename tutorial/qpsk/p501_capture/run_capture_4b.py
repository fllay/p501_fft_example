#!/usr/bin/env python3
"""Chapter 4b, host side: B210 transmits the DQPSK signal of chapter 4a (TX/RX port, 915.0 MHz), the P501 records 1 s of I/Q with its ADC DMA,
the recording is copied here and converted to complex64 (scaled to +-1) for the offline decoder.

    source tools/gnuradio_env.sh
    python3 run_capture_4b.py --out /tmp/p501_cap --tx-gain 60 --rx-gain 70

Very low power (TX gain 60 dB by default, antennas a few centimetres apart); check the rules where you are before radiating."""
import argparse, os, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gnuradio"))
from qpsk_b210_loop import Tx

SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser()
p.add_argument("--out", default="/tmp/p501_cap"); p.add_argument("--tx-gain", type=float, default=60); p.add_argument("--tx-amp", type=float, default=0.25)
p.add_argument("--rx-gain", type=int, default=70); p.add_argument("--signal", default="qpsk", choices=["qpsk", "twotone"], help="qpsk: the DQPSK signal of chapter 4a; twotone: two tones at +-1.5 MHz (sample-clock offset measurement)"); p.add_argument("--seconds", type=float, default=1.0); p.add_argument("--freq", type=float, default=915.0e6)
a = p.parse_args()
os.makedirs(a.out, exist_ok=True)
# the transmitter flowgraph of chapter 4a, started first (its start-up transient must be over when the P501 records)
a.samp_rate, a.sps, a.excess_bw = 3.84e6, 4, 0.35
a.dev_args = "num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360"
tx = Tx(a)
subprocess.run(SSH + ["rm -f /tmp/go /tmp/p501_cap.i16"])
log = open(os.path.join(a.out, "p501.log"), "w")
board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_capture.py %s %d'" % (a.seconds, a.rx_gain)], stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while "READY" not in open(os.path.join(a.out, "p501.log")).read():
    if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(os.path.join(a.out, "p501.log")).read()); sys.exit(1)
    time.sleep(0.5)
print("P501 ready; starting the B210 transmitter", flush=True)
tx.start(); time.sleep(3.0)
subprocess.run(SSH + ["touch /tmp/go"])
while "DONE" not in open(os.path.join(a.out, "p501.log")).read():
    if time.time() - t0 > 400: break
    time.sleep(0.1)
tx.stop(); tx.wait()
print([l for l in open(os.path.join(a.out, "p501.log")).read().splitlines() if "CAPTURED" in l][-1:])
subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1:/tmp/p501_cap.i16", os.path.join(a.out, "p501_cap.i16")], check=True)
raw = np.fromfile(os.path.join(a.out, "p501_cap.i16"), dtype=np.int16).astype(np.float32) / 2048.0
(raw[0::2] + 1j * raw[1::2]).astype(np.complex64).tofile(os.path.join(a.out, "p501_cap.c64"))
print("saved", os.path.join(a.out, "p501_cap.c64"), len(raw) // 2, "complex samples")
