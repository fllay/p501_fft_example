# Built overlays and the SD card image

## The PYNQ SD card image

The PYNQ 3.1.2 image for the P501 (Ubuntu 22.04, aarch64) is a release of its own repository:

**[fllay/p501-pynq, release v3.1.2-p501](https://github.com/fllay/p501-pynq/releases/tag/v3.1.2-p501)**

| file | what |
|---|---|
| `P501-3.1.2.img.xz` | the image, compressed (1.34 GiB; 9.7 GB when decompressed) |
| `P501-3.1.2.img.xz.sha256` | its SHA-256 |

Flash it with balenaEtcher (it opens the `.xz` directly) or:

```bash
sha256sum -c P501-3.1.2.img.xz.sha256
xz -dc P501-3.1.2.img.xz | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
```

!!! danger "Change the defaults"
    The image uses the standard PYNQ credentials: user `xilinx` and user `root` with the password `xilinx`, and Jupyter (port 9090) with the password `xilinx`. Anyone on the same network can log in. Change them (`passwd`, `jupyter notebook password`) before the board is on a network you do not control. The SSH host keys are the same on every board flashed from the image; make your own with `sudo rm /etc/ssh/ssh_host_* && sudo ssh-keygen -A && sudo systemctl restart ssh`.

The image was built before the OFDM overlays and does not contain them.

## The built overlays of this repository

The folder [`overlays/`](https://github.com/fllay/p501_fft_example/tree/main/overlays) holds the finished OFDM transmitter + receiver overlays (`.bit` and the already fixed `.hwh`), so that a clone runs them without Vivado:

| overlay | transmitter | receiver | `create_project.tcl` options |
|---|---|---|---|
| `p501_ofdm_trx_sc` | Schmidl-and-Cox frame, in the FPGA | ID `0xDD520007` | `FFT=0 OFDMRXSC=1 OFDMTXSC=1` |
| `p501_ofdm_trx_sts` | 128-sample STS frame, in the FPGA | ID `0xDD520008` | `FFT=0 OFDMRXSTS=1 OFDMTXSTS=1` |

Timing is met on both (worst setup slack +0.417 ns). The other overlays are built from source: see [Getting started](getting-started.md).
