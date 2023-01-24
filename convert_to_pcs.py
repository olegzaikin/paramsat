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
version = '0.0.10'

import sys

# In kissat3, seed, statistics, verbose, and quiet don't affect the search.
# The following parameters are in fact not used:
#   backboneeffort, eliminateeffort, eliminateinit, eliminateint,
#   forwardeffort, probeinit, probeint, reduceinit, reduceint, rephaseinit,
#   rephaseint, sweepeffort, vivifyeffort, vivifyirred, walkeffort,
#   walkinitially.
# The following parameters are used but not needed:
#   incremental - because no incremental solving occurs in parameterisation.
#   simplify - it enables both probing and elimination, but these
#   options have their own parameters.
#   bumpreasons - it almost duplicates bump.
parameters_to_skip = ['seed', 'statistics', 'verbose', 'quiet', \
  'backboneeffort', 'bumpreasons', 'eliminateeffort', 'eliminateinit', \
  'eliminateint', 'forwardeffort', 'incremental', 'probeinit', 'probeint', \
  'reduceinit', 'reduceint', 'rephaseinit', 'rephaseint', 'simplify', \
  'sweepeffort', 'vivifyeffort', 'vivifyirred', 'walkeffort', 'walkinitially']

class Param:
  name = ''
  left_bound = -1
  right_bound = -1
  default = -1

def if_parameter_str(s : str, substr : str):
  # kissat --range style:
  if s.startswith(substr + ' '):
    return True
  # cadical style
  if '--' + substr + '=' in s:
    return True
  return False

# Read SAT solver's parameters:
def read_solver_parameters(param_file_name : str):
  params = []
  with open(param_file_name, 'r') as param_file:
    lines = param_file.read().splitlines()
    for line in lines:
      # Check if a parameter must be skipped:
      isSkip = False
      for p in parameters_to_skip:
        if if_parameter_str(line, p):
          isSkip = True
          break
      if isSkip:
        continue
      words = line.strip().split(' ')
      # kissat --range format:
      if len(words) == 4 and '=' not in line:
          p = Param()
          p.name = words[0]
          p.left_bound = int(words[1])
          p.default = int(words[2])
          p.right_bound = int(words[3]) 
      # cadical --help format:
      elif len(words) > 1 and '=' in words[0]:
          assert('--' in words[0])
          s = words[0].replace('--', '')
          print(s)
          p = Param()
          p.name = s.split('=')[0]
          if s.split('=')[1] == 'bool':
              p.left_bound = 0
              p.right_bound = 1
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
      print(words)
      assert(isinstance(p.left_bound, int))
      assert(isinstance(p.right_bound, int))
      assert(isinstance(p.default, int))
      assert(p.left_bound < p.right_bound)
      assert(p.right_bound > 0)
      params.append(p)
  assert(len(params) > 0)
  return params

# Convert to string a given list of values:
def domain_to_str(name : str, default : int, values : list):
  assert(name != '')
  assert(len(values) > 0)
  assert(default in values)
  s = name + ' {'
  for i in values:
    s += str(i)
    if i != values[-1]:
      s += ', '
  s += '}[' + str(default) + ']'
  return s

if __name__ == '__main__':

  if len(sys.argv) == 1:
    sys.exit('Usage : ' + script_name + ' solver-parameters-file')

  param_file_name = sys.argv[1]
  params = read_solver_parameters(param_file_name)
  #print(str(len(params)) + ' params')

  values_num = 0

  # Convert each parameter to the PCS format:
  pcs_str = ''
  for p in params:
    # If Boolean:
    if p.left_bound == 0 and p.right_bound == 1:
      default_bool = 'true' if p.default == 1 else 'false'
      pcs_str += p.name + ' {false, true}[' + default_bool + ']'
      values_num += 2
    # If integer with few values:
    elif int(p.right_bound) - int(p.left_bound) < 10: # e.g. [0,9] or [11,20]
      values = [i for i in range(p.left_bound, p.right_bound + 1)]
      pcs_str += domain_to_str(p.name, p.default, values)
      values_num += len(values)
    # If integer with too many values, use logariphmic steps:
    else:
      koef = 2 if int(p.right_bound) - int(p.left_bound) <= 100000 else 4
      values = [p.left_bound]
      i = p.left_bound
      while values[-1] != p.right_bound:
        if i < 0:
          i *= -1 / koef
        elif i == 0:
          i = 1
        else:
          i *= koef
        if i >= p.right_bound:
          values.append(p.right_bound)
          break
        values.append(i)
      if p.default not in values:
        values.append(p.default)
      values = sorted(values)
      pcs_str += domain_to_str(p.name, p.default, values)
      values_num += len(values)
    pcs_str += '\n'

  print('')
  print(str(values_num) + ' values in ' + str(len(params)) + ' domains')

  # Report results:
  pcs_file_name = param_file_name + '.pcs'
  print('Writing to file ' + pcs_file_name)
  with open(pcs_file_name, 'w') as ofile:
    ofile.write(pcs_str)
