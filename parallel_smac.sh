#!/usr/bin/bash

# Created on: 30 Nov 2022
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Run Sequential Model Algorithm Configuration (SMAC) in parallel
# to parameterize a SAT solver.
# SMAC3 of version 1.4 is used from the release
#   https://github.com/automl/SMAC3/releases/tag/v1.4.0
#
# Example:
#  parallel_smac.sh ./scenario ROAR 2 
# runs 2 species of SMAC with the shared directory ./out/
#  smac --scenario ./scenario --abort-on-first-run-crash false --mode SMAC4AC --shared_model True --input_psmac_dirs ./smac3-output* --seed 1
#  smac --scenario ./scenario --abort-on-first-run-crash false --mode SMAC4AC --shared_model True --input_psmac_dirs ./smac3-output* --seed 2
#==============================================================================

version="0.0.4"

scriptname="parallel_smac.sh"

if [ $# -ne 2 ]; then
  echo "Usage: $scriptname scenario mode cpunum shareddir"
  echo "  scenario  : path to a file with SMAC scenario"
  echo "  cpunum    : CPU cores"
  exit 1
fi

echo "Running $scriptname of version $version"

scenario=$1
cpunum=$2

echo "scenario  : $scenario"
echo "cpu_num   : $cpunum"

set -x
for (( i=0; i<$cpunum; i++ ))
do
    smac --scenario $scenario --abort-on-first-run-crash false --mode SMAC4AC --shared_model True --input_psmac_dirs ./smac3-output* --seed $i &> out_$i &
done
