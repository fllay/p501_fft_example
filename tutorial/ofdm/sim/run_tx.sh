#!/bin/bash
# xsim of ofdm_tx.v against ofdm_tx_fixed.py.   ./run_tx.sh [ce_div] [amp] [samples] [sc|sts]
set -e
cd "$(dirname "$0")"
CE=${1:-2}; AMP=${2:-32767}; N=${3:-12000}; VAR=${4:-sc}
STS=0; [ "$VAR" = sts ] && STS=1
xvlog -sv ../../../rtl/ofdm_fft.v ../../../rtl/ofdm_tx.v tb_ofdm_tx.v > xvlog_tx.log 2>&1 || { tail xvlog_tx.log; exit 1; }
xelab -debug off tb_ofdm_tx -generic_top "STS=$STS" -s simtx > xelab_tx.log 2>&1
xsim simtx -runall -testplusarg ce_div=$CE -testplusarg amp=$AMP -testplusarg n=$N > xsim_tx.log 2>&1
grep -E "^samples|timeout|rror" xsim_tx.log
python3 compare_tx.py $AMP $VAR
