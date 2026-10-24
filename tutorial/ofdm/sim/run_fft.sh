#!/bin/bash
# xsim of ofdm_fft.v against ofdm_fixed.fft64.   ./run_fft.sh
set -e
cd "$(dirname "$0")"
python3 gen_fft_vectors.py
NT=$(( $(wc -l < fft_in.hex) / 64 ))
xvlog -sv ../../../rtl/ofdm_fft.v tb_ofdm_fft.v > xvlog_fft.log 2>&1 || { tail xvlog_fft.log; exit 1; }
xelab -debug off tb_ofdm_fft -s simfft > xelab_fft.log 2>&1
xsim simfft -runall -testplusarg nt=$NT > xsim_fft.log 2>&1
grep -E "^transforms" xsim_fft.log
python3 compare_fft.py
