#!/usr/bin/bash

scriptname="parallel_bbo.sh"
version="0.0.1"

if [ $# -ne 1 ]; then
  echo "Usage: $scriptname cpunum"
  echo "  cpunum    : CPU cores"
  exit 1
fi

echo "Running $scriptname of version $version"

cpunum=$1

echo "cpu_num   : $cpunum"

set -x
for (( i=1; i<=$cpunum; i++ ))
do
    python3 ./bbo_param_solver.py kissat_3.0.0 ./kissat3.pcs ./cbmc_md5-27_1hash.cnf $i &> out_27_$i &
done
