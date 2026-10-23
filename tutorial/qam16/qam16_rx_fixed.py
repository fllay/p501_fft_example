"""Bit-exact integer model of the 16-QAM receiver of PLAN_QAM16.md (the specification of the RTL): front end, ZC synchroniser (qam_zc_fixed.py), delay line, 16-QAM PLL and slicer.

front16(xi, xq, regs)   ADC counts (4 samples per symbol) -> mi2, mq2: the integer polyphase matched + derivative filter and timing loop of rtl/qpsk_rx.v (qpsk_rx_fixed.py), with the 16-QAM symbol-rate AGC:
                        power detector P = mi2^2 + mq2^2, g += (MU (PREF - P)>>8 + 2^23) >> 24 (ROUNDED: the floor of the QPSK AGC leaves a gain bias of -0.5 LSB per symbol, -0.6 dB at MU 40)
engine16(mi, mq, sync)  the PLL: the symbol j is derotated D symbols after it arrives (the delay line gives the synchroniser time to deliver w and th0 before the first payload symbol)
    scale: unit RMS = R = 4096 sqrt(10) counts, the inner 16-QAM level L = 4096, thresholds 0 and +-2L;  z = m e^{-j theta} (1024-entry Q15 table, floor shifts as the engine)
    phase error e (K_e = 640 per unit of float error, 13 bit):
      data    s = slicer(z) in units of L ({-3,-1,1,3} per axis):  e = (zq si - zi sq + 32) >> 6          (shift-add, no multiplier: 3x = 2x + x)
      pilot   s = +-3 (the pilot is +-1 = 3.16 L): e = (9 zq p + 32) >> 6                                    (weight 3, 9x = 8x + x)
      CP/word ZC[k] known, Q14: e = ((zq ZCr - zi ZCi) 13 + 2^21) >> 22     (aided) or no update (freeze); the references come from the predicted frame position
    omega += (CB e + 128) >> 8;  theta += omega + ((CA e + 128) >> 8)         (turns x 2^32; rounded)
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "qpsk", "p501_rx"))
import qpsk_rx_fixed as Q
import frame16 as F
import qam_zc_fixed as Z

R_UNIT = 12953
LV = 4096
KE = 640
D_DELAY = 8
NF, SPS = Q.NF, Q.SPS


def loop_gains(bw, damping=np.sqrt(2) / 2):
    den = 1 + 2 * damping * bw + bw * bw
    return 4 * damping * bw / den, 4 * bw * bw / den


def regs16(timing_bw=2 * np.pi / 400, loop_bw=0.02, mu=136, g0=1024, max_rate=0.05, timing_bw_acq=2 * np.pi / 100, mu_acq=544, acq_symbols=6000):
    """timing_bw_acq / mu_acq / acq_symbols: wide timing loop and fast AGC for the first acq_symbols symbols (in the FPGA: until the synchroniser has locked and NSW hits have followed, as the Costas gains of the m-sequence project)"""
    ta, tb = loop_gains(timing_bw); al, be = loop_gains(loop_bw)
    tqa, tqb = loop_gains(timing_bw if timing_bw_acq is None else timing_bw_acq)
    return dict(TA=int(round(ta * 2 ** Q.F_T)), TB=int(round(tb * 2 ** Q.F_T)), MU=int(mu), G0=int(g0), MAXR=int(round(max_rate * NF * 2 ** 16)),
                TAA=int(round(tqa * 2 ** Q.F_T)), TBA=int(round(tqb * 2 ** Q.F_T)), MUA=int(mu if mu_acq is None else mu_acq), ACQ=int(acq_symbols),
                PREF=(R_UNIT * R_UNIT) >> 8, CA=int(round(al * 2 ** 40 / (2 * np.pi * KE))), CB=int(round(be * 2 ** 40 / (2 * np.pi * KE))))


def front16(xi, xq, regs=None, max_symbols=None):
    R = regs16() if regs is None else regs
    cm, cd = Q.coefs()
    xi = np.asarray(xi, dtype=np.int64); xq = np.asarray(xq, dtype=np.int64)
    g, rate = R["G0"], 0
    p = (Q.NTAPS * NF + NF // 2) << 16
    out = {k: [] for k in ("mi2", "mq2", "g", "rate", "e_t")}
    n = 0
    clip = Q.clip
    while True:
        t = p >> 20; k = (p >> 16) & (NF - 1)
        if t >= len(xi) or (max_symbols is not None and n >= max_symbols): break
        wi = xi[t - Q.NTAPS + 1:t + 1][::-1]; wq = xq[t - Q.NTAPS + 1:t + 1][::-1]
        mi = clip(int(np.dot(wi, cm[k])) >> 11, -2 ** 23, 2 ** 23 - 1); mq = clip(int(np.dot(wq, cm[k])) >> 11, -2 ** 23, 2 ** 23 - 1)
        di = clip(int(np.dot(wi, cd[k])) >> 11, -2 ** 23, 2 ** 23 - 1); dq = clip(int(np.dot(wq, cd[k])) >> 11, -2 ** 23, 2 ** 23 - 1)
        mi2 = clip((mi * g) >> 10, -32768, 32767); mq2 = clip((mq * g) >> 10, -32768, 32767)
        di2 = clip((di * g) >> 10, -32768, 32767); dq2 = clip((dq * g) >> 10, -32768, 32767)
        e_p = R["PREF"] - ((mi2 * mi2 + mq2 * mq2) >> 8)
        acq = n < R["ACQ"]
        mu_n, ta_n, tb_n = (R["MUA"], R["TAA"], R["TBA"]) if acq else (R["MU"], R["TA"], R["TB"])
        g = clip(g + ((mu_n * e_p + (1 << 23)) >> 24), 16, 2 ** 17 - 1)
        e_t = clip((mi2 * di2 + mq2 * dq2) >> 13, -8191, 8191)
        rate = clip(rate + ((tb_n * e_t + (1 << (Q.F_T - 4))) >> (Q.F_T - 3)), -R["MAXR"], R["MAXR"])
        p += ((NF * SPS) << 16) + rate + ((ta_n * e_t) >> (Q.F_T - 3))
        for key, val in (("mi2", mi2), ("mq2", mq2), ("g", g), ("rate", rate), ("e_t", e_t)): out[key].append(val)
        n += 1
    return {k: np.array(v, dtype=np.int64) for k, v in out.items()}


class Result:
    pass


def _level(z):
    return -3 if z < -2 * LV else (-1 if z < 0 else (1 if z < 2 * LV else 3))


def engine16(mi, mq, sy, regs=None, word_mode="aided", pilot_weight=3, ref_idx=None, check_causality=True):
    """The PLL over the symbols with the labels from the synchroniser result `sy` (qam_zc_fixed.sync). pilot_weight: 3 (9x) or 5 (15x) or 1 (3x), as shift-adds"""
    R = regs16() if regs is None else regs
    CA, CB = R["CA"], R["CB"]
    mi = np.asarray(mi, dtype=np.int64); mq = np.asarray(mq, dtype=np.int64); L = len(mi)
    cos_l, sin_l = Z.COS_L, Z.SIN_L
    pmul = 3 * pilot_weight
    res = Result(); res.frames = res.locks = 0; res.sym_err = res.sym_cnt = res.bit_err = res.bad_frames = 0
    res.frame_errs = []; res.evm = []; res.lock_w = []; res.out = []; res.lates = []
    ref_idx = F.prbs15_indices() if ref_idx is None else ref_idx
    fl = sy.frames
    i = 0
    while i < len(fl):
        f = fl[i]
        assert f["lock"]
        res.locks += 1; res.lock_w.append(f["w"])
        theta, omega = f["th0"], f["w"]
        e_prev = f["e"]
        j = f["e"] + 1
        k = i
        while k < len(fl) and (k == i or not fl[k]["lock"]):
            fk = fl[k]; e_f = fk["e"]
            if k == i:
                e_pred = None
            else:
                e_pred = e_prev + F.FRAME
            if check_causality:
                res.lates.append((e_f + 1 + D_DELAY) - (fk["known"] + 2))
            pay_end = e_f + F.PAY_LEN
            err2 = ref2 = 0.0; data_n = 0; ne = 0; idxs = []
            if pay_end >= L: k = len(fl); break
            while j <= pay_end:
                # label
                if j > e_f:
                    o = j - (e_f + 1); b, r_ = divmod(o, F.BLK)
                    kind = 2 if r_ == F.BLK - 1 else 1; arg = b if kind == 2 else b * F.N_DATA + r_
                elif e_pred is not None and e_pred - 70 <= j <= e_pred and word_mode == "aided":
                    c = j - (e_pred - 70); kind = 3; arg = c - 8 if c >= 8 else (F.N_ZC - 8 + c)        # CP = ZC[55..62], word = ZC[0..62]
                else:
                    kind = 0; arg = 0
                idx = (theta >> 22) & 1023; c_, s_ = int(cos_l[idx]), int(sin_l[idx])
                zi = (int(mi[j]) * c_ + int(mq[j]) * s_) >> 15; zq = (int(mq[j]) * c_ - int(mi[j]) * s_) >> 15
                e = 0
                if kind == 1:
                    si, sq = _level(zi), _level(zq)
                    e = (zq * si - zi * sq + 32) >> 6
                    err2 += (zi - si * LV) ** 2 + (zq - sq * LV) ** 2; ref2 += (si * LV) ** 2 + (sq * LV) ** 2; data_n += 1
                    ix = 4 * F.LEVEL_IDX[si] + F.LEVEL_IDX[sq]; idxs.append(ix)
                    res.out.append((zi, zq))
                elif kind == 2:
                    e = (pmul * zq * int(F.PILOTS[arg]) + 32) >> 6
                elif kind == 3:
                    e = ((zq * int(Z.ZCR[arg]) - zi * int(Z.ZCI[arg])) * 13 + (1 << 21)) >> 22
                if kind:
                    omega = Q.clip(omega + ((CB * e + 128) >> 8), -2 ** 31, 2 ** 31 - 1)
                    theta = (theta + omega + ((CA * e + 128) >> 8)) & 0xFFFFFFFF
                else:
                    theta = (theta + omega) & 0xFFFFFFFF
                j += 1
            if len(idxs) == F.N_PAY:
                d = np.asarray(idxs) != ref_idx; ne = int(d.sum())
                res.sym_err += ne; res.sym_cnt += F.N_PAY; res.frame_errs.append(ne)
                xb = np.asarray(idxs) ^ ref_idx; res.bit_err += int(sum(bin(v).count("1") for v in xb[d]))
                if ne > 0.2 * F.N_PAY: res.bad_frames += 1
                res.evm.append(10 * np.log10(max(err2, 1e-12) / max(ref2, 1e-12))); res.frames += 1
            e_prev = e_f
            k += 1
        i = k
    return res


def receive16(xi, xq, regs=None, **kw):
    """ADC counts -> front end -> synchroniser -> engine"""
    fe = front16(xi, xq, regs)
    sy = Z.sync(fe["mi2"], fe["mq2"])
    return fe, sy, engine16(fe["mi2"], fe["mq2"], sy, regs, **kw)
