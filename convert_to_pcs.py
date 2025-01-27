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
version = '0.4.0'
MIN_DOMAIN_LEN_LOG_MODE = 11
MAX_RIGHT_BOUND = 2147483647

import sys
from decimal import Decimal

# In kissat3, the following parameters don't affect the search:
#   statistics, verbose, quiet, profile, flushproof.
# The following parameters must be excluded to make kissat deterministic:
#   seed
# The following parameters adjust random decisions which are disabled by
#   default:
# randec, randecfocused, randeclength, randecstable.
# The following parameters are in fact not used:
#   backboneeffort, eliminateeffort, eliminateinit, eliminateint,
#   forwardeffort, probeinit, probeint, reduceinit, reduceint, rephaseinit,
#   randecinit, randecint, rephaseint, sweepeffort, transitiveeffort,
#   vivifyeffort, vivifyirred, walkeffort, walkinitially.
# The following parameters are true by default while their false-values
# disables obligatory CDCL or Kissat heuristics:
#   ands
#   bump
#   bumpreasons
#   compact
#   chrono
#   equivalences
#   extract
#   forward
#   ifthenelse
#   minimize
#   minimizeticks
#   otfs
#   phasesaving
#   probe
#   promote
#   reduce
#   reluctant
#   rephase
#   restart 
#   transitive
#   transitivekeep
#   tumble
#   vivify
#   warmup
# The following parameters are used but not needed for tuning:
#   backbonemaxrounds - should be constant for backbonerounds
#   definitions - false-value can be reached by definition* parameters
#   defragsize - it seems that the watches defragmantation is not called
#     at all since defragsize is too large (2^18)
#   defraglim - see above
#   eliminate - false-value can be reached by eliminate* parameters
#   forcephase - true-value is target=0 and phasesaving=false
#   incremental - no incremental solving occurs in tuning
#   phase - false is not better than true.
#   simplify - it enables both probing and elimination, but these
#     options have their own parameters
#   substitute - false-value can be reached by substitute* parameters
#   sweep - false-value can be reached by sweep* parameters
#   sweepmaxvars - should be constant for sweepvars

parameters_to_skip = ['statistics', 'verbose', 'quiet', 'profile', \
  'flushproof', \
  'seed', \
  'randec', 'randecfocused','randeclength', 'randecstable', \
  'backboneeffort', 'eliminateeffort', 'eliminateinit', \
  'eliminateint', 'forwardeffort', 'probeinit', 'probeint', \
  'randecinit', 'randecint', 'reduceinit', 'reduceint', 'rephaseinit', \
  'rephaseint', 'sweepeffort', 'transitiveeffort', 'vivifyeffort', \
  'vivifyirred', 'walkeffort', 'walkinitially',
  'ands', 'bump', 'bumpreasons', 'compact', 'chrono', 'equivalences', \
  'extract', 'forward', 'ifthenelse', 'minimize', 'minimizeticks', 'otfs', \
  'phasesaving', 'probe', 'promote', 'reduce', 'reluctant', 'rephase', \
  'restart', 'transitive', 'transitivekeep', 'tumble', 'vivify', 'warmup', \
  'backbonemaxrounds', 'definitions', 'defragsize', 'defraglim', 'eliminate', \
  'forcephase', 'incremental', 'phase', 'simplify', 'substitute', 'sweep', \
  'sweepmaxvars']

## log-2-formula1
#0-10-25   [0, 1, 2, 5, 10, 25]
#0-10-100  [0, 1, 2, 5, 10, 25, 50, 100]
#1-2-100   [1, 2, 5, 10, 25, 50, 100]
#1-50-200  [1, 2, 5, 10, 25, 50, 100, 200]
#10-75-100 [10, 25, 50, 75, 100]
#1-6-1000 [1, 3, 6, 10, 25, 50, 100, 200, 500, 1000]
#0-3-100 [0, 1, 3, 6, 10, 25, 50, 100]
#1-3-100  [1, 3, 6, 10, 25, 50, 100]
#1-6-100  [1, 3, 6, 10, 25, 50, 100]

