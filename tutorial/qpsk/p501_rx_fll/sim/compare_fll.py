"""Compare the RTL logs of tb_qpsk_rx_fll.v with the integer models.   python3 compare_fll.py [GI [GP [F0]]]     (the same values as the plusargs of the simulation)
 1. rtl_fll_y.txt: every derotated sample against qpsk_fll_fixed.fll_stage        2. rtl_fll_e.txt: the error of every block (from block 13 on)
 3. rtl_rx_out.txt: the engine's per-symbol log (bits, zi, zq, omega, rate, g, e_t, e_c) against qpsk_rx_fixed.receive_fixed on the derotated samples"""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, os.path.join(HERE, "..", "..", "p501_rx"))
import qpsk_fll_fixed as M, qpsk_rx_fixed as F
GI = int(sys.argv[1]) if len(sys.argv) > 1 else 1367131
GP = int(sys.argv[2]) if len(sys.argv) > 2 else 0
F0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0
xi, xq = np.load(os.path.join(HERE, "..", "..", "p501_rx", "sim", "xi.npy")), np.load(os.path.join(HERE, "..", "..", "p501_rx", "sim", "xq.npy"))
m = M.fll_stage(xi, xq, GI=GI, GP=GP, F0=F0)
y = np.loadtxt(os.path.join(HERE, "rtl_fll_y.txt"), dtype=np.int64); n = min(len(y), len(m["yi"]))
bad_y = int(np.sum((y[:n, 0] != m["yi"][:n]) | (y[:n, 1] != m["yq"][:n])))
print("FLL: RTL derotated samples %d, model %d, compared %d: mismatches %d" % (len(y), len(m["yi"]), n, bad_y))
e = np.loadtxt(os.path.join(HERE, "rtl_fll_e.txt"), dtype=np.int64); me = m["e"][M.FIRST_BLOCK:]; ne = min(len(e), len(me))
bad_e = int(np.sum(e[:ne] != me[:ne]))
print("FLL: block errors: RTL %d, model %d, compared %d: mismatches %d   (e range %d .. %d)" % (len(e), len(me), ne, bad_e, e[:ne].min(), e[:ne].max()))
r = F.receive_fixed(m["yi"], m["yq"]); r["bits"] = r["bits"].reshape(-1, 2) @ np.array([2, 1])
d = np.loadtxt(os.path.join(HERE, "rtl_rx_out.txt"), dtype=np.int64); k = min(len(d), len(r["bits"]))
bad = bad_y + bad_e
for j, name in enumerate(("bits", "zi", "zq", "omega", "rate", "g", "e_t", "e_c")):
    mm = int(np.sum(d[:k, j] != r[name][:k])); bad += mm; print("  engine %-6s mismatches %d" % (name, mm))
print("engine: RTL symbols %d, model %d, compared %d.   FLL frequency at the end (model) %+.1f Hz,  Costas omega %+.1f Hz" % (len(d), len(r["bits"]), k, M.fr_hz(m["fr"][-1]), r["omega"][k - 1] / 2 ** 32 * 960e3))
print("RESULT:", "MATCH (0 mismatches)" if bad == 0 else "MISMATCH (%d)" % bad)
