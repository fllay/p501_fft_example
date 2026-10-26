#!/bin/bash
# xsim of the OFDM detector and derotator against the integer model.   ./run_sync.sh [a|b|c|d|e|n|q|all] [sts]      (sts: the detector of the 128-sample STS variant, no derotator test)
set -e
cd "$(dirname "$0")"
if [ "$2" = sts ]; then P=sts; G="-generic_top STS=1"; else P=sc; G=""; fi
xvlog -sv ../../../rtl/ofdm_cordic.v ../../../rtl/ofdm_detect.v ../../../rtl/ofdm_derot.v ../../../rtl/qpsk_rx_trig.v tb_ofdm_sync.v tb_ofdm_derot.v > xvlog_sync.log 2>&1 || { cat xvlog_sync.log | tail; exit 1; }
xelab -debug off tb_ofdm_sync $G -s sim_sync_$P > xelab_sync.log 2>&1
for S in ${1:-all}; do
  if [ "$S" = all ]; then L="a b c d e n q"; else L=$S; fi
  for V in $L; do
    N=$(wc -l < ${P}_$V.hex)
    xsim sim_sync_$P -runall -testplusarg hex=${P}_$V.hex -testplusarg ns=$N > xsim_sync.log 2>&1
    grep -E "^(found|late) =" xsim_sync.log | tr '\n' ' '; python3 compare_sync.py $V $2
  done
done
if [ "$P" = sc ]; then
  xelab -debug off tb_ofdm_derot -s simderot > xelab_derot.log 2>&1
  xsim simderot -runall > xsim_derot.log 2>&1
  python3 compare_derot.py
fi
