#!/usr/bin/env python3
"""Lab for the OFDM synchronisation study (PLAN_OFDM_SYNC.md): frames with a SHORT field (the STS of period 16, the Schmidl-and-Cox symbol of period 32, or none) and a LONG field (a guard interval of 32 samples and L training symbols of 64,
periodic with 64 over the whole field), a channel, and a receiver whose detection, timing, carrier and channel estimates can be chosen method by method.

    Cfg(short="sts", short_len=128, L=2)            frame A of the plan (tutorial 6, STS)
    Cfg(short="sc", L=2)                            frame B (the S&C symbol, then the long field)
    Cfg(short="sts", short_len=128, L=8)            a long field of 8 symbols
    Cfg(short="none", L=4)                          no short field: the long field is detected itself (lag 64)

    r = receive(y, cfg, fine=["multi"], timing="xcorr")        -> dict(Z, f, f_coarse, t0, ...) or None
    python3 ofdm_sync_lab.py                        checks that frame A reproduces ofdm_model.receive

Floating point (stage 1 of the design flow): no quantisation. Everything not listed here (the symbol set, the pilots, the training values) is the one of tutorial 6 (ofdm_model.py)."""
import os, sys
from dataclasses import dataclass
from functools import lru_cache
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ofdm")); sys.path.insert(0, os.path.join(HERE, "..", "qam16"))
import ofdm_model as Fm

N, CP, FS, BACK, L_SYM, SYM = Fm.N, Fm.CP, Fm.FS, Fm.BACK, Fm.L_SYM, Fm.SYM
GI2 = 32
T_SYM = Fm.to_time((Fm.USED, Fm.TRAIN))                  # the long training symbol, 64 samples
STS64 = Fm.to_time((Fm.STS_K, Fm.STS_V))                 # every 4th subcarrier: period 16
SC64 = Fm.to_time((Fm.SC_K, Fm.SC_V))                    # even subcarriers: two equal halves
KB_USED = Fm.bin_of(Fm.USED)
PILOTS_802 = (-11, -4, 4, 11)                            # the pilots of tutorial 6
PILOT_SETS = {2: (-7, 7), 4: PILOTS_802, 6: (-12, -8, -4, 4, 8, 12), 8: (-12, -9, -6, -3, 3, 6, 9, 12)}


@lru_cache(maxsize=None)
def layout(pilots):
    """the subcarriers of a frame with the given pilots: data subcarriers (the rest of the 28 used), their bins, the 16-QAM symbols of the PRBS-15 (L_SYM x n data), the pilot values x the polarity of every symbol"""
    pil = np.array(pilots); data = np.array([k for k in Fm.USED if k not in pilots]); nd = len(data)
    d = Fm.qam_syms(Fm.F.prbs15_bits(L_SYM * 4 * nd)).reshape(L_SYM, nd)
    pv = np.resize(Fm.PIL_V, len(pil))[None, :] * Fm.POL[:, None]
    return dict(pil=pil, data=data, kb_pil=Fm.bin_of(pil), kb_data=Fm.bin_of(data), d=d, pilref=pv)


@dataclass
class Cfg:
    short: str = "sts"            # "sts" | "sc" | "none"
    short_len: int = 128          # samples of the STS field (a multiple of 16)
    L: int = 2                    # long training symbols (after a guard interval of 32 samples)
    idle: int = 32
    pilots: tuple = PILOTS_802    # the pilot subcarriers (the others of the 28 used carry 16-QAM data)

    @property
    def len_short(self): return {"sts": self.short_len, "sc": 80, "none": 0}[self.short]
    @property
    def len_long(self): return GI2 + N * self.L
    @property
    def preamble(self): return self.len_short + self.len_long
    @property
    def frame_len(self): return self.preamble + L_SYM * SYM + self.idle
    @property
    def overhead(self): return (self.preamble + self.idle) / self.frame_len
    @property
    def n_data(self): return 28 - len(self.pilots)
    @property
    def bits_per_frame(self): return L_SYM * self.n_data * 4
    @property
    def name(self): return "%s%s L%d" % (self.short, str(self.short_len) if self.short == "sts" else "", self.L)


