"""Python side of the FPGA OFDM receiver with the Schmidl-and-Cox synchroniser (rtl/ofdm_rx.v, overlay p501_ofdm_rx_sc).

    from p501_ofdm_rx import P501OfdmRx
    rx = P501OfdmRx(ol.ofdm_rx)
    rx.start()                          # run, continuous: every frame that the detector finds is decoded
    rx.wait_frames(3)                   # until three complete frames have been decoded
    rx.stats()                          # frames, symbol / bit errors against the PRBS-15 payload, EVM, SNR, carrier offset, gain ...
    z = rx.capture()                    # the first 1024 soft symbols of a frame (complex, unit RMS 1.0)
    k, h = rx.channel()                 # the channel estimate H of the 28 used subcarriers (k = -14 .. -1, 1 .. 14)

Frame: PLAN_OFDM.md section 12 (S&C symbol, two QPSK training symbols, 44 data symbols of 24 16-QAM subcarriers + 4 QPSK pilots, 1 ms). The numbers behind the registers: tutorial/ofdm/ofdm_fixed.py
(unit RMS 12953 counts, 16-QAM levels +-4096 / +-12288, thresholds 0 / +-8192)."""
import time
import numpy as np

REG = dict(ID=0x00, CTRL=0x04, THR=0x08, EMIN=0x0C, TARGET=0x10, GAIN_OVR=0x14, STATUS=0x20, FRAMES=0x24, FOUND=0x28, REJ=0x2C, BAD=0x30, TOT_SYM=0x34, TOT_ERR=0x38, TOT_BIT=0x3C,
           SYM_CNT=0x40, SYM_ERR=0x44, BIT_ERR=0x48, EVM_ERR_LO=0x4C, EVM_ERR_HI=0x50, EVM_REF_LO=0x54, EVM_REF_HI=0x58, S0=0x60, W_C=0x64, W_F=0x68, W=0x6C, GAIN=0x70,
           NOISE_LO=0x74, NOISE_HI=0x78, WR_COUNT=0x7C, LATE=0x80)
CAPTURE, HMEM = 0x1000, 0x2000
FS, R_UNIT, LV = 3.84e6, 12953, 4096
EXPECTED_ID = 0xDD520007
USED = np.array([k for k in range(-14, 15) if k != 0])


def _signed(v, bits=32):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


class P501OfdmRx:
    def __init__(self, ip):
        self.ip = ip
        if self.ip.read(REG["ID"]) != EXPECTED_ID:
            raise RuntimeError("not the OFDM receiver (ID 0x%08X)" % self.ip.read(REG["ID"]))

    def r(self, name):
        return self.ip.read(REG[name])

    def configure(self, thr=166, emin=4, target=400, gain_override=0):
        """detector threshold (in 1/256 of the metric: 166 = 0.65), minimum window energy, the rms of the samples after the gain (counts), a fixed gain (Q8; 0 = from the detector)"""
        self.ip.write(REG["THR"], int(thr)); self.ip.write(REG["EMIN"], int(emin)); self.ip.write(REG["TARGET"], int(target)); self.ip.write(REG["GAIN_OVR"], int(gain_override))

    def start(self, continuous=True, capture=True):
        """run (bit 0), continuous (bit 2: re-arm after every frame), capture armed for the next frame (bit 1)"""
        self.ip.write(REG["CTRL"], 0)
        self.ip.write(REG["CTRL"], 1 | (4 if continuous else 0) | (2 if capture else 0))

    def stop(self):
        self.ip.write(REG["CTRL"], 0)

    def arm_capture(self):
        c = self.ip.read(REG["CTRL"]); self.ip.write(REG["CTRL"], c & ~2); self.ip.write(REG["CTRL"], c | 2)

    def wait_frames(self, n=1, timeout_s=2.0):
        f0 = self.r("FRAMES"); t0 = time.time()
        while self.r("FRAMES") - f0 < n:
            if time.time() - t0 > timeout_s: return False
            time.sleep(0.002)
        return True

    def channel(self):
        """(k, H): the channel estimate of the last frame, complex, in the units of the FFT of the receiver (the transmitted subcarriers have unit power: |H| about 4000 to 5000 at 400 counts rms)"""
        w = np.array([self.ip.read(HMEM + 4 * i) for i in range(28)], dtype=np.uint32)
        hr = (w & 0xFFFF).astype(np.uint16).view(np.int16).astype(float); hi = (w >> 16).astype(np.uint16).view(np.int16).astype(float)
        return USED, hr + 1j * hi

    def stats(self):
        r = self.r; g = lambda lo, hi: r(lo) + (r(hi) << 32)
        sc, se, be = r("SYM_CNT"), r("SYM_ERR"), r("BIT_ERR"); ee, er = g("EVM_ERR_LO", "EVM_ERR_HI"), g("EVM_REF_LO", "EVM_REF_HI")
        noise = g("NOISE_LO", "NOISE_HI"); k, h = self.channel(); sig2 = noise / (2 * 28.0) if noise else float("nan")
        w = _signed(r("W")); st = r("STATUS")
        return dict(running=bool(st & 1), capture_done=bool(st & 2), found_pending=bool(st & 4), busy=bool(st & 8), late=bool(st & 16), ovf=bool(st & 32), fft_ovf=bool(st & 64), overrun=bool(st & 128),
                    frames=r("FRAMES"), found=r("FOUND"), rejected=r("REJ"), bad_frames=r("BAD"), tot_sym=r("TOT_SYM"), tot_err=r("TOT_ERR"), tot_bit=r("TOT_BIT"),
                    sym_cnt=sc, sym_err=se, bit_err=be, ser=(se / sc if sc else float("nan")), ber=(be / (4 * sc) if sc else float("nan")),
                    evm_db=(10 * np.log10(ee / er) if er and ee else float("nan")), snr_db=(10 * np.log10(np.mean(np.abs(h) ** 2) / sig2) if noise and sig2 > 0 else float("nan")),
                    s0=r("S0"), carrier_hz=w / 2 ** 32 * FS, carrier_coarse_hz=_signed(r("W_C")) / 2 ** 32 * FS, gain=r("GAIN") / 256.0, level_counts=(400 * 256.0 / max(r("GAIN"), 1)), wr_count=r("WR_COUNT"), late_count=r("LATE"))

    def capture(self):
        """the first 1024 corrected data symbols of the last frame captured (complex, unit RMS 1.0): arm with start(capture=True) or arm_capture(), wait for the next frame"""
        w = np.array([self.ip.read(CAPTURE + 4 * i) for i in range(1024)], dtype=np.uint32)
        zi = (w & 0xFFFF).astype(np.uint16).view(np.int16).astype(float); zq = (w >> 16).astype(np.uint16).view(np.int16).astype(float)
        return (zi + 1j * zq) / R_UNIT
