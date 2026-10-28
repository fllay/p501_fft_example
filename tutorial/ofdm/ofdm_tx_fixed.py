#!/usr/bin/env python3
"""Bit-exact integer model of the FPGA OFDM transmitter rtl/ofdm_tx.v: variant SC (the Schmidl-and-Cox frame of the overlay p501_ofdm_rx_sc) and variant STS (the 128-sample short training field, overlay p501_ofdm_rx_sts).

The frame is the one of ofdm_model.tx_frame(preamble="scu"): 48 symbols of 80 samples (16 prefix + 64) = 3840 samples = 1 ms at 3.84 MS/s:
    slot 0      the Schmidl-and-Cox symbol: only the even subcarriers loaded (two identical halves of 32 samples)
    slot 1, 2   the training symbol twice (QPSK on all 28 used subcarriers, each with its own prefix)
    slot 3..46  the 44 data symbols: 24 subcarriers of 16-QAM from the PRBS-15 (restarted in every frame), 4 QPSK pilots with the polarity of IEEE 802.11
    slot 47     idle (zeros)
The STS frame (ofdm_model.tx_frame(preamble="sts16")): STS 128 samples (every 4th subcarrier k = -12, -8, -4, 4, 8, 12 loaded: period 16, the 64-sample IFFT twice) | the long training field of 160 samples (the last 32 samples
of the training symbol, then the symbol twice) | 44 data symbols of 80 samples | 32 idle = 3840 samples; 47 segments.
Integer scale: a loaded subcarrier of unit power is U = 1518 counts (QPSK and pilot: +-1073 on I and Q, Schmidl and Cox: +-1518, 16-QAM: levels +-480, +-1440). The IFFT is the FFT of ofdm_fixed.fft64 (bit-exact with
rtl/ofdm_fft.v) on the conjugated values, conjugated again: x[n] = sum_k X[k] exp(+j 2 pi k n / 64), no scaling (8 x the float model of unit power 1, rms 8032, peak about 27200 < 32767).
The DAC value is clip((x * amp) >> 15, +-32767) with amp Q15 (0 .. 32767): the same law as rtl/qam16_tx_fr.v.
    python3 ofdm_tx_fixed.py          self-test against the float model
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ofdm_model as Fm
import ofdm_fixed as FX

N, CP = 64, 16
A_Q, A_SC, A_STS, LQ = 1073, 1518, 2319, 480
LEV = np.array([-3, -1, 3, 1]) * LQ                                   # Gray code 00 01 10 11
SLOTS = 48
USED, DATA, PIL = Fm.USED, Fm.DATA, Fm.PIL
STS_S = (np.where(Fm.STS_V.real > 0, 1, -1), np.where(Fm.STS_V.imag > 0, 1, -1))
TRAIN_S = (np.where(Fm.TRAIN.real > 0, 1, -1), np.where(Fm.TRAIN.imag > 0, 1, -1))
SC_S = (np.where(Fm.SC_V.real > 0, 1, -1), np.where(Fm.SC_V.imag > 0, 1, -1))
PIL_S = (np.where(Fm.PIL_V.real > 0, 1, -1), np.where(Fm.PIL_V.imag > 0, 1, -1))
POL = Fm.POL.astype(int)                                              # +-1 per data symbol
BITS = Fm.payload_bits().astype(int)


def prbs_nibble(l, i):
    """the 4 bits of data subcarrier i of data symbol l"""
    b = BITS[l * 96 + 4 * i: l * 96 + 4 * i + 4]; return int(b[0] * 8 + b[1] * 4 + b[2] * 2 + b[3])


def slot_values(slot, var="sc"):
    """the loaded values of a slot as integers: dict k -> (re, im). SC: slot 0 S&C, 1 and 2 training, 3 .. 46 data, 47 idle. STS: slot 0 the STS, 1 the training symbol, 2 .. 45 data, 46 idle"""
    X = {}
    if var == "sts":
        first_data = 2
        if slot == 0:
            for j, k in enumerate(Fm.STS_K): X[int(k)] = (int(STS_S[0][j]) * A_STS, int(STS_S[1][j]) * A_STS)
        elif slot == 1:
            for j, k in enumerate(USED): X[int(k)] = (int(TRAIN_S[0][j]) * A_Q, int(TRAIN_S[1][j]) * A_Q)
    else:
        first_data = 3
        if slot == 0:
            for j, k in enumerate(Fm.SC_K): X[int(k)] = (int(SC_S[0][j]) * A_SC, int(SC_S[1][j]) * A_SC)
        elif slot in (1, 2):
            for j, k in enumerate(USED): X[int(k)] = (int(TRAIN_S[0][j]) * A_Q, int(TRAIN_S[1][j]) * A_Q)
    if first_data <= slot < first_data + 44:
        l = slot - first_data
        for i, k in enumerate(DATA):
            n = prbs_nibble(l, i); X[int(k)] = (int(LEV[n >> 2]), int(LEV[n & 3]))
        for j, k in enumerate(PIL): X[int(k)] = (int(PIL_S[0][j]) * int(POL[l]) * A_Q, int(PIL_S[1][j]) * int(POL[l]) * A_Q)
    return X


def ifft_int(X):
    """-> (re, im) of the 64 samples, int16 saturated, the IFFT through the forward FFT of the receiver: x = conj(FFT(conj X))"""
    xr = np.zeros(N, np.int64); xi = np.zeros(N, np.int64)
    for k, (r, i) in X.items(): xr[k % N] = r; xi[k % N] = -i
    ar, ai = FX.fft64(xr, xi)
    return np.clip(ar, -32767, 32767), np.clip(-ai, -32767, 32767)


def slot_samples(slot, var="sc"):
    """the samples of a slot: SC: 80 (the last 16 samples of the IFFT, then the 64). STS: slot 0: the 64 twice (128), slot 1: the last 32, the 64 twice (160), data: 80, the idle slot 46: 32 zeros"""
    if var == "sts":
        if slot == 46: return np.zeros(32, np.int64), np.zeros(32, np.int64)
        r, i = ifft_int(slot_values(slot, var))
        if slot == 0: return np.concatenate([r, r]), np.concatenate([i, i])
        if slot == 1: return np.concatenate([r[-32:], r, r]), np.concatenate([i[-32:], i, i])
        return np.concatenate([r[-CP:], r]), np.concatenate([i[-CP:], i])
    r, i = ifft_int(slot_values(slot)) if slot < 47 else (np.zeros(N, np.int64), np.zeros(N, np.int64))
    return np.concatenate([r[-CP:], r]), np.concatenate([i[-CP:], i])


def frame_samples(var="sc"):
    """-> I, Q: the 3840 samples of the frame before the amplitude"""
    parts = [slot_samples(s, var) for s in range(47 if var == "sts" else SLOTS)]
    return np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])


def dac(x, amp):
    """the DAC value: clip((x * amp) >> 15), amp Q15"""
    return np.clip((np.asarray(x, np.int64) * int(amp)) >> 15, -32767, 32767)


if __name__ == "__main__":
    for var, pre in (("sc", "scu"), ("sts", "sts16")):
        I, Q = frame_samples(var); xf, d = Fm.tx_frame(preamble=pre)
        assert len(I) == 3840
        err = (I + 1j * Q) / (8 * A_SC) - xf
        print("%s frame: %d samples, rms %.0f, peak %.0f counts; against the float model: error rms %.4f (signal rms %.4f), max %.4f" %
              (var, len(I), np.sqrt(np.mean(I ** 2 + Q ** 2)), np.max(np.abs(I + 1j * Q)), np.sqrt(np.mean(np.abs(err) ** 2)), np.sqrt(np.mean(np.abs(xf) ** 2)), np.abs(err).max()))
        assert np.sqrt(np.mean(np.abs(err) ** 2)) < 0.01, "the integer frame does not follow the float model"
        assert max(np.abs(I).max(), np.abs(Q).max()) < 32767, "saturation"
    print("ok")
