#!/usr/bin/env python3
"""The real front end on a 16-QAM signal: the integer polyphase matched filter / derivative filter, timing loop and symbol-rate AGC of rtl/qpsk_rx.v (qpsk_rx_fixed.receive_fixed; the Costas loop in it
is the QPSK one and is ignored: its outputs do not feed back into the symbols mi2, mq2) -> FrameRxHW (the ZC sync + 16-QAM PLL model).

    source tools/gnuradio_env.sh; python3 study_frontend16.py [quick|all]
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "qpsk", "p501_rx"))
import qpsk_rx_fixed as Q
import frame16 as F
from make_signal16 import synth16
from framerx_hw import FrameRxHW

REF = F.prbs15_indices()
R_UNIT = 4096 * np.sqrt(10)                  # unit RMS in counts: the inner 16-QAM level is 4096
AREF = int(round(1.0275 * R_UNIT))            # mean of max + min/2 over random 16-QAM at unit RMS


def front(xi, xq, mu=40, ref=AREF, timing_bw=2 * np.pi / 400):
    regs = Q.regs_from_bw(timing_bw=timing_bw, ref=ref, mu=mu)
    return Q.receive_fixed(xi, xq, regs), regs


def case(nfr=120, snr=22, cfo=3000, ppm=10.4, mu=40, timing_bw=2 * np.pi / 400, rx_kw=None, scale_to_unit=True):
    xi, xq, ids = synth16(nfr, snr_db=snr, cfo_hz=cfo, ppm=ppm)
    o, regs = front(xi, xq, mu=mu, timing_bw=timing_bw)
    m = (o["mi2"] + 1j * o["mq2"]).astype(complex)
    st = slice(len(m) // 3, None)                                       # after the loops have settled
    rms = np.sqrt(np.mean(np.abs(m[st]) ** 2)) / R_UNIT
    ppm_est = -o["rate"][st].mean() / 2 ** 16 / Q.NF / Q.SPS * 1e6
    clip = np.mean(np.abs(o["e_t"][st]) >= 8191)
    r = FrameRxHW(**(rx_kw or dict(word_mode="aided", anchor="first"))).run(m / R_UNIT, ref_idx=REF)
    fe = np.array(r.frame_errs); skip = 15
    ser_ss = fe[skip:].sum() / max((len(fe) - skip) * F.N_PAY, 1)                       # after the loops have settled
    evm_ss = float(np.mean(r.evm[skip:])) if len(r.evm) > skip else float("nan")
    return dict(ser_ss=ser_ss, evm_ss=evm_ss, rms_db=20 * np.log10(rms), g_std=np.std(o["g"][st]) / np.mean(o["g"][st]), ppm=ppm_est, clip=clip, et_std=np.std(o["e_t"][st]),
                frames=r.frames, locks=r.locks, ser=r.sym_err / max(r.sym_cnt, 1), bad=r.bad_frames, m=m, o=o, r=r)


def show(title, **kw):
    c = case(**kw)
    print("%-30s level %+5.2f dB, gain scatter %.3f, clock %+6.1f ppm, e_t clipped %.3f | locks %d SER total %.1e, after 15 frames %.1e (EVM %.1f dB) bad %d" %
          (title, c["rms_db"], c["g_std"], c["ppm"], c["clip"], c["locks"], c["ser"], c["ser_ss"], c["evm_ss"], c["bad"]))
    return c


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "quick"
    show("22 dB, CFO 3 kHz, 10.4 ppm, default loops")
    if what == "all":
        for snr in (18, 20, 25, 30):
            show("SNR %d dB, CFO 3 kHz" % snr, snr=snr)
        for cfo in (0, 1500, 6000):
            show("CFO %d Hz, 22 dB" % cfo, cfo=cfo)
        for mu in (10, 20, 80):
            show("AGC MU %d" % mu, mu=mu)
        for bw in (800, 1600):
            show("timing loop 2pi/%d" % bw, timing_bw=2 * np.pi / bw)
        for ppm in (0, -30, 50):
            show("clock offset %d ppm" % ppm, ppm=ppm)
