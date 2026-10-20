#!/usr/bin/env python3
"""Host side of the FLL receiver test: the B210 (GNU Radio) transmits the PRBS-15 DQPSK signal, the P501 (overlay p501_qpsk_trx_fll, p501_fll_link.py) acquires with the FLL
and, for comparison, with the original procedure.

    source tools/gnuradio_env.sh
    python3 run_fll_test.py --out /tmp/p501_fll_run --tx-gain 80 --trials 5 --seconds 6

The B210 starts first, then the P501 starts to acquire (it only receives: its TX is fully attenuated). The log of the P501 is in <out>/p501.log.
Very low power: B210 TX gain 80 dB at most, antennas a few centimetres apart; check the rules where you are before radiating."""
import argparse, os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gnuradio"))
from qpsk_b210_loop import Tx

SSH = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "xilinx@192.168.2.1"]
p = argparse.ArgumentParser()
p.add_argument("--out", default="/tmp/p501_fll_run"); p.add_argument("--tx-gain", type=float, default=80); p.add_argument("--tx-amp", type=float, default=0.25)
p.add_argument("--rx-gain", type=int, default=70, help="P501 RX gain index"); p.add_argument("--seconds", type=float, default=6); p.add_argument("--trials", type=int, default=5)
p.add_argument("--pullin", action="store_true", help="measure the pull-in time with and without the FLL instead of the acquire procedures"); p.add_argument("--freq", type=float, default=915.0e6); p.add_argument("--tx-delay", type=float, default=2.0)
a = p.parse_args()
assert a.tx_gain <= 80, "B210 TX gain is limited to 80 dB"
os.makedirs(a.out, exist_ok=True)
a.samp_rate, a.sps, a.excess_bw, a.pattern = 3.84e6, 4, 0.35, "prbs15"
a.dev_args = "num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360"
subprocess.run(SSH + ["rm -f /tmp/go"])
logf = os.path.join(a.out, "p501.log"); log = open(logf, "w")
board = subprocess.Popen(SSH + ["echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh 2>/dev/null; python3 /tmp/p501_fll_link.py %d %d %g %s'" % (a.rx_gain, a.trials, a.seconds, "pullin" if a.pullin else "-")],
                         stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while "WAITING" not in open(logf).read():
    if time.time() - t0 > 240 or board.poll() is not None: print("the P501 did not get ready:\n" + open(logf).read()); sys.exit(1)
    time.sleep(0.5)
tx = Tx(a); tx.start(); print("B210 transmitting (gain %g dB)" % a.tx_gain, flush=True); time.sleep(a.tx_delay)
subprocess.run(SSH + ["touch /tmp/go"])
board.wait(timeout=a.seconds + 40 * a.trials + 120)
tx.stop(); tx.wait()
print("\n".join(l for l in open(logf).read().splitlines() if l[:2] in ("A ", "B ", "C ", "P ") or l.startswith(("LONG", "t=", "soft", "DONE", "READY", "Traceback", "  File", "RuntimeError", "TimeoutError"))))
