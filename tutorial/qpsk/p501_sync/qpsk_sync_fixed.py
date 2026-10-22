#!/usr/bin/env python3
"""Bit-exact integer model of the frame synchroniser rtl/qpsk_sync.v (chapter 4e, part 1): correlation of the phase steps with the m-sequence preamble, peak detection, frame tracking, payload gate.

Input: the symbols m = (mi2, mq2) of the receiver engine (after the polyphase matched filter, the timing loop and the AGC, before the Costas derotation: the synchroniser works
before any carrier loop has locked).  Per symbol n:
    d_n  = round((m_n conj(m_n-1)) >> 15), clipped to +-16383        the phase step (the same arithmetic as the 4th-power estimator; d_0 = 0)
    C_n  = sum_{k=0..62} chip[k] d[n-62+k]                            (complex; chip[k] = +-1 is the m-sequence: the newest d is the LAST step of the preamble)
    E_n  = sum_{k=0..62} |d[n-62+k]|                                  |x| ~ max(|re|,|im|) + min(|re|,|im|)/2
    M_n  = |C_n| in the same approximation
    cand_n = E_n > 0 and 256 M_n >= THR E_n                           (THR: register, Q8; 140 = 0.55)
    peak at n-1  <=>  cand_{n-1} and M_{n-1} >= M_{n-2} and M_{n-1} > M_n          (one symbol of look-ahead: the peak symbol p = n-1 is the last step of a preamble)
Tracker (state after processing symbol n, visible to the payload gate of symbol n+1):
    SEARCH: a peak at p with a previous peak at q, |p - q - FL| <= TOL  -> LOCKED, ref = p.  Otherwise q = p.
    LOCKED: expected = ref + FL.  A peak with |p - expected| <= TOL is a HIT (ref = p, miss run = 0); another peak counts as false.
            When n = ref + FL + TOL + 1 has been processed without a hit: MISS (ref += FL, miss run += 1); MISSMAX misses in a row -> SEARCH (lost).
Payload gate of symbol n (state before processing n):  LOCKED and GUARD <= n - ref - 1 < PL.      The PRBS checker of the engine counts only inside the gate and restarts at its start.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "p501_rx_fll")); sys.path.insert(0, os.path.join(HERE, "..", "p501_rx"))
import qpsk_fe_fixed as E
from qpsk_frame import chips

NCH = 63
CHIP = chips()
THR_DEFAULT, TOL_DEFAULT, MISSMAX_DEFAULT, GUARD_DEFAULT = 140, 1, 3, 2


def amag(r, i):
    a, b = abs(int(r)), abs(int(i))
    return max(a, b) + (min(a, b) >> 1)


def run_sync(mi2, mq2, fl, pl, thr=THR_DEFAULT, tol=TOL_DEFAULT, missmax=MISSMAX_DEFAULT, guard=GUARD_DEFAULT):
    n_sym = len(mi2)
    dr, di, _ = E.d_symbols(mi2, mq2)
    dr = [int(v) for v in dr]; di = [int(v) for v in di]
    dr[0] = 0; di[0] = 0                                               # the first symbol has no predecessor (the RTL's previous symbol is 0 as well, so d_0 = 0 anyway)
    cre = np.zeros(n_sym, dtype=np.int64); cim = np.zeros(n_sym, dtype=np.int64); en = np.zeros(n_sym, dtype=np.int64); met = np.zeros(n_sym, dtype=np.int64)
    cand = np.zeros(n_sym, dtype=bool); gate = np.zeros(n_sym, dtype=bool); peak_at = []
    st = dict(state=0, last_valid=False, last_p=0, ref=0, miss_run=0, n_det=0, n_hit=0, n_miss=0, n_false=0, n_lock=0, n_lost=0)
    events = []
    snap = dict(cre=0, cim=0, met=0, en=0, p=0)
    for n in range(n_sym):
        # payload gate of symbol n: the state after the symbols < n
        if st["state"] == 1:
            pos = n - st["ref"] - 1
            gate[n] = (pos >= guard) and (pos < pl)
        # the correlator for symbol n
        sr = si = se = 0
        for k in range(NCH):
            j = n - 62 + k
            if j >= 0:
                a, b = dr[j], di[j]
                if CHIP[k] > 0: sr += a; si += b
                else: sr -= a; si -= b
                se += amag(a, b)
        cre[n], cim[n], en[n] = sr, si, se
        met[n] = amag(sr, si)
        cand[n] = se > 0 and 256 * met[n] >= thr * se
        # peak at p = n - 1
        if n >= 1:
            p = n - 1
            m2 = met[n - 2] if n >= 2 else 0
            if cand[p] and met[p] >= m2 and met[p] > met[n]:
                st["n_det"] += 1; peak_at.append(p)
                snap = dict(cre=int(cre[p]), cim=int(cim[p]), met=int(met[p]), en=int(en[p]), p=p)
                if st["state"] == 0:
                    if st["last_valid"] and abs(p - st["last_p"] - fl) <= tol:
                        st.update(state=1, ref=p, miss_run=0, last_valid=False); st["n_lock"] += 1; events.append((n, "lock", p))
                    else:
                        st["last_p"] = p; st["last_valid"] = True
                else:
                    if abs(p - (st["ref"] + fl)) <= tol:
                        st["ref"] = p; st["miss_run"] = 0; st["n_hit"] += 1; events.append((n, "hit", p))
                    else:
                        st["n_false"] += 1; events.append((n, "false", p))
        if st["state"] == 1 and n == st["ref"] + fl + tol + 1:
            st["n_miss"] += 1; st["miss_run"] += 1; st["ref"] += fl; events.append((n, "miss", st["ref"]))
            if st["miss_run"] >= missmax:
                st.update(state=0, last_valid=False); st["n_lost"] += 1; events.append((n, "lost", 0))
    return dict(cre=cre, cim=cim, en=en, met=met, cand=cand, gate=gate, peaks=peak_at, events=events, stats=st, snap=snap)


def gated_checker(bits, gate):
    """The engine's PRBS-15 checker with the payload gate: bits = 2 per symbol (b0, b1). Restarts (history empty) when the gate opens; holds when it is closed. (n_bits, n_mism)."""
    sr, n, n_bits, n_mism, prev = 0, 0, 0, 0, False
    for k in range(len(gate)):
        if not gate[k]:
            prev = False; continue
        if not prev: n = 0                                              # restart
        prev = True
        b0, b1 = int(bits[2 * k]), int(bits[2 * k + 1])
        pred0 = ((sr >> 14) ^ (sr >> 13)) & 1
        sr1 = ((sr << 1) & 0x7FFF) | b0
        pred1 = ((sr1 >> 14) ^ (sr1 >> 13)) & 1
        pr0, pr1 = n >= 15, n >= 14
        n_mism += int(pr0 and b0 != pred0) + int(pr1 and b1 != pred1)
        n_bits += int(pr0) + int(pr1)
        sr = ((sr1 << 1) & 0x7FFF) | b1
        n = 15 if n >= 13 else n + 2
    return n_bits, n_mism


def freq_hz(cre, cim):
    """The frequency offset from the correlation at a peak: arg(C) = 2 pi f T (data aided: unambiguous for |f| < 480 kHz)."""
    return float(np.arctan2(cim, cre) / (2 * np.pi) * 960e3)
