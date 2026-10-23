"""Bit-exact integer model of the 16-QAM receiver of PLAN_QAM16.md (the specification of the RTL): front end, ZC synchroniser (qam_zc_fixed.py), delay line, 16-QAM PLL and slicer.

front16(xi, xq, regs)   ADC counts (4 samples per symbol) -> mi2, mq2: the integer polyphase matched + derivative filter and timing loop of rtl/qpsk_rx.v (qpsk_rx_fixed.py), with the 16-QAM symbol-rate AGC:
                        power detector P = mi2^2 + mq2^2, g += (MU (PREF - P)>>8 + 2^23) >> 24 (ROUNDED: the floor of the QPSK AGC leaves a gain bias of -0.5 LSB per symbol, -0.6 dB at MU 40)
engine16(mi, mq, sync)  the PLL: the symbol j is derotated D = 10 symbols after it arrives (the delay line gives the synchroniser time to deliver its events: an event with decision index `known` is applied at the engine
                        step n = known + 2, i.e. to the symbol j = n - D; D >= 2 W + 2 so that even the earliest frame (e = ee - W) has not started yet).
    labels: a position counter pos (0..966: CP 0-7, word 8-70, payload 71-966) runs on in the engine; a frame event sets pos = 70 + (j - e) before the symbol j is labelled; a lock event waits for j = e + 1,
            loads theta = th0, omega = w and sets pos = 71; a lost event stops the run.
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
sys.path.insert(0, os.path.join(HERE, "..", "qpsk", "p501_rx_fll"))
import qpsk_fll_fixed as FL

R_UNIT = 12953
LV = 4096
KE = 640
D_DELAY = 10
NF, SPS = Q.NF, Q.SPS


def loop_gains(bw, damping=np.sqrt(2) / 2):
    den = 1 + 2 * damping * bw + bw * bw
    return 4 * damping * bw / den, 4 * bw * bw / den


def regs16(timing_bw=2 * np.pi / 400, loop_bw=0.02, mu=136, g0=1024, max_rate=0.05, timing_bw_acq=2 * np.pi / 100, mu_acq=544, acq_symbols=0, nsw=4):
    """timing_bw_acq / mu_acq / acq_symbols: wide timing loop and fast AGC for the first acq_symbols symbols (in the FPGA: until the synchroniser has locked and NSW hits have followed, as the Costas gains of the m-sequence project)"""
    ta, tb = loop_gains(timing_bw); al, be = loop_gains(loop_bw)
    tqa, tqb = loop_gains(timing_bw if timing_bw_acq is None else timing_bw_acq)
    return dict(TA=int(round(ta * 2 ** Q.F_T)), TB=int(round(tb * 2 ** Q.F_T)), MU=int(mu), G0=int(g0), MAXR=int(round(max_rate * NF * 2 ** 16)),
                TAA=int(round(tqa * 2 ** Q.F_T)), TBA=int(round(tqb * 2 ** Q.F_T)), MUA=int(mu if mu_acq is None else mu_acq), ACQ=int(acq_symbols), NSW=int(nsw),
                PREF=(R_UNIT * R_UNIT) >> 8, CA=int(round(al * 2 ** 40 / (2 * np.pi * KE))), CB=int(round(be * 2 ** 40 / (2 * np.pi * KE))))


def front16(xi, xq, regs=None, max_symbols=None, acq_sched=None):
    """acq_sched: [(n, bool), ...] sorted: from the symbol n on the acquisition mode is on/off (the RTL's acq_auto flag); on top of it the first ACQ symbols are always acquisition"""
    R = regs16() if regs is None else regs
    sched = list(acq_sched or []); si_ = 0; auto = False
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
        while si_ < len(sched) and sched[si_][0] <= n: auto = sched[si_][1]; si_ += 1
        acq = n < R["ACQ"] or auto
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


def engine16(mi, mq, sy, regs=None, word_mode="aided", pilot_weight=3, trace=False):
    """The PLL over the symbols (the front end's mi2, mq2) with the events of the synchroniser `sy` (qam_zc_fixed.sync). pilot_weight: 1, 3 or 5 -> the pilot error is 3 pw zq / 64"""
    R = regs16() if regs is None else regs
    CA, CB = R["CA"], R["CB"]
    mi = np.asarray(mi, dtype=np.int64); mq = np.asarray(mq, dtype=np.int64); L = len(mi)
    cos_l, sin_l = Z.COS_L, Z.SIN_L
    pmul = 3 * pilot_weight
    ref_idx = F.prbs15_indices()
    res = Result(); res.frames = res.locks = 0; res.sym_err = res.sym_cnt = res.bit_err = res.bad_frames = 0
    res.frame_errs = []; res.evm = []; res.evm_sums = []; res.lock_w = []; res.out = []; res.late = 0
    res.trace = []
    ev = sy.events; ep = 0
    run = False; wait = False; theta = 0; omega = 0; pos = 0
    lock_e = lock_w = lock_th = 0
    fr_on = False; fr_err = fr_n = 0; fr_biterr = 0; e2 = r2 = 0
    for j in range(0, L - D_DELAY):
        n = j + D_DELAY
        while ep < len(ev) and ev[ep]["known"] + 2 <= n:
            f = ev[ep]; ep += 1
            if f["kind"] == "lock":
                run, wait = True, True; lock_e, lock_w, lock_th = f["e"], f["w"], f["th0"]; res.locks += 1; res.lock_w.append(f["w"]); fr_on = False
            elif f["kind"] == "frame":
                if run and not wait: pos = 70 + (j - f["e"])
            else:
                run = False; wait = False; fr_on = False
        if not run: continue
        if wait:
            if j != lock_e + 1: continue
            theta, omega, pos, wait = lock_th, lock_w, 71, False
        # label
        if pos >= 71:
            o = pos - 71; b, r_ = divmod(o, F.BLK)
            kind = 2 if r_ == F.BLK - 1 else 1; arg = b if kind == 2 else b * F.N_DATA + r_
        elif word_mode == "aided":
            kind = 3; arg = (F.N_ZC - 8 + pos) if pos < 8 else pos - 8                    # CP = ZC[55..62], word = ZC[0..62]
        else:
            kind = 0; arg = 0
        idx = (theta >> 22) & 1023; c_, s_ = int(cos_l[idx]), int(sin_l[idx])
        zi = (int(mi[j]) * c_ + int(mq[j]) * s_) >> 15; zq = (int(mq[j]) * c_ - int(mi[j]) * s_) >> 15
        e = 0
        if pos == 71:
            fr_on = True; fr_err = fr_n = fr_biterr = 0; e2 = r2 = 0                       # the payload of a frame starts
        if kind == 1:
            si, sq = _level(zi), _level(zq)
            e = (zq * si - zi * sq + 32) >> 6
            ix = 4 * F.LEVEL_IDX[si] + F.LEVEL_IDX[sq]; rix = int(ref_idx[arg])
            fr_err += int(ix != rix); fr_biterr += bin(ix ^ rix).count("1"); fr_n += 1
            e2 += (zi - si * LV) ** 2 + (zq - sq * LV) ** 2; r2 += (si * si + sq * sq) * LV * LV
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
        if trace: res.trace.append((j, pos, kind, zi, zq, e, omega, theta))
        if pos == F.FRAME - 1:
            if fr_on and fr_n == F.N_PAY:
                res.frames += 1; res.sym_err += fr_err; res.sym_cnt += F.N_PAY; res.bit_err += fr_biterr; res.frame_errs.append(fr_err)
                res.bad_frames += int(5 * fr_err > F.N_PAY)                                # more than 20 % of the symbols wrong
                res.evm_sums.append((e2, r2)); res.evm.append(10 * np.log10(max(e2, 1) / max(r2, 1)))
            fr_on = False; pos = 0
        else:
            pos += 1
    return res


def acq_schedule(events, nsw):
    """The acquisition flag of the RTL (acq_auto) as a schedule [(n, on)]: on from the start (when NSW > 0); a lock event starts counting the hits (frame events without a miss) applied after it, NSW of them switch the
    acquisition mode off, a lost event switches it on again. An event with decision index `known` is applied at the engine step known + 2 and acts on the front end from the next symbol on (known + 3)."""
    if nsw == 0: return []
    sched = [(0, True)]; on = True; hits = 0
    for e in sorted(events, key=lambda x: x["known"]):
        t = e["known"] + 3
        if e["kind"] == "lock": hits = 0
        elif e["kind"] == "frame":
            if not e["miss"]:
                hits += 1
                if on and hits >= nsw: on = False; sched.append((t, False))
        else:
            hits = 0
            if not on: on = True; sched.append((t, True))
    return sched


def receive16(xi, xq, regs=None, iterations=8, fll=None, fll_sched=None, **kw):
    """ADC counts -> front end -> synchroniser -> engine. The acquisition mode follows the synchroniser (acq_schedule): the front end and the synchroniser are run again until the schedule no longer changes (causality makes the
    prefix of the result final at every pass)."""
    R = regs16() if regs is None else regs
    if fll is not None:                                                           # (GI, GP[, F0]) register values of the band-edge FLL in front of the front end
        f = FL.fll_stage(xi, xq, fll[0], fll[1], F0=(fll[2] if len(fll) > 2 else 0), sched=fll_sched); xi, xq = f["yi"], f["yq"]
    sched = [(0, True)] if R.get("NSW", 0) else []
    for _ in range(iterations):
        fe = front16(xi, xq, R, acq_sched=sched)
        sy = Z.sync(fe["mi2"], fe["mq2"])
        new = acq_schedule(sy.events, R.get("NSW", 0))
        if new == sched: break
        sched = new
    fe["acq_sched"] = sched
    return fe, sy, engine16(fe["mi2"], fe["mq2"], sy, regs, **kw)
