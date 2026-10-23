import numpy as np, sys
import tx_block as T, rx_block as R
def run(snr, df_hz, rs=250e3, nfr=60, seed=1, off=137):
    tx = T.blk(seed=seed, fixed_payload=True)
    s = np.concatenate([tx.make_frame() for _ in range(nfr)]).astype(complex)
    rng = np.random.default_rng(5)
    n = np.arange(len(s))
    x = s*np.exp(1j*(2*np.pi*df_hz/rs*n+0.9))*0.37
    nz = 10**(-snr/20)*0.37
    x = x + nz*(rng.standard_normal(len(x))+1j*rng.standard_normal(len(x)))/np.sqrt(2)
    x = np.concatenate([nz*(rng.standard_normal(off)+1j*rng.standard_normal(off))/np.sqrt(2), x])
    rx = R.FrameRx(check_payload=True, seed=seed)
    out=[]
    for i in range(0,len(x),1000): out.append(rx.push(x[i:i+1000]))
    y=np.concatenate(out)
    print("snr %2d df %6.0f Hz: frames %d locks %d SER %.2e cfo_est %.0f Hz evm %.1f dB"%(snr,df_hz,rx.frames,rx.lock_count,rx.sym_err/max(rx.sym_cnt,1),rx.omega/2/np.pi*rs,rx.evm_db))
for snr,df in [(40,0),(30,1500),(25,-1500),(20,1900),(18,800),(15,-800),(12,0),(30,2400)]: run(snr,df)
