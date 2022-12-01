#!/usr/bin/bash

# Created on: 30 Nov 2022
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Given a SAT solver's input parameters, convert them to the PCS format.
#
# Example:
#   kissat --range > range && python3 ./convert_to_pcs.py range
#==============================================================================

script_name = "convert_to_pcs.py"
version = '0.0.1'

import sys

class Param:
  name = ''
  left_bound = -1
  right_bound = -1
  default = -1

if len(sys.argv) == 1:
  sys.exit('Usage : ' + script_name + ' solver-parameters')

param_file_name = sys.argv[1]

params = []

# Read SAT solver's parameters:
with open(param_file_name, 'r') as param_file:
  lines = param_file.read().splitlines()
  for line in lines:
    if 'seed' in line or 'statistics' in line or 'verbose' in line:
      continue
    words = line.split(' ')
    assert(len(words) == 4)
    p = Param()
    p.name = words[0]
    p.left_bound = words[1]
    p.default = words[2]
    p.right_bound = words[3]
    params.append(p)

print(str(len(params)) + ' params')

# Convert each parameter to the PCS format:
pcs_str = ''
for p in params:
  # If Boolean:
  if p.left_bound == '0' and p.right_bound == '1':
    default_bool = 'true' if p.default == '1' else 'false'
    pcs_str += p.name + ' {false, true}[' + default_bool + ']'
  # If integer with too many values, force logariphmic steps:
  elif int(p.right_bound) - int(p.left_bound) > 100:
      lb = '1' if int(p.left_bound) == 0 else p.left_bound
      pcs_str += p.name + ' [' + lb + ', ' + p.right_bound + ']' +\
      '[' + p.default + ']il'
  # Just integer:
  else:
    pcs_str += p.name + ' [' + p.left_bound + ', ' + p.right_bound + ']' +\
    '[' + p.default + ']i'
  pcs_str += '\n'

# Report results:
pcs_file_name = param_file_name + '.pcs'
print('Writing to file ' + pcs_file_name)
with open(pcs_file_name, 'w') as ofile:
  ofile.write(pcs_str)
