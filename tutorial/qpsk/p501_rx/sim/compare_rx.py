"""Compare the RTL log (rtl_rx_out.txt: bits2 zi zq omega rate g e_t e_c per symbol) with the integer model, for a timing integral gain TB (default: the 2 pi/400 value).
    python3 compare_rx.py [TB]"""
import sys
sys.path.insert(0, "..")
import numpy as np, qpsk_rx_fixed as F
regs = F.regs_from_bw()
if len(sys.argv) > 1: regs["TB"] = int(sys.argv[1])
xi, xq = np.load("xi.npy"), np.load("xq.npy")
m = F.receive_fixed(xi, xq, regs)
m["bits"] = m["bits"].reshape(-1, 2) @ np.array([2, 1])          # the model has one entry per bit, the RTL log the two bits of a symbol (MSB first)
d = np.loadtxt("rtl_rx_out.txt", dtype=np.int64)
n = min(len(d), len(m["bits"]))
print("RTL symbols %d, model symbols %d, compared %d" % (len(d), len(m["bits"]), n))
bad = 0
for j, k in enumerate(("bits", "zi", "zq", "omega", "rate", "g", "e_t", "e_c")):
    mism = int(np.sum(d[:n, j] != m[k][:n])); bad += mism; print("  %-6s mismatches %d" % (k, mism))
print("RATE range (model) %d .. %d, MATCH" % (m["rate"].min(), m["rate"].max()) if bad == 0 else "MISMATCH")
