"""Python driver for the DDS register block (rtl/dds_regs.v) of the P501 DDS overlay.

    from p501_dds import P501Dds
    dds = P501Dds(ol.dds_regs, fs_hz=3_840_000)    # fs = the DAC sample rate (TX sample rate of the AD9361)
    dds.set(freq_hz=1e6, amp=0.5)                  # complex tone cos + j sin at +1 MHz, half scale
    dds.set(freq_hz=-250e3)                        # negative frequency: the tone moves to the other side of the LO
    dds.off()                                      # DAC gets zeros

Register map (byte offsets):  0x00 ID, 0x04 CONTROL (bit0 enable), 0x08 FTW, 0x0C AMP (Q15), 0x10 STATUS (bit0 applied),
0x14 COMMIT. `set()` writes the parameter registers, then COMMIT, and waits until the sample-clock side took them over
(STATUS bit0): so the three values change at the same sample, and the call returns only when the new tone is on its way.
"""
import time

REG_ID, REG_CONTROL, REG_FTW, REG_AMP, REG_STATUS, REG_COMMIT = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14
DDS_ID = 0xDD500001
AMP_FULL = 0x7FFF


class P501Dds:
    def __init__(self, ip, fs_hz):
        self.ip = ip
        self.fs = float(fs_hz)
        if self.ip.read(REG_ID) != DDS_ID:
            raise RuntimeError(f"not the DDS register block (ID 0x{self.ip.read(REG_ID):08X}, expected 0x{DDS_ID:08X})")

    # --- conversions ---------------------------------------------------------------------------
    def freq_to_ftw(self, freq_hz):
        """Frequency word: f = FTW / 2^32 * fs, two's complement for negative frequencies."""
        if abs(freq_hz) >= self.fs / 2:
            raise ValueError(f"|f| must be below fs/2 = {self.fs / 2:.0f} Hz")
        return int(round(freq_hz / self.fs * 2**32)) & 0xFFFFFFFF

    def ftw_to_freq(self, ftw):
        if ftw >= 2**31:
            ftw -= 2**32
        return ftw / 2**32 * self.fs

    # --- state ----------------------------------------------------------------------------------
    @property
    def freq_hz(self):
        return self.ftw_to_freq(self.ip.read(REG_FTW))

    @property
    def amp(self):
        return (self.ip.read(REG_AMP) & AMP_FULL) / AMP_FULL

    @property
    def enabled(self):
        return bool(self.ip.read(REG_CONTROL) & 1)

    @property
    def applied(self):
        """True when the last commit has been taken over by the sample clock (needs the AD9361 clock running)."""
        return bool(self.ip.read(REG_STATUS) & 1)

    # --- control --------------------------------------------------------------------------------
    def set(self, freq_hz=None, amp=None, enable=None, timeout_s=1.0):
        """Change any of frequency (Hz), amplitude (0..1 of full scale) and enable; unspecified values stay as they are."""
        if freq_hz is not None:
            self.ip.write(REG_FTW, self.freq_to_ftw(freq_hz))
        if amp is not None:
            if not 0.0 <= amp <= 1.0:
                raise ValueError("amp must be between 0 and 1")
            self.ip.write(REG_AMP, int(round(amp * AMP_FULL)))
        if enable is not None:
            self.ip.write(REG_CONTROL, 1 if enable else 0)
        elif freq_hz is not None or amp is not None:
            if not self.ip.read(REG_CONTROL) & 1:
                self.ip.write(REG_CONTROL, 1)      # setting a tone switches the output on
        self.ip.write(REG_COMMIT, 1)
        t0 = time.time()
        while not self.applied:
            if time.time() - t0 > timeout_s:
                raise TimeoutError("DDS update not taken over: is the AD9361 clock (l_clk) running? "
                                   "Run the bring-up first (axi_ad9361_core_enable).")
            time.sleep(0.001)

    def off(self, timeout_s=1.0):
        self.set(enable=False, timeout_s=timeout_s)
