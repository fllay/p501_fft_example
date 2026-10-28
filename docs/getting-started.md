# Getting started

From an empty SD card to a decoded OFDM frame in about half an hour, without Vivado.

## What you need

| | |
|---|---|
| **Board** | PZSDR P501 (Zynq UltraScale+ ZU5EV, AD9361) with its antennas, connected to your PC by Ethernet |
| **SD card** | 16 GB or more |
| **PC** | any Linux, macOS or Windows machine with `ssh`/`scp` and a browser |
| **To build overlays yourself** (optional) | Linux with Vivado 2024.1 (about 15 minutes per overlay, one build at a time) |
| **A reference radio** (optional, for tutorials 4 to 6) | USRP B210 and GNU Radio 3.10 with UHD |

## 1. Flash the PYNQ image

Download `P501-3.1.2.img.xz` from the [release](https://github.com/fllay/p501-pynq/releases/tag/v3.1.2-p501) and flash it with balenaEtcher, or see [the SD card image](images.md) for the command line and for the default passwords you should change.

Boot the board and open Jupyter (`http://<board address>:9090`) or log in with `ssh xilinx@<board address>`.

## 2. Get the repository

```bash
git clone https://github.com/fllay/p501_fft_example.git
cd p501_fft_example
```

## 3. Copy what the board needs

The notebooks and scripts look for their files in these folders of the board (`BOARD` is the board's address):

```bash
ssh xilinx@BOARD 'mkdir -p /home/xilinx/jupyter_notebooks/p501_fft_dds /home/xilinx/jupyter_notebooks/p501_ofdm'
scp notebook/p501_radio.py notebook/p501_dds.py xilinx@BOARD:/home/xilinx/jupyter_notebooks/p501_fft_dds/
scp overlays/p501_ofdm_trx_sc.bit overlays/p501_ofdm_trx_sc.hwh overlays/p501_ofdm_trx_sts.bit overlays/p501_ofdm_trx_sts.hwh \
    notebook/p501_ofdm_rx.py notebook/p501_ofdm_tx.py notebook/P501_OFDM_Live.ipynb notebook/P501_OFDM_STS_Live.ipynb \
    xilinx@BOARD:/home/xilinx/jupyter_notebooks/p501_ofdm/
```

!!! note "Other overlays"
    The overlays of tutorials 1 to 5 are not prebuilt: build them with `create_project.tcl` (below) and copy the `.bit` and `.hwh` the same way, together with the driver and the notebook of the tutorial.

## 4. First test: the digital loopback (nothing is radiated)

Open `P501_OFDM_Live.ipynb` in Jupyter and run the *Configuration* cell and the next one, then the self-test cell: the FPGA transmitter sends frames into the receiver **inside the AD9361**, and every check should print `PASS`: no frame without a transmitter, every frame found (about 2000 per 2 s), no symbol error in 2 million symbols, EVM better than -40 dB.

The same test as a script (as root on the board):

```bash
scp tutorial/ofdm/p501_ofdm_txtest.py xilinx@BOARD:/tmp/
ssh xilinx@BOARD "echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh; python3 /tmp/p501_ofdm_txtest.py 0.8,0.2,0.4'"
```

Use `OFDM_VARIANT=sts` in front of `python3` for the STS overlay.

## 5. Over the air

!!! warning "This radiates"
    Start with a **large TX attenuation** and step down (the script `tutorial/ofdm/p501_ofdm_txair.py` starts at 40 dB and goes to 20 dB). Antennas a few centimetres apart, or a cable with an attenuator.

**Read the level at the ADC first.** At the same attenuation it changed by up to 14 dB between runs (every start of the AD9361 is different), and the error rate follows it: below about 100 counts the link is not clean, below 25 the detector does not find the frames. See [tutorial 6, C.8](../tutorial/TUTORIAL_OFDM.md).

With a B210 as the reference radio, use the GNU Radio flowgraphs of [OFDM in GNU Radio](../tutorial/ofdm/GRC_OFDM.md):

```bash
source tools/gnuradio_env.sh          # GNU Radio 3.10 / UHD 4.8 from radioconda
python3 tutorial/ofdm/ofdm_b210_frame_rx_sts_pilot.py     # or open the .grc in gnuradio-companion
```

## 6. Build an overlay yourself

Requirements: Vivado 2024.1 and the packaged ADI HDL library (`library/` of the [pzsdr-p501](https://github.com/fllay/puzi501iio) repository; the script looks for it at `../pzsdr-p501/hdl/library`, otherwise pass `LIB=`).

```bash
vivado -mode batch -source create_project.tcl -tclargs FFT=0 OFDMRXSC=1 OFDMTXSC=1 RUN=bit JOBS=6
python3 tools/fix_hwh.py build/overlay/p501_ofdm_trx_sc.hwh
```

The options of every overlay are in [the overlays at a glance](overlays.md). Two practical rules:

* **One build at a time.** Two parallel Vivado builds used all 31 GB of RAM of the build machine and the system killed other programs.
* Run `tools/fix_hwh.py` on the `.hwh` before PYNQ loads it.

## Where to go next

* [Tutorial 1: an FFT on the ADC data](../tutorial/TUTORIAL.md) if you are new to the board;
* [Tutorial 6: OFDM](../tutorial/TUTORIAL_OFDM.md) for the newest work (the transmitter and the receiver in the FPGA);
* [The design flow](../tutorial/DESIGN_FLOW.md) to reuse the method for your own modulation.
