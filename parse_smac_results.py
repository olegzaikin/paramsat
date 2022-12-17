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

import sys
import glob, os

script_name = "parse_smac_results.py"
version = '0.0.2'

class Result:
  obj_val = 0
  solver_call = ''

if len(sys.argv) != 3:
  sys.exit('Usage : ' + script_name + ' smac-output-mask solver-pcs')

print('Running script ' + script_name + ' of version ' + version )

smac_output_mask = sys.argv[1]
solver_pcs_file_name = sys.argv[2]
default_solver_params = dict()
with open(solver_pcs_file_name, 'r') as f:
     lines = f.read().splitlines()
     for line in lines:
         if len(line) < 2:
             continue
         words = line.split(' ')
         assert(len(words) == 3)
         default_solver_params[words[0]] = words[2].split('[')[1].split(']')[0]

print('Default values of solver parameters:')
print(default_solver_params)

params_values = dict()

results = []
for filename in glob.glob(smac_output_mask + '*'):
    print('reading file ' + filename)
    isStartRead = False
    call = ''
    call_params = dict()
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
                if words[2] not in call_params:
                    call_params[words[2]] = words[3]
                if call_params == default_solver_params:
                    print('Skipping set with default values')
                    break
            if 'INFO:	Estimated cost of incumbent: ' in line:
                val = float(line.split('INFO:	Estimated cost of incumbent: ')[1])
                r = Result()
                r.obj_val = val
                r.solver_call = call
                results.append(r)
                for key in call_params:
                    if key not in params_values:
                        params_values[key] = [call_params[key]]
                    else:
                        params_values[key].append(call_params[key])
                #print(str(objval))
results = sorted(results, key=lambda x: x.obj_val)
assert(len(results) != 0)

for p in params_values:
    lst = params_values[p]
    #print(lst)
    if [lst[0]]*len(lst) == lst:
        'Equal elements:'
        print(p)
        print(lst)
    val_counts = dict()
    for val in lst:
        if val not in val_counts:
            val_counts[val] = 1
        else:
            val_counts[val] += 1
    for val in val_counts:
        if val_counts[val] > len(lst)*75/100:
            print('More than 60 % values')
            print(p)
            print(val + ' : ' + str(val_counts[val]) + ' / ' + str(len(lst)))

outfile_name = 'solver_calls'
print('Writing solver calls to ' + outfile_name)
print('')
print('Objective function values:')
with open(outfile_name, 'w') as o:
  #o.write('solver-call\n')
  for r in results:
    print(r.obj_val)
    #o.write(str(r.obj_val) + ' ' + r.solver_call + '\n')
    o.write(r.solver_call + '\n')

print('The best solver call:')
print(results[0].solver_call)
