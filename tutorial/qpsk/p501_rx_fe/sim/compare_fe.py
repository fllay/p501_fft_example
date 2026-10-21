"""Compare the estimator of tb_qpsk_rx_fe.v with the integer models.   python3 compare_fe.py [GI [GP [F0 [FLLC]]]]   (the plusargs of the simulation; FLLC 0 = FLL held at F0)
 1. the FLL stage and the engine as in compare_fll.py (derotated samples, block errors, 8 engine columns)
 2. rtl_fe.txt: the two windows (cnt, ACC_RE, ACC_IM, ACC_ABS, first) against qpsk_fe_fixed.window() on the model's mi2, mq2"""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
FLL = os.path.join(HERE, "..", "..", "p501_rx_fll")
sys.path.insert(0, FLL); sys.path.insert(0, os.path.join(HERE, "..", "..", "p501_rx"))
import qpsk_fll_fixed as M, qpsk_rx_fixed as F, qpsk_fe_fixed as E
GI = int(sys.argv[1]) if len(sys.argv) > 1 else 1367131
GP = int(sys.argv[2]) if len(sys.argv) > 2 else 0
F0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0
EN = (int(sys.argv[4]) if len(sys.argv) > 4 else 1) != 0
RX = os.path.join(HERE, "..", "..", "p501_rx", "sim")
xi, xq = np.load(os.path.join(RX, "xi.npy")), np.load(os.path.join(RX, "xq.npy"))
m = M.fll_stage(xi, xq, GI=GI, GP=GP, F0=F0, enable=EN)
y = np.loadtxt(os.path.join(HERE, "rtl_fll_y.txt"), dtype=np.int64); n = min(len(y), len(m["yi"]))
bad = int(np.sum((y[:n, 0] != m["yi"][:n]) | (y[:n, 1] != m["yq"][:n])))
print("FLL: derotated samples RTL %d, model %d: mismatches %d" % (len(y), len(m["yi"]), bad))
r = F.receive_fixed(m["yi"], m["yq"]); r["bits"] = r["bits"].reshape(-1, 2) @ np.array([2, 1])
d = np.loadtxt(os.path.join(HERE, "rtl_rx_out.txt"), dtype=np.int64); k = min(len(d), len(r["bits"]))
for j, name in enumerate(("bits", "zi", "zq", "omega", "rate", "g", "e_t", "e_c")):
    mm = int(np.sum(d[:k, j] != r[name][:k])); bad += mm; print("  engine %-6s mismatches %d" % (name, mm))
c, s, mag, valid = E.fe_symbols(r["mi2"], r["mq2"])
w = np.atleast_2d(np.loadtxt(os.path.join(HERE, "rtl_fe.txt"), dtype=np.int64))
for row in w:
    cnt, re, im, ab, first = [int(v) for v in row]
    a = E.window(c, s, mag, valid, first, cnt)
    ok = (a[0] == re) and (a[1] == im) and (a[2] == ab) and (a[3] == cnt) and (a[4] == first)
    fh, q, _ = E.estimate(re, im, cnt); bad += 0 if ok else 1
    print("  window first %5d N %5d: RTL re %d im %d abs %d | model re %d im %d abs %d  -> %s   f = %+.1f Hz, quality %.2f (Costas omega at the end %+.1f Hz, FLL %+.1f Hz)" % (
          first, cnt, re, im, ab, a[0], a[1], a[2], "match" if ok else "MISMATCH", fh, q, r["omega"][k - 1] / 2 ** 32 * 960e3, M.fr_hz(m["fr"][-1])))
print("RESULT:", "MATCH (0 mismatches)" if bad == 0 else "MISMATCH (%d)" % bad)
