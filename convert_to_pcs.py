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
version = '0.1.11'

import sys

# In kissat3, seed, statistics, verbose, quiet, and prifile don't affect the search.
# The following parameters are in fact not used:
#   backboneeffort, eliminateeffort, eliminateinit, eliminateint,
#   forwardeffort, probeinit, probeint, reduceinit, reduceint, rephaseinit,
#   rephaseint, sweepeffort, vivifyeffort, vivifyirred, walkeffort,
#   walkinitially.
# The following parameters are used but not needed:
#   bump - disables an obligatory CDCL feature.
#   compact - false-value can be reached by compactlim=0
#   minimze - false-value can be reached by minimize* parameters
#   chrono - false-value can be reached by chronolevels=0
#   backbonemaxrounds - should be constant for a variable backbonerounds
#   sweep - false-vale can be reached by sweep* parameters
#   sweepmaxvars - should be constant for a variable sweepvars
#   incremental - because no incremental solving occurs in parameterisation.
#   simplify - it enables both probing and elimination, but these
#   options have their own parameters.
#   bumpreasons - it almost duplicates bump.
#   eliminate - false-value can be reached by eliminate* parameters
#   definitions - false-value can be reached by definition* parameters
#   substitute - false-value can be reached by substitute* parameters
#   vivify - false-value can be reached by vivify* parameters
#   extract - false-value can be reached by ands, equivalences, ifthenelse.
parameters_to_skip = ['seed', 'statistics', 'verbose', 'quiet', 'profile', \
  'backboneeffort', 'bumpreasons', 'eliminateeffort', 'eliminateinit', \
  'eliminateint', 'forwardeffort', 'incremental', 'probeinit', 'probeint', \
  'reduceinit', 'reduceint', 'rephaseinit', 'rephaseint', 'simplify', \
  'sweepeffort', 'vivifyeffort', 'vivifyirred', 'walkeffort', 'walkinitially', \
  'bump', 'compact', 'minimize', 'chrono', 'backbonemaxrounds', 'sweep', \
  'sweepmaxvars', 'eliminate', 'definitions', 'substitute', 'vivify', 'extract']

# The following parameters values are chosen manually, here _*_ means default:
# backbonerounds 1, 10, _100_, 1000
# bumpreasonslimit 1, 2, 4, 8, _10_, 16, 32, 64, 128, 256, 512, 2147483647
# chronolevels 0, 10, _100_, 1000, 2147483647
# definitionticks 0, 100, 10000, _1000000_, 100000000, 2147483647
# defragsize 10, 2048, _262144_, 16777216, 2147483647
# eliminateclslim 1, 10, _100_, 1000, 2147483647
# eliminateocclim 0, 1000, _2000_, 3000, 2147483647
# eliminaterounds 1, _2_, 4, 8, 16, 32, 10000
# emafast 10, 20, _33_, 40, 50, 100, 1000000
# emaslow 100, 50000, 75000, _100000_, 125000, 150000, 1000000
# mineffort 0, 5, _10_, 15, 20, 2147483647
# minimizedepth 1, 10, 100, _1000_, 10000, 1000000
# modeinit 10, 100, _1000_, 10000, 100000, 100000000
# reducefraction 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, _75_, 80, 85, 90, 95, 100
# reluctantint 2, 256, 512, _1024_, 2048, 4096, 32768
# reluctantlim 0, 65536, 262144, _1048576_, 4194304, 16777216, 1073741824
# restartint _1_, 2, 5, 10, 25, 50, 100, 1000, 10000
# restartmargin 0, 5, _10_, 15, 20, 25
# substituteeffort 1, 2, 4, _10_, 16, 32, 64, 1000
# substituterounds 1, _2_, 4, 8, 16, 32, 64, 100
# subsumeclslim 1, 10, 100, _1000_, 10000, 2147483647
# subsumeocclim 0, 1, 10, 100, _1000_, 10000, 2147483647
# sweepclauses 0, 256, 512, _1024_, 2048, 4096, 2147483647
# sweepdepth 0, _1_, 2, 3, 4, 5, 2147483647
# sweepeffort 0, 5, _10_, 15, 20, 100, 10000
# sweepfliprounds 0, _1_, 2, 3, 4, 5, 10, 100, 2147483647
# sweepmaxclauses 2, 1024, 2048, _4096_, 8192, 16384, 2147483647
# sweepmaxdepth 1, _2_, 3, 4, 5, 10, 2147483647
# sweepvars 0, 1, 2, 4, 8, 16, 32, 64, _128_
# tier1 1, _2_, 3, 4, 5, 6, 7, 8, 9, 10, 100
# tier2 1, 2, 3, 4, 5, _6_, 7, 8, 9, 10, 100, 1000
# vivifytier1 1, 2, _3_, 4, 5, 6, 7, 8, 9, 10, 100
# vivifytier2 1, 2, 3, 4, 5, _6_, 7, 8, 9, 10, 100

