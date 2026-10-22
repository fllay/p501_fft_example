"""Python side of the FPGA QPSK transmitter (rtl/qpsk_tx.v, chapter 4c): the register block is the one of the DDS, so P501Dds does the work.

    from p501_qpsk import P501QpskTx
    tx = P501QpskTx(ol.qpsk_regs, fs_hz=3_840_000)
    tx.start(amp=0.5)       # the PRBS-15 QPSK signal starts from its first bit, 960 ksym/s, 1.92 Mbit/s
    tx.stop()               # zeros to the DAC
"""
from p501_dds import P501Dds


class P501QpskTx(P501Dds):
    def start(self, amp=0.5, timeout_s=1.0):
        self.set(amp=amp, enable=True, timeout_s=timeout_s)

    def stop(self, timeout_s=1.0):
        self.off(timeout_s=timeout_s)


class P501QpskTxFrames(P501QpskTx):
    """The transmitter of the overlays with the frame synchroniser (rtl/qpsk_tx_fr.v, chapter 4e): besides the continuous PRBS-15 it sends FRAMES: a 64-symbol m-sequence preamble followed by `payload`
    symbols of PRBS-15 (restarted in every frame), repeated back to back. The configuration is the FTW register of the register block (bit 31 frames, bits 15:0 the payload symbols); it takes effect
    when the transmitter is started.

        tx = P501QpskTxFrames(ol.qpsk_regs, 3_840_000)
        tx.start_frames(payload=960, amp=0.5)      # frames of 1024 symbols (1.067 ms); the receiver of p501_qpsk_trx_sync: rx.configure_sync(fl=1024, pl=960)
        tx.start(amp=0.5)                          # the continuous PRBS-15 as before
    """
    def start_frames(self, payload=960, amp=0.5, timeout_s=1.0):
        if payload % 4 or not 4 <= payload <= 0xFFFF:
            raise ValueError("payload: a multiple of 4 symbols, 4 .. 65532")
        self.off(timeout_s=timeout_s)
        self.ip.write(0x08, (1 << 31) | int(payload))
        self.set(amp=amp, enable=True, timeout_s=timeout_s)

    def start(self, amp=0.5, timeout_s=1.0):
        self.off(timeout_s=timeout_s)
        self.ip.write(0x08, 0)
        self.set(amp=amp, enable=True, timeout_s=timeout_s)
