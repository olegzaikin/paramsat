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
version = '0.3.1'
MIN_DOMAIN_LEN_LOG_MODE = 11

import sys

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
   for p in params:
      s = p.name + ' '
      values_len = p.right_bound - p.left_bound + 1
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
      else:
        s += '['
        assert(values_len >= MIN_DOMAIN_LEN_LOG_MODE)
        # 0 is illegal in SMAC3 logarithmic parameter: 
        mod_left_bound = p.left_bound if p.left_bound > 0 else 1
        s += str(mod_left_bound) + ', ' + str(p.right_bound) + '][' + \
          str(p.default) + ']il'
      res_str += s + '\n'
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
