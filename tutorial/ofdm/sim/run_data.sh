#!/bin/bash
# xsim of ofdm_fft.v + ofdm_data.v against the integer model (equaliser, pilots, slope, averaging, correction, slicer, checker).   ./run_data.sh
set -e
cd "$(dirname "$0")"
python3 gen_data_vectors.py
NC=$(( $(wc -l < data_in.hex) / (56 + 44 * 64) ))
xvlog -sv ../../../rtl/ofdm_fft.v ../../../rtl/ofdm_cordic.v ../../../rtl/ofdm_div.v ../../../rtl/ofdm_data.v ../../../rtl/qpsk_rx_trig.v tb_ofdm_data.v > xvlog_data.log 2>&1 || { grep -i error xvlog_data.log; exit 1; }
xelab -debug off tb_ofdm_data -s simdata > xelab_data.log 2>&1
xsim simdata -runall -testplusarg nc=$NC > xsim_data.log 2>&1
grep -E "^(cases|case )" xsim_data.log
python3 compare_data.py
