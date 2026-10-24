#!/bin/bash
# xsim of ofdm_fft.v + ofdm_chan.v against the integer model (the channel estimate, the noise sum and the weights).   ./run_chan.sh
set -e
cd "$(dirname "$0")"
python3 gen_chan_vectors.py
NC=$(( $(wc -l < chan_in.hex) / 128 ))
xvlog -sv ../../../rtl/ofdm_fft.v ../../../rtl/ofdm_chan.v tb_ofdm_chan.v > xvlog_chan.log 2>&1 || { tail xvlog_chan.log; exit 1; }
xelab -debug off tb_ofdm_chan -s simchan > xelab_chan.log 2>&1
xsim simchan -runall -testplusarg nc=$NC > xsim_chan.log 2>&1
grep -E "^cases" xsim_chan.log
python3 compare_chan.py
