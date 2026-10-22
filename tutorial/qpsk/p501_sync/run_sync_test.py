#!/usr/bin/env python3
"""Host side of the frame-synchronisation test: the B210 transmits frames (qpsk_frame_tx.FrameTx, the same as qpsk_b210_frame_tx.grc), the P501 (overlay p501_qpsk_trx_sync,
p501_sync_link.py) finds the preambles in the FPGA.

    source tools/gnuradio_env.sh
    python3 run_sync_test.py --out /tmp/p501_sync_run --gains 80,76,72,68,64,60 --payload 960 --seconds 3 [--freq 915.03e6]

The B210 starts first at the first gain, the P501 starts to count when released; the gain is lowered level by level. --freq moves the B210 carrier (the P501 stays at 915.0 MHz).
Very low power: B210 TX gain 80 dB at most, antennas a few centimetres apart; check the rules where you are before radiating."""
import argparse, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from qpsk_frame_tx import FrameTx

SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser()
p.add_argument("--out", default="/tmp/p501_sync_run"); p.add_argument("--gains", default="80,76,72,68,64,60"); p.add_argument("--tx-amp", type=float, default=0.25)
p.add_argument("--rx-gain", type=int, default=70); p.add_argument("--payload", type=int, default=960); p.add_argument("--seconds", type=float, default=3.0)
p.add_argument("--freq", type=float, default=915.0e6); p.add_argument("--tx-delay", type=float, default=2.0)
a = p.parse_args()
gains = [float(g) for g in a.gains.split(",")]
assert max(gains) <= 80, "B210 TX gain is limited to 80 dB"
os.makedirs(a.out, exist_ok=True)
subprocess.run(SSH + ["rm -f /tmp/go_*"])
logf = os.path.join(a.out, "p501.log"); log = open(logf, "w")
board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_sync_link.py %d %d %d %g'" % (a.rx_gain, a.payload, len(gains), a.seconds)],
                         stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while "WAITING" not in open(logf).read():
    if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(logf).read()); sys.exit(1)
    time.sleep(0.5)
tx = FrameTx(tx_gain=gains[0], tx_amp=a.tx_amp, freq=a.freq, payload=a.payload); tx.start(); print("B210 transmitting frames (payload %d symbols) at %.4f MHz" % (a.payload, a.freq / 1e6), flush=True); time.sleep(a.tx_delay)
for k, g in enumerate(gains):
    tx.set_gain(g); time.sleep(0.5)
    subprocess.run(SSH + ["echo %g > /tmp/tx_gain; touch /tmp/go_%d" % (g, k)])
    t1 = time.time()
    while ("LEVEL_DONE %d" % k) not in open(logf).read():
        if time.time() - t1 > 240 or board.poll() is not None: print("level %d did not finish" % k); break
        time.sleep(0.5)
board.wait(timeout=60)
tx.stop(); tx.wait()
keep = lambda l: ("Costas unlocked" in l) or ("lock time from a cold" in l) or ("tx_gain" in l) or l.lstrip("U").startswith(("DONE", "READY", "Traceback", "  File", "RuntimeError", "TimeoutError", "ValueError"))
print("\n".join(l[l.index(next(m for m in ("N Costas", "L lock", "S tx_gain") if m in l)):] if any(m in l for m in ("N Costas", "L lock", "S tx_gain")) else l for l in open(logf, errors="replace").read().splitlines() if keep(l)))
