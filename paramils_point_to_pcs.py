#!/usr/bin/bash

# Created on: 31 Jan 2025
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Given a ParamILS's output, convert the final point to the PCS format.
#
# Example:
#   python3 ./paramils_point_to_pcs.py out param.pcs
#==============================================================================

script_name = "paramils_point_to_pcs.py"
version = '0.0.2'

import sys

solver = 'kissat4.0.1'

if len(sys.argv) < 3 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
  print('Usage : ' + script_name + ' out-paramils psc-file')
  exit(1)

print('Running ' + script_name + ' of version ' + version)

out_paramils = sys.argv[1]
pcs_fname = sys.argv[2]
print('out_paramils  : ' + out_paramils)
print('pcs_fname : ' + pcs_fname)

param_str = ''
param_dict = dict()
values = []
with open(out_paramils, "r") as f:
  lines = f.read().splitlines()
  for line in lines:
    if 'Final best parameter configuration found:' in line:
      param_line = line.split('Final best parameter configuration found:')[1]
      words = param_line.replace(',', '').split()
      for word in words:
        print(word)
        param_name = word.split('=')[0]
        param_value = word.split('=')[1]
        param_dict[param_name] = param_value
        values.append(param_value)
        #print(param_name + ' ' + param_value)
        param_str += '--' + param_name + '=' + param_value + ' '
      break

s = ''
for val in values[:-1]:
    s += str(val) + ', '
s += str(values[-1])
print('Values :')
print(s)

solver_param_str = 'solver=\"' + solver + ' ' + param_str[:-1] + '\"'
print(solver_param_str)

bash_exec_fname = './' + solver + '_param.sh'
print('Writing to file ' + bash_exec_fname)
with open(bash_exec_fname, 'w') as ofile:
    ofile.write('cnf=$1\n')
    ofile.write(solver_param_str + '\n')
    ofile.write('$solver $cnf\n')

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

assert('.pcs' in pcs_fname)
new_pcs_fname = pcs_fname.split('.pcs')[0] + '_upd.pcs'
print('Writing to file ' + new_pcs_fname)
with open(new_pcs_fname, 'w') as new_pcs_f:
  for line in new_pcs_lines:
    new_pcs_f.write(line + '\n')
