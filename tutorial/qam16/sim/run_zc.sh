#!/bin/bash
# xsim of tb_qam_zc_sync.v with one of the test vectors and the comparison with the integer model.   ./run_zc.sh [a|b|c|d]
set -e
cd "$(dirname "$0")"
S=${1:-a}
N=$(wc -l < zc_$S.hex)
xvlog -sv ../../../rtl/qam_zc_sync.v ../../../rtl/qam_zc_rom.v ../../../rtl/qpsk_rx_trig.v tb_qam_zc_sync.v > xvlog_zc.log
xelab -debug off tb -s simzc > xelab_zc.log
xsim simzc -runall -testplusarg hex=zc_$S.hex -testplusarg ns=$N > xsim_zc.log
grep -E "^(peaks|locks|hits|misses|lost|late|evover) =" xsim_zc.log | tr '\n' ' '; echo
python3 compare_zc.py $S
