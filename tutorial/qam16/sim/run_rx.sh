#!/bin/bash
# xsim of tb_qam16_rx.v with one of the test vectors and the comparison with the integer model.   ./run_rx.sh [a|b]
set -e
cd "$(dirname "$0")"
S=${1:-a}
N=$(wc -l < rx_$S.hex)
xvlog -sv ../../../rtl/qam16_rx.v ../../../rtl/qam_zc_sync.v ../../../rtl/qam_zc_rom.v ../../../rtl/qpsk_rx_rom.v ../../../rtl/qpsk_rx_trig.v tb_qam16_rx.v > xvlog_rx.log
xelab -debug off tb -s simrx > xelab_rx.log
xsim simrx -runall -testplusarg hex=rx_$S.hex -testplusarg ns=$N > xsim_rx.log
python3 compare_rx.py $S
