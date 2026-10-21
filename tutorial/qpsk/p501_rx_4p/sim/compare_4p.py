"""Compare the RTL logs of tb_qpsk_rx_4p.v with the integer models.   python3 compare_4p.py [N [QMIN [AUTO]]]   (the plusargs of the simulation: n, qmin, auto)
 1. rtl_fe_win.txt: every window (cnt, ACC_RE, ACC_IM, ACC_ABS, first) against qpsk_fe_auto_fixed.auto_sequence on the symbols of qpsk_rx_fixed.receive_fixed;
 2. rtl_fe_load.txt: the symbol and the value of every load of the Costas frequency;
 3. rtl_rx_out.txt: the 8 engine columns against qpsk_rx_fixed.receive_fixed(..., omega_loads=...)."""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
P4 = os.path.join(HERE, ".."); RX = os.path.join(HERE, "..", "..", "p501_rx")
sys.path.insert(0, P4); sys.path.insert(0, RX)
import qpsk_rx_fixed as F, qpsk_fe_auto_fixed as A
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1024
QMIN = int(sys.argv[2]) if len(sys.argv) > 2 else 16000
AUTO = int(sys.argv[3]) if len(sys.argv) > 3 else 3
xi, xq = np.load(os.path.join(RX, "sim", "xi.npy")), np.load(os.path.join(RX, "sim", "xq.npy"))
r0 = F.receive_fixed(xi, xq); bad = 0
win = np.atleast_2d(np.loadtxt(os.path.join(HERE, "rtl_fe_win.txt"), dtype=np.int64))
ld = np.loadtxt(os.path.join(HERE, "rtl_fe_load.txt"), dtype=np.int64).reshape(-1, 2)
seq = A.auto_sequence(r0["mi2"], r0["mq2"], int(win[0, 4]), N, QMIN, continuous=bool(AUTO & 2), n_windows=len(win))
nb = 0
for k, row in enumerate(win):
    if k >= len(seq): print("  RTL window %d has no model counterpart" % k); nb += 1; continue
    q = seq[k]; ok = [int(v) for v in row] == [q["cnt"], q["acc_re"], q["acc_im"], q["acc_abs"], q["start"]]
    nb += 0 if ok else 1
    if k < 3 or not ok: print("  window %2d first %5d: RTL re %d im %d | model re %d im %d  w %+.1f Hz  passed %s  -> %s" % (k, row[4], row[1], row[2], q["acc_re"], q["acc_im"], A.w_hz(q["w"]), q["passed"], "match" if ok else "MISMATCH"))
print("windows: RTL %d, model %d, mismatches %d" % (len(win), len(seq), nb)); bad += nb
want = A.loads_of(seq); got = {int(a): int(b) for a, b in ld}
nl = int(len(want) != len(got) or any(got.get(k) != v for k, v in want.items()))
print("loads: RTL %d, model %d: %s   RTL: %s" % (len(got), len(want), "identical" if not nl else "MISMATCH", ", ".join("sym %d: %+.1f Hz" % (k, A.w_hz(v)) for k, v in list(got.items())[:4])))
bad += nl
r = F.receive_fixed(xi, xq, omega_loads=want); r["bits"] = r["bits"].reshape(-1, 2) @ np.array([2, 1])
d = np.loadtxt(os.path.join(HERE, "rtl_rx_out.txt"), dtype=np.int64); k = min(len(d), len(r["bits"]))
for j, name in enumerate(("bits", "zi", "zq", "omega", "rate", "g", "e_t", "e_c")):
    mm = int(np.sum(d[:k, j] != r[name][:k])); bad += mm; print("  engine %-6s mismatches %d" % (name, mm))
print("engine: RTL symbols %d, model %d, compared %d; Costas omega at the end %+.1f Hz" % (len(d), len(r["bits"]), k, r["omega"][k - 1] / 2 ** 32 * 960e3))
print("RESULT:", "MATCH (0 mismatches)" if bad == 0 else "MISMATCH (%d)" % bad)
