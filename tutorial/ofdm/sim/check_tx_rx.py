#!/usr/bin/env python3
"""The frames of the FPGA transmitter (tx_out.txt of run_tx.sh, or the integer model) through the integer model of the FPGA receiver: the DAC value >> 4 as the 12-bit ADC count (the digital loopback of the AD9361), noise-free.
    python3 check_tx_rx.py [tx_out.txt] [sc|sts]"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ofdm_fixed as FX, ofdm_tx_fixed as T
VAR = sys.argv[2] if len(sys.argv) > 2 else "sc"
if len(sys.argv) > 1 and sys.argv[1] != "-": d = np.loadtxt(sys.argv[1], dtype=np.int64); oi, oq = d[:, 0], d[:, 1]
else:
    I, Q = T.frame_samples(VAR); oi, oq = np.tile(T.dac(I, 26000), 4), np.tile(T.dac(Q, 26000), 4)
xi, xq = oi >> 4, oq >> 4
print("ADC counts rms %.0f" % np.sqrt(np.mean(xi ** 2 + xq ** 2) / 2 * 48 / 47))
xi = np.concatenate([np.zeros(300, np.int64), xi, np.zeros(300, np.int64)]); xq = np.concatenate([np.zeros(300, np.int64), xq, np.zeros(300, np.int64)])
res = FX.receive_fixed(xi, xq, var=FX.STS if VAR == "sts" else FX.SC)
if res is None: print("the receiver found no frame"); sys.exit(1)
sc = FX.score(res); print("receiver model: s0 %d, SER %.2e, BER %.2e, EVM %.1f dB" % (res["s0"], sc["ser"], sc["ber"], sc["evm"]) if "s0" in res else "SER %.2e BER %.2e EVM %.1f dB" % (sc["ser"], sc["ber"], sc["evm"]))
sys.exit(0 if sc["ser"] == 0 else 1)
