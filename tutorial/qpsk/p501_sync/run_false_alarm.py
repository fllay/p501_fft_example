#!/usr/bin/env python3
"""Host side of the false-alarm test: the P501's synchroniser counts peaks and locks while the B210 sends nothing (noise) or PRBS-15 data without a preamble.
    source tools/gnuradio_env.sh;  python3 run_false_alarm.py --what noise|prbs --seconds 20"""
import argparse, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gnuradio"))
SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser(); p.add_argument("--what", choices=["noise", "prbs"], default="noise"); p.add_argument("--seconds", type=float, default=20); p.add_argument("--rx-gain", type=int, default=70); p.add_argument("--out", default="/tmp/p501_false_run")
a = p.parse_args(); os.makedirs(a.out, exist_ok=True)
subprocess.run(SSH + ["rm -f /tmp/go_f"]); logf = os.path.join(a.out, "p501.log"); log = open(logf, "w")
board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_sync_false.py %d %g %s'" % (a.rx_gain, a.seconds, a.what)], stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while "WAITING" not in open(logf).read():
    if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(logf).read()); sys.exit(1)
    time.sleep(0.5)
tx = None
if a.what == "prbs":
    import argparse as ap
    from qpsk_b210_loop import Tx
    ns = ap.Namespace(tx_gain=80.0, tx_amp=0.25, freq=915.0e6, samp_rate=3.84e6, sps=4, excess_bw=0.35, pattern="prbs15", out=a.out,
                      dev_args="num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360")
    tx = Tx(ns); tx.start(); time.sleep(2.0)
subprocess.run(SSH + ["touch /tmp/go_f"]); board.wait(timeout=a.seconds + 120)
if tx: tx.stop(); tx.wait()
print("\n".join(l[l.index("F "):] for l in open(logf, errors="replace").read().splitlines() if "F noise" in l or "F prbs" in l))
