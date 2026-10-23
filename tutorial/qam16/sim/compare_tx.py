#!/usr/bin/env python3
"""rtl_tx16.txt (tb_qam16_tx_fr.v) against qam16_tx_model.model().   python3 compare_tx.py [amp]
The testbench logs dac after each ce edge; the sample n of the model is the value after ce number n."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import qam16_tx_model as M
amp = int(sys.argv[1]) if len(sys.argv) > 1 else 0x2000
d = np.loadtxt(os.path.join(HERE, "rtl_tx16.txt"), dtype=np.int64)
i, q = M.model(len(d), amp)
# the log is taken one clock after the ce edge's non-blocking updates are NOT yet visible: the value read at the end of the k-th period is the one registered at ce number k
mi = int(np.sum(d[:, 0] != i)); mq = int(np.sum(d[:, 1] != q))
if mi + mq:                                           # try the one-sample shift of the logging
    mi2 = int(np.sum(d[1:, 0] != i[:-1])); mq2 = int(np.sum(d[1:, 1] != q[:-1]))
    print("  unshifted mismatches I %d Q %d; shifted by one sample I %d Q %d" % (mi, mq, mi2, mq2))
print("  %d samples: I mismatches %d, Q mismatches %d, peak %d, rms %.0f" % (len(d), mi, mq, np.max(np.abs(d[:, 0])), np.sqrt(np.mean(d[2000:, 0].astype(float) ** 2))))
print("RESULT:", "MATCH (0 mismatches)" if mi + mq == 0 else "MISMATCH (%d)" % (mi + mq))
