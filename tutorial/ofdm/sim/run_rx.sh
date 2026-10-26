#!/bin/bash
# Whole-frame xsim of ofdm_rx.v against ofdm_fixed.receive_fixed.   ./run_rx.sh [1|2|3|4|all] [sts]      (sts: the 128-sample STS variant, files frame_sts_<n>)
set -e
cd "$(dirname "$0")"
if [ "$2" = sts ]; then P=frame_sts_; G="-generic_top STS=1"; CN=sts_; else P=frame_; G=""; CN=""; fi
python3 gen_frame_vectors.py $2 > /dev/null
R=../../../rtl
xvlog -sv $R/ofdm_cordic.v $R/ofdm_div.v $R/ofdm_fft.v $R/ofdm_chan.v $R/ofdm_data.v $R/ofdm_detect.v $R/ofdm_derot.v $R/qpsk_rx_trig.v $R/ofdm_rx.v tb_ofdm_rx.v > xvlog_rx.log 2>&1 || { grep -i error xvlog_rx.log; exit 1; }
xelab -debug off tb_ofdm_rx $G -s simrx_$P > xelab_rx.log 2>&1
for S in ${1:-all}; do
  if [ "$S" = all ]; then L="1 2 3 4"; else L=$S; fi
  for V in $L; do
    N=$(wc -l < ${P}$V.hex)
    xsim simrx_$P -runall -testplusarg hex=${P}$V.hex -testplusarg ns=$N > xsim_rx.log 2>&1
    echo "== frame ${CN}$V"; grep -E "^frames" xsim_rx.log; python3 compare_rx.py ${CN}$V
  done
done
