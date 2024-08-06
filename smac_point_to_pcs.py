#!/usr/bin/bash

# Created on: 6 Aug 2024
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Given a SMAC3's output, convert the final point to the PCS format.
#
# Example:
#   python3 ./smac_point_to_pcs.py out_smac
#==============================================================================

script_name = "convert_to_pcs.py"
version = '0.0.1'

import sys

if len(sys.argv) < 3 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
  print('Usage : ' + script_name + ' out-smac psc-file')
  exit(1)

print('Running ' + script_name + ' of version ' + version)

out_smac = sys.argv[1]
pcs_fname = sys.argv[2]
print('out_smac  : ' + out_smac)
print('pcs_fname : ' + pcs_fname)

is_start_parsing = False
param_str = ''
param_dict = dict()
with open(out_smac, "r") as f:
  lines = f.read().splitlines()
  for line in lines:
    if 'Final Incumbent' in line:
      is_start_parsing = True
    if 'INFO' in line or '}' in line:
      continue
    if is_start_parsing:
      line = line.replace(' ', '')
      line = line.replace('\'', '')
      line = line.replace(',', '')
      param_name = line.split(':')[0]
      param_value = line.split(':')[1]
      param_dict[param_name] = param_value
      print(param_name + ' ' + param_value)
      param_str += '--' + param_name + '=' + param_value + ' '

print('solver=\"kissat3.1.1 ' + param_str[:-1] + '\"')

is_start_parsing = False
param_str = ''
new_pcs_lines = []
with open(pcs_fname, "r") as pcs_f:
  lines = pcs_f.read().splitlines()
  for line in lines:
    if line == '':
      continue
    assert('[' in line and ']' in line)
    param_name = line.split()[0]
    assert(param_name in param_dict)
    param_value = param_dict[param_name]
    before_value_idx = line.rfind('[')
    after_value_idx = line.rfind(']')
    new_pcs_lines.append(line[0:before_value_idx+1] + param_value + line[after_value_idx:])

#for line in new_pcs_lines:
#  print(line)

assert('.pcs' in pcs_fname)
new_pcs_fname = pcs_fname.split('.pcs')[0] + '_upd.pcs'
with open(new_pcs_fname, 'w') as new_pcs_f:
  for line in new_pcs_lines:
    new_pcs_f.write(line + '\n')