## log-8
#0-16-8192    [0, 2,  16,  128,  1024, 8192]
#1-2-10000    [1, 2,  16,  128,  1024, 10000]
#2-1024-32768 [2, 16, 128, 1024, 8192, 32768] 

## log-10
#1-10-1000          [1, 10, 100, 1000]
#1-1-10000          [1, 10, 100, 1000, 10000]
#1-1000-1000000     [1, 10, 100, 1000, 10000, 100000, 1000000]
#100-100000-1000000 [100, 1000, 10000, 100000, 1000000]
#10-33-1000000 [10, 33, 100, 1000, 10000, 100000, 1000000]

## log-100
#0-10-2147483647      [0, 10, 1000, 100000,  10000000, 2147483647]
#1-10-2147483647      [1, 10, 1000, 100000,  10000000, 2147483647]
#0-100-2147483647     [0, 100,  100000, 10000000, 2147483647]
#0-128-2147483647     [0, 128,  100000, 10000000, 2147483647]
#0-256-2147483647     [0, 256,  100000, 10000000, 2147483647]
#1-100-2147483647     [1, 100,  100000, 10000000, 2147483647]
#0-1-2147483647       [0, 1,  1000, 100000,  10000000, 2147483647]
#1-2-2147483647       [1, 2,  1000, 100000,  10000000, 2147483647]
#1-3-2147483647       [1, 3,  1000, 100000,  10000000, 2147483647]
#0-2-2147483647       [0, 2,  1000, 100000,  10000000, 2147483647]
#2-4096-2147483647    [2, 10, 4096, 100000,  10000000, 2147483647]
#2-32768-2147483647   [2, 10, 1000, 32768,   10000000, 2147483647]
#10-1000-100000000       [10, 1000, 100000,  10000000, 100000000]

## log-1024
#0-1048576-1073741824 [0, 1024, 1048576, 1073741824]
#0-1000000-2147483647 [0, 1024, 1000000, 2147483647]
#0-1000-2147483647    [0, 1000, 1048576, 2147483647]
#1-1000-2147483647    [1, 1000, 1048576, 2147483647]
#0-1024-2147483647    [0, 1024, 1048576, 2147483647]
#0-2000-2147483647    [0, 2000, 1048576, 2147483647]

