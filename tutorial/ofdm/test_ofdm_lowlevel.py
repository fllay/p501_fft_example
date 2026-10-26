#!/usr/bin/env python3
"""The S&C and the STS detector of the integer receiver at low ADC levels (Es/N0 26 dB, 300 frames per point): python3 test_ofdm_lowlevel.py"""
import sys, numpy as np
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from multiprocessing import Pool
import ofdm_model as Fm, ofdm_fixed as X
LEAD=300
def one(a):
    var_name, snr, rms, seed = a; var = X.STS if var_name=="sts" else X.SC; rng=np.random.default_rng(seed)
    x,d=Fm.tx_frame(preamble=var["preamble"]); cfo=rng.uniform(-10e3,10e3); tau=rng.uniform(0,12)
    y=Fm.channel(x,snr,cfo_hz=cfo,tau=tau,ppm=10.0,rng=rng,lead=LEAD); xi,xq=X.to_adc(y,rms); ri=X.receive_fixed(xi,xq,var=var)
    if ri is None: return None
    sc=X.score(ri); return sc["ser"], ri["s0"]-(LEAD+tau)
if __name__=="__main__":
    pool=Pool(14); print("integer model, 300 frames per point, noise as 26 dB Es/N0 per subcarrier; ADC level = rms counts of the signal; bad = SER > 0.2 or frame missed")
    for snr in (26,):
        for rms in (60,25,16,12,9,6):
            row=[]
            for v in ("sc","sts"):
                res=pool.map(one,[(v,snr,rms,500+i) for i in range(300)],chunksize=5); miss=sum(r is None for r in res); ok=[r for r in res if r is not None]
                bad=miss+sum(r[0]>0.2 for r in ok); good=[r for r in ok if r[0]<=0.2]
                row.append("%s: bad %3d of 300, SER of the good frames %.1e, start err std %.2f"%(v.upper(),bad,np.mean([r[0] for r in good]) if good else 1,np.std([r[1] for r in ok]) if ok else 0))
            print("level %3d counts: %s | %s"%(rms,row[0],row[1]),flush=True)
