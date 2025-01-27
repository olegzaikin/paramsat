#!/usr/bin/bash

# Created on: 27 Jan 2024
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Given files with input parameters of two SAT solvers, choose those parameters
# which occur in both files (i.e. an intersection of parameters lists).
# The values are taken from the second file.
#
# Example:
#   kissat3 --range > range3 && kissat4 --range > range4
#   python3 ./intersect_params.py ./range3 ./range4
#==============================================================================

script_name = "intersect_params.py"
version = '0.0.1'

import sys

def print_usage():
  print('Usage : ' + script_name + ' solver-parameters')

if __name__ == '__main__':

  if len(sys.argv) < 3:
    print_usage()
    exit(1)

  print('Running script ' + script_name + ' version ' + version)

  fname1 = sys.argv[1]
  fname2 = sys.argv[2]

  params1_names = []
  params2_lines = []

  with open(fname1, 'r') as file1:
    lines = file1.read().splitlines()
    for line in lines:
      if len(line) < 2:
        continue
      words = line.split()
      assert(len(words) == 4)
      params1_names.append(words[0])

  with open(fname2, 'r') as file2:
    lines = file2.read().splitlines()
    for line in lines:
      if len(line) < 2:
        continue
      words = line.split()
      assert(len(words) == 4)
      if words[0] in params1_names:
        params2_lines.append(line)

  print(str(len(params2_lines)) + ' params in the intersection')
  with open('range_intersection', 'w') as f:
    for line in params2_lines:
      f.write(line + '\n')