log_values_dict = {'0-10-25' : [0, 1, 2, 5, 10, 25],\
  '0-10-100' : [0, 1, 2, 5, 10, 25, 50, 100],\
  '1-2-100' : [1, 2, 5, 10, 25, 50, 100],\
  '1-50-200' : [1, 2, 5, 10, 25, 50, 100, 200],\
  '10-75-100' : [10, 25, 50, 75, 100],\
  '1-6-1000' : [1, 3, 6, 10, 25, 50, 100, 200, 500, 1000],\
  '0-3-100' : [0, 1, 3, 6, 10, 25, 50, 100],\
  '1-3-100' : [1, 3, 6, 10, 25, 50, 100],\
  '1-6-100' : [1, 3, 6, 10, 25, 50, 100],\
  '0-16-8192' : [0, 2, 16, 128, 1024, 8192],\
  '1-2-10000' : [1, 2, 16, 128, 1024, 10000],\
  '2-1024-32768' : [2, 16, 128, 1024, 8192, 32768],\
  '2-32768-2147483647' : [2, 10, 1000, 32768, 10000000, 2147483647],\
  '1-10-1000' : [1, 10, 100, 1000],\
  '1-1-10000' : [1, 10, 100, 1000, 10000],\
  '1-1000-1000000' : [1, 10, 100, 1000, 10000, 100000, 1000000],\
  '100-100000-1000000' : [100, 1000, 10000, 100000, 1000000],\
  '10-33-1000000' : [10, 33, 100, 1000, 10000, 100000, 1000000],\
  '0-10-2147483647' : [0, 10, 1000, 100000, 10000000, 2147483647],\
  '1-10-2147483647' : [1, 10, 1000, 100000, 10000000, 2147483647],\
  '0-100-2147483647' : [0, 100, 100000, 10000000, 2147483647],\
  '1-100-2147483647' : [1, 100, 100000, 10000000, 2147483647],\
  '0-128-2147483647' : [0, 128, 100000, 10000000, 2147483647],\
  '0-256-2147483647' : [0, 256, 100000, 10000000, 2147483647],\
  '0-1-2147483647' : [0, 1, 1000, 100000, 10000000, 2147483647],\
  '1-2-2147483647' : [1, 2, 1000, 100000, 10000000, 2147483647],\
  '1-3-2147483647' : [1, 3, 1000, 100000, 10000000, 2147483647],\
  '0-2-2147483647' : [0, 2, 1000, 100000, 10000000, 2147483647],\
  '2-4096-2147483647' : [2, 10, 4096, 100000, 10000000, 2147483647],\
  '10-1000-100000000' : [10, 1000, 100000, 10000000, 100000000],\
  '0-1048576-1073741824' : [0, 1024, 1048576, 1073741824],\
  '0-1000000-2147483647' : [0, 1024, 1000000, 2147483647],\
  '0-1000-2147483647' : [0, 1000, 1048576, 2147483647],\
  '1-1000-2147483647' : [1, 1000, 1048576, 2147483647],\
  '0-1024-2147483647' : [0, 1024, 1048576, 2147483647],\
  '0-2000-2147483647' : [0, 2000, 1048576, 2147483647]}

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

# Read SAT solver's parameters.
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

# Convert a given list of values to string:
def domains_to_str(params : list):
   res_str = ''
   dict_keys = []
   combin_num = 1
   values_len = 1
   for p in params:
      s = p.name + ' '
      values_len = p.right_bound - p.left_bound + 1
      #print(p.name + ' ' + str(values_len))
      if p.left_bound == 0 and p.right_bound == 1:
         assert(values_len == 2)
         assert(p.default == 0 or p.default == 1)
         default_bool_str = 'true' if p.default == 1 else 'false'
         s += '{false, true}[' + default_bool_str + ']'
      elif values_len < MIN_DOMAIN_LEN_LOG_MODE:
        s += '{'
        for i in range(p.left_bound, p.right_bound + 1):
          s += str(i)
          if i != p.right_bound:
            s += ', '
        s += '}[' + str(p.default) + ']'
      # discretization - uniform for a logarithmic scale:
      else:
        key = str(p.left_bound) + '-' + str(p.default) + '-' + str(p.right_bound)
        if key not in dict_keys:
          dict_keys.append(key)
        s += '{'
        values = log_values_dict[key]
        values_len = len(values)
        for i in range(values_len):
          s += str(values[i])
          if i != len(values)-1:
           s += ', '
        s += '}[' + str(p.default) + ']'
      res_str += s + '\n'
      combin_num = combin_num * values_len
   print(str(len(dict_keys)) + ' unique keys in the form leftbound-default-rightbound:')
   for key in dict_keys:
     print(key)
   print('combin_num : ' + '%.2E' % Decimal(combin_num))
   return res_str

def print_usage():
  print('Usage : ' + script_name + ' solver-parameters')

if __name__ == '__main__':

  if len(sys.argv) == 1:
    print_usage()
    exit(1)

  param_file_name = sys.argv[1]
  params = read_solver_parameters(param_file_name)
  print(str(len(params)) + ' parameters where read')

  pcs_str = domains_to_str(params)

  # Report results:
  pcs_file_name = param_file_name + '.pcs'
  print('Writing to file ' + pcs_file_name)
  with open(pcs_file_name, 'w') as ofile:
    ofile.write(pcs_str)
