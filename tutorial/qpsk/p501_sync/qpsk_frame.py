#!/usr/bin/env python3
"""The frame format of the m-sequence synchronisation project (chapter 4e, part 1): known preamble + known payload, repeated.

    frame = PREAMBLE (64 symbols)  +  PAYLOAD (PL symbols, PRBS-15 restarted in every frame)         FL = 64 + PL symbols
    preamble: symbol 0 is the reference (phase step 0); the 63 phase STEPS of symbols 1 .. 63 are the chips of an m-sequence of length 63
              (LFSR x^6 + x + 1, a[n+6] = a[n+1] xor a[n], seed 1 0 0 0 0 0): bit 0 -> step 0 (chip +1), bit 1 -> step 180 degrees (chip -1)
    why STEPS: the modulation is differential (DQPSK); the phase step between two symbols, d = m_n conj(m_n-1), does not depend on the carrier phase and only
               by 2 pi f T on the frequency offset, so the correlator works before any loop has locked, and arg(correlation) = 2 pi f T measures the frequency
               (data aided, unambiguous for |f| < 480 kHz, against 120 kHz of the 4th-power estimator).
In the transmitter's bit stream (before the pre-differential code [0,1,3,2]): a chip +1 is the 2-bit chunk 00, a chip -1 the chunk 11.
FL * 2 bits must be a multiple of 8 for GNU Radio's packed bytes: PL a multiple of 4.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "p501_tx"))
from qpsk_model import prbs15_bits

PRE_SYMBOLS = 64
NCHIPS = 63


def mseq(seed=(1, 0, 0, 0, 0, 0)):
    """The 63 bits of the m-sequence x^6 + x + 1."""
    a = list(seed)
    while len(a) < NCHIPS:
        n = len(a) - 6
        a.append(a[n + 1] ^ a[n])
    return np.array(a[:NCHIPS], dtype=np.uint8)


def chips():
    """+1 / -1 chips (bit 0 -> +1)."""
    return (1 - 2 * mseq().astype(int)).astype(int)


def frame_bits(pl):
    """The bits of ONE frame (2 per symbol, first bit = MSB of the chunk, as qpsk_model.symbol_indices expects): the preamble, then the PRBS-15 payload."""
    pre = [0, 0]                                                          # symbol 0: the reference, step 0
    for c in mseq():
        pre += [1, 1] if c else [0, 0]                                    # chip -1 (m-sequence bit 1) -> chunk 11 -> step 180 degrees
    return np.concatenate([np.array(pre, dtype=np.uint8), prbs15_bits(2 * pl)])


def frames_bits(pl, nframes):
    return np.tile(frame_bits(pl), nframes)


if __name__ == "__main__":
    c = chips(); ac = np.array([int(np.dot(c, np.roll(c, k))) for k in range(NCHIPS)])
    print("m-sequence: length", len(c), "ones", int(mseq().sum()), " periodic autocorrelation: peak", ac[0], "sidelobes", set(ac[1:].tolist()))
    print("frame of PL = 960: %d symbols, %d bits, %.3f ms at 960 ksym/s" % (PRE_SYMBOLS + 960, len(frame_bits(960)), (PRE_SYMBOLS + 960) / 960.0))
