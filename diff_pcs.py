#!/usr/bin/bash

# Created on: 6 Feb 2025
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Given files with input parameters of two SAT solvers, choose those parameters
# which occur in both files (i.e. an intersection of parameters lists).
# The values are taken from the second file.
#
# Example:
#   python3 ./diff_pcs ./1.pcs ./2.pcs
#==============================================================================

script_name = "diff_pcs.py"
version = '0.0.1'

import sys

def print_usage():
  print('Usage : ' + script_name + ' pcs1 pcs2')

if __name__ == '__main__':

  if len(sys.argv) < 3:
    print_usage()
    exit(1)

  print('Running script ' + script_name + ' version ' + version)

  fname1 = sys.argv[1]
  fname2 = sys.argv[2]

  pcs1_name = []
  pcs2_name = []

  pcs1_dict = dict()
  pcs2_dict = dict()

  # backbone {0, 1, 2}[1]
  with open(fname1, 'r') as f:
    lines = f.read().splitlines()
    for line in lines:
      if len(line) < 2:
        continue
      words = line.split()
      assert(len(words) > 2)
      name = words[0]
      assert('[' in line and ']' in line)
      def_value = line.split('[')[1].split(']')[0]
      assert(def_value != '')
      pcs1_dict[name] = def_value

  with open(fname2, 'r') as f:
    lines = f.read().splitlines()
    for line in lines:
      if len(line) < 2:
        continue
      words = line.split()
      assert(len(words) > 2)
      name = words[0]
      assert('[' in line and ']' in line)
      def_value = line.split('[')[1].split(']')[0]
      assert(def_value != '')
      pcs2_dict[name] = def_value

  print('param-name before-def-val after-def-val')
  for name in pcs1_dict:
    if pcs2_dict[name] != pcs1_dict[name]:
      print(name + ' ' + pcs1_dict[name] + ' ' + pcs2_dict[name])
