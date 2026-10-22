"""Compare the RTL logs of tb_qpsk_rx_sync.v with the integer models.   python3 compare_sync.py [FL [PL [THR]]]   (the plusargs of the simulation: fl pl thr; the test signal x = a|b|c via the environment variable SIGNAL, default a)
 1. rtl_sy_corr.txt: C, E, M and the candidate of every symbol;  2. rtl_sy_peak.txt: the peaks (symbol of the decision, peak symbol, C at the peak, state);  3. rtl_sy_gate.txt: the gate of every symbol;
 4. the counters at the end (peaks, hits, misses, false, locks, losses, ref, C, M, E, late);  5. rtl_rx_out.txt: the 8 engine columns against receive_fixed;  6. the gated checker's bits / mismatches."""
import sys, os, re
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, os.path.join(HERE, "..", "..", "p501_rx"))
import qpsk_rx_fixed as F, qpsk_sync_fixed as S
FL = int(sys.argv[1]) if len(sys.argv) > 1 else 256
PL = int(sys.argv[2]) if len(sys.argv) > 2 else 192
THR = int(sys.argv[3]) if len(sys.argv) > 3 else 140
SIG = os.environ.get("SIGNAL", "a")
xi, xq = np.load(os.path.join(HERE, "xi_%s.npy" % SIG)), np.load(os.path.join(HERE, "xq_%s.npy" % SIG))
r = F.receive_fixed(xi, xq); r["bits_flat"] = r["bits"]; r["bits"] = r["bits"].reshape(-1, 2) @ np.array([2, 1])
s = S.run_sync(r["mi2"], r["mq2"], FL, PL, thr=THR)
bad = 0
c = np.loadtxt(os.path.join(HERE, "rtl_sy_corr.txt"), dtype=np.int64).reshape(-1, 6); k = min(len(c), len(s["cre"]))
for j, name in ((1, "cre"), (2, "cim"), (3, "en"), (4, "met")):
    mm = int(np.sum(c[:k, j] != s[name][:k])); bad += mm; print("  correlator %-4s mismatches %d" % (name, mm))
mm = int(np.sum(c[:k, 5] != s["cand"][:k].astype(int))); bad += mm; print("  correlator cand mismatches %d  (%d symbols)" % (mm, k))
pk = np.loadtxt(os.path.join(HERE, "rtl_sy_peak.txt"), dtype=np.int64).reshape(-1, 5)
mp = int(len(pk) != len(s["peaks"]) or np.any(pk[:, 1] != np.array(s["peaks"][:len(pk)]))); bad += mp
print("  peaks: RTL %d, model %d: %s   (first peak symbols %s)" % (len(pk), len(s["peaks"]), "identical" if not mp else "MISMATCH", pk[:4, 1].tolist()))
g = np.loadtxt(os.path.join(HERE, "rtl_sy_gate.txt"), dtype=np.int64).reshape(-1, 2); kg = min(len(g), len(s["gate"]))
mg = int(np.sum(g[:kg, 1] != s["gate"][:kg].astype(int))); bad += mg; print("  gate mismatches %d of %d symbols (open for %d)" % (mg, kg, int(g[:kg, 1].sum())))
log = open(os.path.join(HERE, "xsim_sync.log")).read() if os.path.exists(os.path.join(HERE, "xsim_sync.log")) else ""
vals = {m.group(1): int(m.group(2)) for m in re.finditer(r"^([A-Za-z ]+) = (-?\d+)$", log, re.M)}
st = s["stats"]; sn = s["snap"]
want = dict(ndet=st["n_det"], nhit=st["n_hit"], nmiss=st["n_miss"], nfalse=st["n_false"], nlock=st["n_lock"], nlost=st["n_lost"], late=0, cre=sn["cre"], cim=sn["cim"], met=sn["met"], en=sn["en"], pk=sn["p"])
for key, w in want.items():
    ok = vals.get(key) == w; bad += 0 if ok else 1
    print("  register %-6s RTL %s  model %d  %s" % (key, vals.get(key), w, "ok" if ok else "MISMATCH"))
d = np.loadtxt(os.path.join(HERE, "rtl_rx_out.txt"), dtype=np.int64); ke = min(len(d), len(r["bits"]))
for j, name in enumerate(("bits", "zi", "zq", "omega", "rate", "g", "e_t", "e_c")):
    mm = int(np.sum(d[:ke, j] != r[name][:ke])); bad += mm; print("  engine %-6s mismatches %d" % (name, mm))
nb, nm = S.gated_checker(r["bits_flat"], s["gate"])
okb = vals.get("bits checked") == nb and vals.get("mismatches") == nm; bad += 0 if okb else 1
print("  gated checker: RTL bits %s mismatches %s, model bits %d mismatches %d  %s" % (vals.get("bits checked"), vals.get("mismatches"), nb, nm, "ok" if okb else "MISMATCH"))
print("  events:", [e for e in s["events"] if e[1] != "hit"][:8])
print("RESULT:", "MATCH (0 mismatches)" if bad == 0 else "MISMATCH (%d)" % bad)
