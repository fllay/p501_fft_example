#!/usr/bin/env python3
"""Host side of the hardware-acquisition test: the B210 sends frames (FrameTx) at carriers 915.0 MHz + offsets, the P501 (p501_sync_acq.py) starts cold with the hardware acquisition (H) and with the
Python carrier search (P).     source tools/gnuradio_env.sh;  python3 run_acq_test.py --offsets 0,30e3,-60e3,80e3,-90e3,110e3 --trials 5 [--payload 960]
The offsets are the B210 carrier minus the P501's 915.0 MHz (the radios' own offset of about +9.5 kHz comes on top). B210 TX gain 80 dB, very low power."""
import argparse, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from qpsk_frame_tx import FrameTx
SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser()
p.add_argument("--out", default="/tmp/p501_acq_run"); p.add_argument("--offsets", default="0,30e3,-60e3,80e3,-90e3,110e3"); p.add_argument("--trials", type=int, default=5)
p.add_argument("--payload", type=int, default=960); p.add_argument("--rx-gain", type=int, default=70); p.add_argument("--tx-gain", type=float, default=80.0)
a = p.parse_args(); offs = [float(o) for o in a.offsets.split(",")]; assert a.tx_gain <= 80
os.makedirs(a.out, exist_ok=True); subprocess.run(SSH + ["rm -f /tmp/go_*"])
logf = os.path.join(a.out, "p501.log"); log = open(logf, "w")
board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_sync_acq.py %d %d %d %d'" % (a.rx_gain, a.payload, len(offs), a.trials)], stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while "WAITING" not in open(logf).read():
    if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(logf).read()); sys.exit(1)
    time.sleep(0.5)
tx = FrameTx(tx_gain=a.tx_gain, freq=915.0e6 + offs[0], payload=a.payload); tx.start(); time.sleep(2.0)
for k, o in enumerate(offs):
    tx.set_freq(915.0e6 + o); time.sleep(1.0)
    subprocess.run(SSH + ["echo 'B210 %+.0f kHz' > /tmp/tx_label; touch /tmp/go_%d" % (o / 1e3, k)])
    t1 = time.time()
    while ("LEVEL_DONE %d" % k) not in open(logf, errors="replace").read():
        if time.time() - t1 > 400 or board.poll() is not None: print("level %d did not finish" % k); break
        time.sleep(0.5)
board.wait(timeout=60); tx.stop(); tx.wait()
for l in open(logf, errors="replace").read().splitlines():
    for m in ("P B210", "H B210"):
        if m in l: print(l[l.index(m):]); break