# Parameters which are worth varying for still-CNFs:
still_params = ['backbone', 'backbonerounds', 'bumpreasonslimit', 'bumpreasonsrate', 'definitionticks',\
  'defraglim', 'defragsize', 'eliminatebound', 'eliminateclslim', 'emafast', 'emaslow', 'mineffort',\
  'minimizedepth', 'reluctantint', 'reluctantlim', 'restartint', 'restartmargin',\
  'stable', 'substituteeffort', 'subsumeclslim', 'subsumeocclim', 'sweepfliprounds', 'sweepmaxclauses',\
  'sweepmaxdepth', 'sweepvars', 'target', 'tier2', 'tumble', 'vivifytier1', 'vivifytier2']

#
dm_params = ['backbone', 'definitioncores', 'eliminatebound', 'emafast', 'mineffort',\
  'minimizedepth', 'modeinit', 'otfs', 'restartint', 'stable', 'substituterounds', 'subsumeclslim',\
  'sweepclauses', 'sweepmaxclauses', 'sweepmaxdepth', 'sweepvars', 'target']

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
# If isStill is True, then a reduced parameters space is constructed.
def read_solver_parameters(param_file_name : str, isStill : bool, isDm : bool):
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
      if isStill == True and p.name not in still_params:
        print('Skip non-still parameter')
        continue
      if isDm == True and p.name not in dm_params:
        print('Skip non-dm parameter')
        continue
      params.append(p)
  assert(len(params) > 0)
  return params

# Convert to string a given list of values:
def domain_to_str(name : str, default : int, values : list):
  assert(name != '')
  assert(len(values) > 0)
  s = name + ' {'
  if values == ['false', 'true']:
    default_bool = 'true' if default == 1 else 'false'
    s += 'false, true}[' + default_bool + ']'
    return s
  assert(default in values)
  for i in values:
    s += str(i)
    if i != values[-1]:
      s += ', '
  s += '}[' + str(default) + ']'
  return s

