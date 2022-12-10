#!/usr/bin/bash

# Created on: 30 Nov 2022
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Parse best parameters' sets from SMAC3 results. 
#
# Example:
#   python3 parse_smac_results.py "out_*"
#==============================================================================

script_name = "parse_smac_results.py"
version = '0.0.1'

import sys
import glob, os

class Result:
  obj_val = 0
  solver_call = ''

if len(sys.argv) != 2:
  sys.exit('Usage : ' + script_name + ' smac-output-mask')

results = []
for filename in glob.glob("out_*"):
    print('reading file ' + filename)
    #if filename != 'out_1':
    #    continue
    isStartRead = False
    call = ''
    with open(filename, 'r') as f:
        lines = f.read().splitlines()
        for line in lines:
            if 'INFO:	Final Incumbent: Configuration(values={' in line:
                isStartRead = True
                continue
            if line == '})':
                isStartRead = False
            if isStartRead:
                line = line.replace(',', '').replace('\'', '').replace(':','')
                words = line.split(' ')
                assert(len(words) == 4)
                call += ' --' + words[2] + '=' + words[3]
            if 'INFO:	Estimated cost of incumbent: ' in line:
                val = float(line.split('INFO:	Estimated cost of incumbent: ')[1])
                r = Result()
                r.obj_val = val
                r.solver_call = call
                results.append(r)
                #print(str(objval))
results = sorted(results, key=lambda x: x.obj_val)
assert(len(results) != 0)

outfile_name = 'solver_calls'
print('Writing solver calls to ' + outfile_name)
print('Objective function values:')
with open(outfile_name, 'w') as o:
  #o.write('solver-call\n')
  for r in results:
    print(r.obj_val)
    #o.write(str(r.obj_val) + ' ' + r.solver_call + '\n')
    o.write(r.solver_call + '\n')

print('The best solver call:')
print(results[0].solver_call)
