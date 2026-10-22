"""Compare the framed transmitter of tb_qpsk_tx_fr.v with the bit-exact model.   python3 compare_tx_fr.py PL     (the simulation ran with +cfg = 2^31 + PL, or 0 for the continuous PRBS: PL = 0)"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, os.path.join(HERE, "..", "..", "p501_tx"))
from qpsk_model import model
from qpsk_frame import frames_bits
PL = int(sys.argv[1]) if len(sys.argv) > 1 else 192
d = np.loadtxt(os.path.join(HERE, "rtl_tx_fr.txt"), dtype=np.int64); n = len(d)
if PL:
    nfr = (n // 4 + 20) // (64 + PL) + 2
    mi, mq = model(n, amp=0x4000, bits=frames_bits(PL, nfr))
else:
    mi, mq = model(n, amp=0x4000)
bad = int(np.sum((d[:, 0] != mi[:n]) | (d[:, 1] != mq[:n])))
print("framed transmitter (PL %d): %d samples, mismatches %d  %s" % (PL, n, bad, "MATCH" if bad == 0 else "MISMATCH"))
