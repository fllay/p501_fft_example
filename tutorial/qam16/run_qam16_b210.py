#!/usr/bin/env python3
"""Host side of the B210 -> P501 16-QAM test: the B210 transmits the 16-QAM frames (qam16_frame_tx.py), the P501 (overlay p501_qam16_trx, p501_qam16_levels.py on the board) receives them.

    source tools/gnuradio_env.sh
    python3 run_qam16_b210.py --out /tmp/qam16_b210 --gains 80,82,84,86 --rx-gain 70 --seconds 3 [--rx-gains 70,70,68,66] [--freq 915.0e6]

The B210 starts first at the first gain; the P501 starts from cold for every level (cold FLL + synchroniser + PLL), the gain is changed between the levels. The P501 does not transmit.
Very low power, antennas a few centimetres apart; check the rules where you are before radiating."""
import argparse, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from qam16_frame_tx import Qam16FrameTx

SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser()
p.add_argument("--out", default="/tmp/qam16_b210"); p.add_argument("--gains", default="80,82,84,86"); p.add_argument("--rx-gain", type=int, default=70); p.add_argument("--rx-gains", default="")
p.add_argument("--seconds", type=float, default=3.0); p.add_argument("--rms", type=float, default=0.18); p.add_argument("--freq", type=float, default=915.0e6); p.add_argument("--tx-delay", type=float, default=2.0)
a = p.parse_args()
gains = [float(g) for g in a.gains.split(",")]
rxg = [int(g) for g in a.rx_gains.split(",")] if a.rx_gains else []
os.makedirs(a.out, exist_ok=True)
subprocess.run(SSH + ["rm -f /tmp/go_* /tmp/rx_gain"])
logf = os.path.join(a.out, "p501.log"); log = open(logf, "w")
board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_qam16_levels.py %d %d %g'" % (a.rx_gain, len(gains), a.seconds)],
                         stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while "WAITING" not in open(logf).read():
    if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(logf).read()); sys.exit(1)
    time.sleep(0.5)
tx = Qam16FrameTx(tx_gain=gains[0], rms=a.rms, freq=a.freq); tx.start(); print("B210 transmitting 16-QAM frames at %.4f MHz, TX gain %g dB first" % (a.freq / 1e6, gains[0]), flush=True); time.sleep(a.tx_delay)
try:
    for k, g in enumerate(gains):
        tx.set_gain(g); time.sleep(0.5)
        cmd = "echo %g > /tmp/tx_gain; " % g + ("echo %d > /tmp/rx_gain; " % rxg[k] if rxg else "") + "touch /tmp/go_%d" % k
        subprocess.run(SSH + [cmd])
        t1 = time.time()
        while ("LEVEL_DONE %d" % k) not in open(logf).read():
            if time.time() - t1 > 120 or board.poll() is not None: print("level %d did not finish" % k); break
            time.sleep(0.5)
    t1 = time.time()
    while "DONE (" not in open(logf).read() and time.time() - t1 < 30: time.sleep(0.3)
finally:
    tx.set_gain(0); tx.stop(); tx.wait()
    subprocess.run(SSH + ["echo xilinx | sudo -S pkill -f '[p]501_qam16_levels.py'"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
keep = lambda l: l.lstrip("U").startswith(("A ", "R ", "DONE", "READY", "Traceback", "  File", "RuntimeError", "TimeoutError", "ValueError", "Error"))
print("\n".join(l.replace("[sudo] password for xilinx: ", "") for l in open(logf, errors="replace").read().splitlines() if keep(l.replace("[sudo] password for xilinx: ", ""))))
