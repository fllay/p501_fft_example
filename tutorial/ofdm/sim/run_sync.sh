#!/bin/bash
# xsim of the OFDM detector and derotator against the integer model.   ./run_sync.sh [a|b|c|d|e|n|all]
set -e
cd "$(dirname "$0")"
xvlog -sv ../../../rtl/ofdm_cordic.v ../../../rtl/ofdm_detect.v ../../../rtl/ofdm_derot.v ../../../rtl/qpsk_rx_trig.v tb_ofdm_sync.v tb_ofdm_derot.v > xvlog_sync.log 2>&1 || { cat xvlog_sync.log | tail; exit 1; }
xelab -debug off tb_ofdm_sync -s simsync > xelab_sync.log 2>&1
for S in ${1:-all}; do
  if [ "$S" = all ]; then L="a b c d e n q"; else L=$S; fi
  for V in $L; do
    N=$(wc -l < sc_$V.hex)
    xsim simsync -runall -testplusarg hex=sc_$V.hex -testplusarg ns=$N > xsim_sync.log 2>&1
    grep -E "^(found|late) =" xsim_sync.log | tr '\n' ' '; python3 compare_sync.py $V
  done
done
xelab -debug off tb_ofdm_derot -s simderot > xelab_derot.log 2>&1
xsim simderot -runall > xsim_derot.log 2>&1
python3 compare_derot.py
