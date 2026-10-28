# Built overlays

Bitstreams and hardware handoff files (`.hwh`, already processed with `tools/fix_hwh.py`) for the board, so that a clone can run the OFDM transmitter + receiver without building (about 15 minutes of Vivado each, one build at a time: two in parallel ran the machine out of memory).

| overlay | source | create_project.tcl options | receiver ID |
|---|---|---|---|
| `p501_ofdm_trx_sc` | `rtl/ofdm_tx.v` (STS = 0) + `rtl/ofdm_rx.v` (STS = 0) | `FFT=0 OFDMRXSC=1 OFDMTXSC=1` | 0xDD520007 |
| `p501_ofdm_trx_sts` | `rtl/ofdm_tx.v` (STS = 1) + `rtl/ofdm_rx.v` (STS = 1) | `FFT=0 OFDMRXSTS=1 OFDMTXSTS=1` | 0xDD520008 |

Built 2026-10-28 from the RTL of the commit that adds them; timing met (WNS +0.417 ns). Copy the `.bit` and `.hwh` of the overlay and `notebook/p501_ofdm_tx.py`, `notebook/p501_ofdm_rx.py` to `/home/xilinx/jupyter_notebooks/p501_ofdm/` on the board (tutorial 6, C.8).