def build(cfg):
    """-> x (the frame), d (the data symbols sent, L_SYM x 24)"""
    if cfg.short == "sts": sh = np.tile(STS64, 1 + cfg.short_len // 64)[:cfg.short_len]
    elif cfg.short == "sc": sh = np.concatenate([SC64[-CP:], SC64])
    else: sh = np.zeros(0, complex)
    lg = np.concatenate([T_SYM[-GI2:]] + [T_SYM] * cfg.L)
    syms = []; ly = layout(tuple(cfg.pilots))
    for l in range(L_SYM):
        X = np.zeros(N, complex); X[ly["kb_data"]] = ly["d"][l]; X[ly["kb_pil"]] = ly["pilref"][l]
        x = np.fft.ifft(X) * np.sqrt(N); syms.append(np.concatenate([x[-CP:], x]))
    return np.concatenate([sh, lg] + syms + [np.zeros(cfg.idle, complex)]), ly["d"]


def detect(y, cfg, thr=0.5):
    """delay-and-correlate on the short field (lag 16 / 32) or, without one, on the long field (lag 64): -> (start of the field, coarse carrier in Hz, peak of the metric) or None"""
    if cfg.short == "sts": lag, Lsf = 16, cfg.short_len; win = min(48, Lsf - 2 * lag); frac = 0.8
    elif cfg.short == "sc": lag, Lsf, win, frac = 32, 80, 32, 0.9
    else: lag, Lsf, win, frac = 64, cfg.len_long, 64, 0.8
    if Lsf - win - lag < 0: return None
    M, S = Fm.timing_metric(y, lag, win)
    idx = np.nonzero(M > thr)[0]
    if len(idx) == 0: return None
    n0 = idx[0]; seg = M[n0:n0 + Lsf + 12]; pk = seg.max(); pl = np.nonzero(seg >= frac * pk)[0]
    ic = n0 + 0.5 * (pl[0] + pl[-1])
    start = ic - (Lsf - win - lag) / 2                                  # the plateau [s, s + Lsf - win - lag] has its centre here
    f = np.angle(np.sum(S[n0 + pl[0]:n0 + pl[-1] + 1])) / (2 * np.pi * lag / FS)
    return start, f, pk


def periodic_cfo(z, period, nlags):
    """carrier (Hz) left in a field that repeats every `period` samples: the phase of the correlation at lag period, then 2 x period, ... each lag refined from the estimate of the shorter ones (the error falls with the lag, the
    range does not shrink because the shorter lags unwrap the longer)"""
    f = 0.0
    for m in range(1, nlags + 1):
        lag = period * m
        if lag >= len(z): break
        R = np.sum(z[lag:] * np.conj(z[:-lag]))
        f += np.angle(R * np.exp(-2j * np.pi * f * lag / FS)) / (2 * np.pi * lag / FS)
    return f


def rotate(y, f, ref):
    return y * np.exp(-2j * np.pi * f / FS * (np.arange(len(y)) - ref))


def refine_timing(yc, t_nom, cfg, span=20):
    """the start of the first long symbol by cross-correlation with the known symbol (incoherent sum over the L symbols), searched around the plateau estimate"""
    ts = np.arange(int(round(t_nom)) - span, int(round(t_nom)) + span + 1)
    ts = ts[(ts >= 0) & (ts + N * cfg.L <= len(yc))]
    if len(ts) == 0: return None
    c = [sum(abs(np.vdot(T_SYM, yc[t + N * l:t + N * l + N])) for l in range(cfg.L)) for t in ts]
    return int(ts[int(np.argmax(c))])


def receive(y, cfg, fine=("multi",), timing="plateau", thr=0.5, force_f=None):
    """-> dict or None.
    fine   the fine-carrier methods applied one after the other, each on the result of the one before: 'orig' (lag 64 between the first two long symbols), 'lag1' (lag 64 over the whole long field),
           'multi' (lags 64 .. L x 64), 'short_multi' (lags inside the short field), [] = coarse only
    timing 'plateau' (the centre of the plateau) or 'xcorr' (cross-correlation with the long symbol)
    force_f  the carrier in Hz to use instead of every estimate (to study what a given error costs)"""
    d = detect(y, cfg, thr)
    if d is None: return None
    start, f_c, pk = d
    s_long = start + cfg.len_short
    t0 = s_long + GI2                                                   # the first long symbol
    yc = rotate(y, f_c, start)
    if timing == "xcorr":
        t = refine_timing(yc, t0, cfg)
        if t is None: return None
        t0 = t
    t0 = int(round(t0))
    f = f_c; used = {}
    if t0 - GI2 < 0 or t0 + N * cfg.L + L_SYM * SYM > len(y): return None
    for m in fine:
        yr = rotate(y, f, start)
        if m == "orig":
            if cfg.L < 2: continue
            a, b = yr[t0:t0 + N], yr[t0 + N:t0 + 2 * N]; df = np.angle(np.sum(b * np.conj(a))) / (2 * np.pi * N / FS)
        elif m == "lag1": df = periodic_cfo(yr[t0 - GI2:t0 + N * cfg.L], N, 1)
        elif m == "multi": df = periodic_cfo(yr[t0 - GI2:t0 + N * cfg.L], N, cfg.L)
        elif m == "short_multi":
            if cfg.short == "none": continue
            s = int(round(start)); per, nl = (16, (cfg.short_len - 16) // 16) if cfg.short == "sts" else (32, 2)
            df = periodic_cfo(yr[s:s + cfg.len_short], per, nl)
        else: raise ValueError(m)
        f += df; used[m] = df
    if force_f is not None: f = force_f
    yf = rotate(y, f, t0)
    A = np.array([np.fft.fft(yf[t0 + N * l - BACK:t0 + N * l - BACK + N]) / np.sqrt(N) for l in range(cfg.L)])
    H = np.mean(A[:, KB_USED] * np.conj(Fm.TRAIN)[None, :], axis=0)
    ly = layout(tuple(cfg.pilots))
    Hd = dict(zip(Fm.USED, H)); Hdat = np.array([Hd[k] for k in ly["data"]]); Hpil = np.array([Hd[k] for k in ly["pil"]])
    base = t0 + N * cfg.L
    Z = np.zeros((L_SYM, len(ly["data"])), complex); g = np.zeros(L_SYM, complex)
    for l in range(L_SYM):
        st = base + l * SYM + CP - BACK
        Y = np.fft.fft(yf[st:st + N]) / np.sqrt(N)
        zp = Y[ly["kb_pil"]] / Hpil
        g[l] = np.sum(zp * np.conj(ly["pilref"][l])) / len(ly["pil"])
        Z[l] = Y[ly["kb_data"]] / Hdat / g[l]
    ph = np.unwrap(np.angle(g)); slope = np.polyfit(np.arange(L_SYM), ph, 1)[0]
    return dict(Z=Z, f=f, f_coarse=f_c, start=start, t0=t0, H=H, peak=pk, fine=used, f_pilot_res=slope / (2 * np.pi * SYM / FS))


def run(cfg, snr_db, nfr=100, cfo_range=30e3, fine=("multi",), timing="plateau", rng=None, ferr=None, tau_max=1.0, taps=None, lead=300, **kw):
    """Monte Carlo: nfr frames through the channel (random carrier in +-cfo_range, random fractional delay, random phase, noise at snr_db per subcarrier).
    ferr: the carrier error in Hz that the receiver is made to have (force_f = true carrier + ferr): what an error costs, whatever method makes it.
    -> dict of arrays: ok (frame found), f_err (carrier error, Hz), t_err (start of the first long symbol, samples), evm (dB), ser, f_pilot_res"""
    rng = rng or np.random.default_rng(1)
    x, d = build(cfg)
    out = dict(ok=[], f_err=[], t_err=[], evm=[], ser=[], f_pilot=[], f_coarse_err=[])
    for _ in range(nfr):
        cfo = rng.uniform(-cfo_range, cfo_range); tau = rng.uniform(0, tau_max)
        y = Fm.channel(x, snr_db, cfo_hz=cfo, tau=tau, taps=taps, lead=lead, trail=300, rng=rng)
        r = receive(y, cfg, fine=fine, timing=timing, force_f=None if ferr is None else cfo + ferr, **kw)
        if r is None:
            out["ok"].append(False); continue
        ev, se = Fm.metrics(r["Z"], d)
        out["ok"].append(True); out["f_err"].append(r["f"] - cfo); out["f_coarse_err"].append(r["f_coarse"] - cfo)
        out["t_err"].append(r["t0"] - (lead + tau + cfg.len_short + GI2)); out["evm"].append(ev); out["ser"].append(se); out["f_pilot"].append(r["f_pilot_res"])
    return {k: np.array(v) for k, v in out.items()}


def summary(o):
    ok = o["ok"]; n = len(ok)
    if not ok.any(): return dict(found=0.0, timing_ok=0.0, bad=1.0, f_rms=np.nan, f_coarse_rms=np.nan, t_mean=np.nan, t_std=np.nan, evm=np.nan, ser=np.nan, ser_all=np.nan)
    good = o["ser"] < 0.2
    tok = (o["t_err"] >= -10) & (o["t_err"] <= 6)                      # the window of every symbol stays inside its prefix
    return dict(found=ok.mean(), timing_ok=float(tok.sum() / n), bad=(~good).sum() / n, f_rms=float(np.sqrt(np.mean(o["f_err"] ** 2))), f_coarse_rms=float(np.sqrt(np.mean(o["f_coarse_err"] ** 2))),
                t_mean=float(np.mean(o["t_err"])), t_std=float(np.std(o["t_err"])), evm=float(np.mean(o["evm"][good])) if good.any() else np.nan,
                ser=float(np.mean(o["ser"][good])) if good.any() else np.nan, ser_all=float(np.mean(o["ser"])))


if __name__ == "__main__":
    cfg = Cfg("sts", 128, 2); x, d = build(cfg); print("frame A: %d samples, preamble %d, overhead %.1f %%" % (len(x), cfg.preamble, 100 * cfg.overhead))
    xr, _ = Fm.tx_frame(preamble="sts16"); print("same samples as ofdm_model.tx_frame(sts16): %s" % np.allclose(x, xr))
    rng = np.random.default_rng(3); ev_lab, ev_ref = [], []
    for i in range(60):
        cfo = rng.uniform(-20e3, 20e3); y = Fm.channel(x, 20, cfo_hz=cfo, tau=0.4, lead=300, trail=300, rng=rng)
        r = receive(y, cfg, fine=("orig",))
        ref = Fm.receive(y, sync="sts16", return_all=True)
        if r is not None and ref is not None: ev_lab.append(Fm.metrics(r["Z"], d)[0]); ev_ref.append(Fm.metrics(ref["Z"], d)[0])
    print("EVM at 20 dB, %d frames: lab %.2f dB, ofdm_model.receive %.2f dB" % (len(ev_lab), np.mean(ev_lab), np.mean(ev_ref)))
