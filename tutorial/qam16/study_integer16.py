#!/usr/bin/env python3
"""The complete integer receiver (qam16_rx_fixed.py: front end with the 16-QAM AGC, ZC synchroniser, PLL) on 16-QAM signals at 4 samples per symbol (make_signal16.py).
    source tools/gnuradio_env.sh; python3 study_integer16.py [quick|all]"""
import sys
import numpy as np
import frame16 as F
import qam16_rx_fixed as X
from make_signal16 import synth16


def case(nfr=120, snr=22, cfo=3000, ppm=10.4, mu=136, timing_bw=2 * np.pi / 400, loop_bw=0.02, rx_kw=None, skip=15, lead=0, **reg_kw):
    xi, xq, ids = synth16(nfr, snr_db=snr, cfo_hz=cfo, ppm=ppm, lead=lead)
    regs = X.regs16(timing_bw=timing_bw, loop_bw=loop_bw, mu=mu, **reg_kw)
    fe, sy, r = X.receive16(xi, xq, regs, **(rx_kw or {}))
    st = slice(len(fe["mi2"]) // 3, None)
    m = fe["mi2"][st] + 1j * fe["mq2"][st]
    level = 10 * np.log10(np.mean(np.abs(m) ** 2) / X.R_UNIT ** 2)
    fe_ = np.array(r.frame_errs)
    return dict(level=level, g_std=np.std(fe["g"][st]) / np.mean(fe["g"][st]), ppm=-fe["rate"][st].mean() / 2 ** 16 / X.NF / X.SPS * 1e6, locks=r.locks, frames=r.frames,
                ser=r.sym_err / max(r.sym_cnt, 1), ser_ss=fe_[skip:].sum() / max((len(fe_) - skip) * F.N_PAY, 1) if len(fe_) > skip else float("nan"),
                evm_ss=float(np.mean(r.evm[skip:])) if len(r.evm) > skip else float("nan"), bad=r.bad_frames, first_good=next((i for i, v in enumerate(r.frame_errs) if v == 0), -1),
                w_hz=r.lock_w[0] / 2 ** 32 * 960e3 if r.lock_w else float("nan"), late=None, fe=fe, sy=sy, r=r)


def show(title, **kw):
    c = case(**kw)
    print("%-26s level %+5.2f dB gain scatter %.3f clock %+6.1f ppm | locks %d frames %3d SER %.1e (after 15: %.1e) EVM %.1f dB bad %2d first clean frame %2d lock w %+6.0f Hz" %
          (title, c["level"], c["g_std"], c["ppm"], c["locks"], c["frames"], c["ser"], c["ser_ss"], c["evm_ss"], c["bad"], c["first_good"], c["w_hz"]))
    return c


def leadin():
    print("== the signal starts after idle noise (acquisition mode until NSW = 4 frames have followed the lock): bad frames / first clean frame / symbol at which the acquisition ends")
    for lead in (0, 200, 500, 1000, 1500, 2500):
        c = case(nfr=60, lead=lead)
        print("  lead %4d: bad %d, first clean frame %d, SER after 15 frames %.1e, acquisition ends at symbol %s" % (lead, c["bad"], c["first_good"], c["ser_ss"], [t for t, on in c["fe"]["acq_sched"] if not on][:1]))


def compare_float(cases=((25, 3000), (20, -4000), (18, 1500), (16, 0))):
    """the integer receiver against the float FrameRxHW fed with the same front-end output"""
    from framerx_hw import FrameRxHW
    REF = F.prbs15_indices()
    print("== integer engine against FrameRxHW (aided / first, bw 0.02) on the same symbols mi2, mq2 of the integer front end")
    for snr, cfo in cases:
        c = case(nfr=150, snr=snr, cfo=cfo)
        m = (c["fe"]["mi2"] + 1j * c["fe"]["mq2"]) / X.R_UNIT
        f = FrameRxHW(word_mode="aided", anchor="first").run(m, ref_idx=REF)
        fe = np.array(f.frame_errs)
        print("  %d dB %+5d Hz: integer SER after 15 frames %.1e EVM %.1f dB | float SER %.1e EVM %.1f dB" % (snr, cfo, c["ser_ss"], c["evm_ss"],
              fe[15:].sum() / max((len(fe) - 15) * F.N_PAY, 1), np.mean(f.evm[15:])))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "quick"
    show("22 dB, 3 kHz, 10.4 ppm")
    if what == "all":
        for snr in (16, 18, 20, 25, 30, 40):
            show("SNR %d dB" % snr, snr=snr)
        for cfo in (-5000, 0, 1500, 5000, 6500):
            show("CFO %d Hz" % cfo, cfo=cfo)
        for mu in (17, 34, 136, 272):
            show("AGC MU %d" % mu, mu=mu)
        for bw in (200, 800):
            show("timing loop 2pi/%d" % bw, timing_bw=2 * np.pi / bw)
        for ppm in (-40, 0, 40):
            show("clock %d ppm" % ppm, ppm=ppm)
        for bw in (0.01, 0.04):
            show("PLL bw %.2f" % bw, loop_bw=bw)
        show("freeze word", rx_kw=dict(word_mode="freeze"))
        show("lead-in 500 symbols", lead=500)
        show("no acquisition mode", timing_bw_acq=2 * np.pi / 400, mu_acq=136, acq_symbols=0, nsw=0)
        leadin()
        compare_float()