def set_values(params : list):
  # Convert each parameter to the PCS format:
  values_num = 0
  pcs_str = ''
  for p in params:
    # Manually chosen values:
    if p.name == 'backbonerounds':
      values = [1, 10, 100, 1000]
    elif p.name == 'bumpreasonsrate':
      values = [1, 2, 4, 8, 10, 16, 32, 64, 128, 256, 512, 2147483647]
    elif p.name == 'bumpreasonslimit':
      values = [1, 2, 4, 8, 10, 16, 32, 64, 128, 256, 512, 2147483647]
    elif p.name == 'chronolevels':
      values = [0, 10, 100, 1000, 2147483647]
    elif p.name == 'definitionticks':
      values = [0, 100, 10000, 1000000, 100000000, 2147483647]
    elif p.name == 'defragsize':
      values = [10, 2048, 262144, 16777216, 2147483647]
    elif p.name == 'eliminateclslim':
      values = [1, 10, 100, 1000, 2147483647]
    elif p.name == 'eliminateocclim':
      values = [0, 1000, 2000, 4000, 2147483647]
    elif p.name == 'eliminaterounds':
      values = [1, 2, 4, 8, 16, 32, 10000]
    elif p.name == 'emafast':
      values = [10, 20, 33, 40, 50, 100, 1000000]
    elif p.name == 'emaslow':
      values = [100, 50000, 75000, 100000, 125000, 150000, 1000000]
    elif p.name == 'mineffort':
      values = [0, 5, 10, 15, 20, 2147483647]
    elif p.name == 'minimizedepth':
      values = [1, 10, 100, 1000, 10000, 1000000]
    elif p.name == 'modeinit':
      values = [10, 100, 1000, 10000, 100000, 100000000]
    elif p.name == 'reducefraction':
      values = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
    elif p.name == 'reluctantint':
      values = [2, 256, 512, 1024, 2048, 4096, 32768]
    elif p.name == 'reluctantlim':
      values = [0, 65536, 262144, 1048576, 4194304, 16777216, 1073741824]
    elif p.name == 'restartint':
      values = [1, 2, 5, 10, 25, 50, 100, 1000, 10000]
    elif p.name == 'restartmargin':
      values = [0, 5, 10, 15, 20, 25]
    elif p.name == 'substituteeffort':
      values = [1, 2, 4, 10, 16, 32, 64, 1000]
    elif p.name == 'substituterounds':
      values = [1, 2, 4, 8, 16, 32, 64, 100]
    elif p.name == 'subsumeclslim':
      values = [1, 10, 100, 1000, 10000, 2147483647]
    elif p.name == 'subsumeocclim':
      values = [0, 1, 10, 100, 1000, 10000, 2147483647]
    elif p.name == 'sweepclauses':
      values = [0, 256, 512, 1024, 2048, 4096, 2147483647]
    elif p.name == 'sweepdepth':
      values = [0, 1, 2, 3, 4, 5, 2147483647]
    elif p.name == 'sweepeffort':
      values = [0, 5, 10, 15, 20, 100, 10000]
    elif p.name == 'sweepfliprounds':
      values = [0, 1, 2, 3, 4, 5, 10, 100, 2147483647]
    elif p.name == 'sweepmaxclauses':
      values = [2, 1024, 2048, 4096, 8192, 16384, 2147483647]
    elif p.name == 'sweepmaxdepth':
      values = [1, 2, 3, 4, 5, 10, 2147483647]
    elif p.name == 'sweepvars':
      values = [0, 1, 2, 4, 8, 16, 32, 64, 128]
    elif p.name == 'tier1':
      values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100]
    elif p.name == 'tier2':
      values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100, 1000]
    elif p.name == 'vivifytier1':
      values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100]
    elif p.name == 'vivifytier2':
      values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100]
    # If Boolean:
    elif p.left_bound == 0 and p.right_bound == 1:
      values = ['false', 'true']
    # If integer with few values:
    elif int(p.right_bound) - int(p.left_bound) < 10: # e.g. [0,9] or [11,20]
      values = [i for i in range(p.left_bound, p.right_bound + 1)]
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
    pcs_str += '\n'
    values_num += len(values)
  # end of for p in params:
  return values_num, pcs_str

def print_usage():
  print('Usage : ' + script_name + ' solver-parameters [Options]')
  print('  Options :\n' +\
  '  --still - reduced parameters space for the still problems.' + '\n' +\
  '  --dm    - reduced parameters space for the dm problems.' + '\n')


if __name__ == '__main__':

  if len(sys.argv) == 1:
    print_usage()
    exit(1)

  param_file_name = sys.argv[1]
  isStill = False
  isDm = False
  if len(sys.argv) > 2 and sys.argv[2] == '--still':
    isStill = True
  elif len(sys.argv) > 2 and sys.argv[2] == '--dm':
    isDm = True
  assert(not isStill or not isDm)
  params = read_solver_parameters(param_file_name, isStill, isDm)
  #print(str(len(params)) + ' params')

  values_num, pcs_str = set_values(params)

  print('\n ' + str(values_num) + ' values in ' + str(len(params)) + ' domains')

  # Report results:
  pcs_file_name = param_file_name + '.pcs'
  print('Writing to file ' + pcs_file_name)
  with open(pcs_file_name, 'w') as ofile:
    ofile.write(pcs_str)
