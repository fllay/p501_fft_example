#!/usr/bin/env python3
"""Sweep of the B210 TX gain, its digital amplitude and the P501's RX gain: the B210 transmits the 16-QAM frames (qam16_frame_tx.py), the P501 (p501_qam16_levels.py on the board) receives; for every combination
the symbol error rate, the EVM and the AGC gain (the received level), and the number of UHD underflows ('U') the transmitter reported during the level.

    source tools/gnuradio_env.sh
    python3 run_qam16_sweep.py --combos 86:0.175:70,83:0.25:70,80:0.35:70,77:0.5:70 --seconds 3          # tx gain : digital RMS : P501 RX gain index
The B210 starts at the first combination; the P501 starts from cold for every one. Very low power (antennas a few cm apart); check the rules where you are before radiating."""
import argparse, os, re, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from qam16_frame_tx import Qam16FrameTx

SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser()
p.add_argument("--combos", required=True); p.add_argument("--seconds", type=float, default=3.0); p.add_argument("--out", default="/tmp/qam16_sweep"); p.add_argument("--freq", type=float, default=915.0e6)
a = p.parse_args()
combos = [tuple(float(v) for v in c.split(":")) for c in a.combos.split(",")]
assert all(g <= 89.75 and r <= 0.5 for g, r, _ in combos)
os.makedirs(a.out, exist_ok=True)
subprocess.run(SSH + ["rm -f /tmp/go_* /tmp/rx_gain"])
logf = os.path.join(a.out, "p501.log"); log = open(logf, "w")
board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_qam16_levels.py %d %d %g'" % (int(combos[0][2]), len(combos), a.seconds)], stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while "WAITING" not in open(logf).read():
    if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(logf).read()); sys.exit(1)
    time.sleep(0.5)
# the UHD underflow characters go to this process's stdout / stderr: count them per level through a pipe on fd 1 and 2 is awkward, so the transmitter runs in a child process that prints one line per level
import io, contextlib
tx = Qam16FrameTx(tx_gain=combos[0][0], rms=combos[0][1], freq=a.freq); tx.start(); time.sleep(2.0)
for k, (g, rms, rxg) in enumerate(combos):
    tx.set_gain(g); tx.set_rms(rms); time.sleep(0.5)
    subprocess.run(SSH + ["echo '%g_%g' > /tmp/tx_gain; echo %d > /tmp/rx_gain; touch /tmp/go_%d" % (g, rms, int(rxg), k)])
    t1 = time.time()
    while ("LEVEL_DONE %d" % k) not in open(logf).read():
        if time.time() - t1 > 120 or board.poll() is not None: print("level %d did not finish" % k); break
        time.sleep(0.5)
tx.set_gain(0); tx.stop(); tx.wait()
subprocess.run(SSH + ["echo xilinx | sudo -S pkill -f '[p]501_qam16_levels.py'"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for l in open(logf, errors="replace").read().splitlines():
    l = l.replace("[sudo] password for xilinx: ", "")
    if l.startswith("R "):
        g = lambda pat: (re.search(pat, l).group(1) if re.search(pat, l) else "?")
        print("tx %-12s locked=%s SER %-9s EVM %-6s dB  AGC gain %-5s  offset %s Hz  misses %s lost %s" % (g(r"R tx(\S+)"), g(r"locked=(\w+)"), g(r"SER (\S+)"), g(r"EVM (\S+) dB"), g(r"AGC gain ([\d.]+)"), g(r"offset ([+-]\d+) Hz"), g(r"miss (\d+)"), g(r"lost (\d+)")))
    elif l.startswith("A "): print("   " + l[:140])
