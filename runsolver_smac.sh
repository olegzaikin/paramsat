#!/usr/bin/bash

# Created on: 28 Nov 2022
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Run a solver on input parameters given by SMAC3.
# SMAC stands for Sequential Model Algorithm Configuration.
#
# Example:
#   ./runsolver_smac.sh kissat 1.cnf X 10 X X X -stable false
# will run
#   kissat 1.cnf --time=10 -q -n --stable=false
#==============================================================================

version="0.0.2"
scriptname="runsolver_smac.sh"

if [ $# -lt 6 ]; then
  echo "Usage: $scriptname solver CNF X cutofftime X X X param1 value1"
  echo "  scenario    : path to a file with SMAC scenario"
  echo "  solver      : SAT solver name"
  echo "  CNF         : CNF name"
  echo "  X           : SMAC's data with redundant information"
  echo "  cutofftime  : cutoff time in seconds for the solver"
  echo "  param1      : SAT solver's parameter"
  echo "  value1      : Value of SAT solver's parameter param1"
  exit 1
fi

echo "Running $scriptname of version $version"

solver=$1
cnf_name=$2
cutoff_time=$4

# Form all pairs of SAT solver's parameters:
shift 6
params=""
while (( "$#" >= 2 )); do
  params="${params} -${1}=${2}"
  shift 2
done

# Start SAT solver in the quiet mode because here only runtime is needed:
start=`date +%s.%N`
set -x
# Call SAT solver with the time limit:
if [[ "$solver" == "kissat"* ]]; then
  $solver $cnf_name --time=$cutoff_time -q -n $params
elif [[ "$solver" == "cadical"* ]]; then
  $solver $cnf_name -t $cutoff_time -q -n $params
fi
end=`date +%s.%N`
# Runtime in seconds:
runtime=$( echo "$end - $start" | bc -l )
# Print runtime in SMAC format:
echo "Result for SMAC: SUCCESS, $runtime, -1, -1, 0, -1"
