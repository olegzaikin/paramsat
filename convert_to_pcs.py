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
version = '0.0.5'

import sys

class Param:
  name = ''
  left_bound = -1
  right_bound = -1
  default = -1

# Read SAT solver's parameters:
def read_solver_parameters(param_file_name : str):
  params = []
  with open(param_file_name, 'r') as param_file:
    lines = param_file.read().splitlines()
    for line in lines:
      if 'seed' in line or 'statistics' in line or 'verbose' or 'quiet' in line:
        continue
      words = line.strip().split(' ')
      # kissat --range format:
      if len(words) == 4 and '=' not in line:
          p = Param()
          p.name = words[0]
          p.left_bound = words[1]
          p.default = words[2]
          p.right_bound = words[3] 
      # cadical --help format:
      elif len(words) > 1 and '=' in words[0]:
          assert('--' in words[0])
          s = words[0].replace('--', '')
          print(s)
          p = Param()
          p.name = s.split('=')[0]
          if s.split('=')[1] == 'bool':
              p.left_bound = '0'
              p.right_bound = '1'
          else:
              p.left_bound = s.split('=')[1].split('..')[0]
              if 'e' in p.left_bound:
                  p.left_bound = str(int(float(p.left_bound)))
              p.right_bound = s.split('..')[1]
              if 'e' in p.right_bound:
                  p.right_bound = str(int(float(p.right_bound)))
          p.default = words[-1].replace('[', '').replace(']', '')
          if p.default == 'true':
              p.default = 1
          elif p.default == 'false':
              p.default = 0
          elif 'e' in p.default:
              p.default = str(int(float(p.default)))
      params.append(p)
  assert(len(params) > 0)
  return params

if __name__ == '__main__':

  if len(sys.argv) == 1:
    sys.exit('Usage : ' + script_name + ' solver-parameters')

  param_file_name = sys.argv[1]
  params = read_solver_parameters(param_file_name)
  print(str(len(params)) + ' params')

  # Convert each parameter to the PCS format:
  pcs_str = ''
  for p in params:
    # If Boolean:
    if p.left_bound == '0' and p.right_bound == '1':
      default_bool = 'true' if p.default == '1' else 'false'
      pcs_str += p.name + ' {false, true}[' + default_bool + ']'
    # If integer with too many values, force logariphmic steps:
    elif float(p.left_bound) > 0 and int(p.right_bound) - int(p.left_bound) > 100 and float(p.default) > 0:
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
