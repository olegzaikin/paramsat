#!/usr/bin/bash

# Created on: 11 Jan 2022
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Given a SAT solver's input parameters and a CNF, find a better set of
# parameters' values via blackbox optimization algorithms.
#
# Example:
#   python3 ./bbo_param_solver.py kissat_3.0.0 ./kissat3.pcs ./problem.cnf 123
#==============================================================================

script_name = "bbo_param_solver.py"
version = '0.0.1'

import sys
import os
import random
import copy

# Solver's parameters:
class Param:
  name : str
  default : int
  values : list
  def __init__(self):
    self.name = ''
    self.default = -1
    self.values = []

# Set of parameters' values:
class Point:
  values : list
  def __init__(self):
    self.values = []
  def __str__(self):
    s = ''
    assert(len(self.values) > 1)
    for x in self.values[:-1]:
      s += str(x) + ','
    s += str(self.values[-1])
    return s

# Convert string to int if not Boolean:
def convert_if_int(x : str):
  if x in ['true', 'false']:
    return x
  assert(x.isnumeric())
  return int(x)

# Read SAT solver's parameters:
def read_pcs(param_file_name : str):
  params = []
  with open(param_file_name, 'r') as param_file:
    lines = param_file.read().splitlines()
    for line in lines:
      assert('{' in line)
      assert('}' in line)
      assert('[' in line)
      assert(']' in line)
      words = line.strip().split(' ')
      assert(len(words) > 2)
      p = Param()
      p.name = words[0]
      #print(p.name)
      defstr = line.split('[')[1].split(']')[0]
      p.default = convert_if_int(defstr)
      valuesstr = line.split('{')[1].split('}')[0].replace(' ', '')
      lst = valuesstr.split(',')
      #print(lst)
      for x in lst:
          p.values.append(convert_if_int(x))
      assert(len(p.values) > 1)
      assert(p.default in ['true', 'false'] or isinstance(p.default, int))
      #print(str(len(p.values)))
      for val in p.values:
        #print(val)
        assert(val in ['true', 'false'] or isinstance(val, int))
      params.append(p)
  assert(len(params) > 0)
  return params

# Parse CDCL solver's log:
def parse_cdcl_time(o):
	t = -1
	refuted_leaves = -1
	lines = o.split('\n')
	for line in lines:
		if '100.00 %  total' in line:
			words = line.split()
			assert(len(words) == 5)
			t = float(words[1])
	return t

# Run solver on a given point:
def run_solver(solver_name : str, cnf_file_name : str, params : list, point : Point):
  assert(len(params) > 1)
  assert(len(params) == len(point.values))
  s = solver_name + ' '
  for i in range(len(params)):
    s += '--' + params[i].name + '=' + str(point.values[i]) + ' '
  s += cnf_file_name
  o = os.popen(s).read()
  return parse_cdcl_time(o), s

# Return (i+1)-th value if i is not the last element, 0-th element otherwise:
def next_value(value, param_values : list):
  assert(value in param_values)
  indx = -1
  for i in range(len(param_values)):
    if param_values[i] == value:
      indx = i
      break
  assert(indx >= 0 and indx < len(param_values))
  if indx == len(param_values) - 1:
    return param_values[0]
  return param_values[indx+1]

# Find a new record point via (1+1)-EA:
def oneplusone(point : Point, params : list):
  global random
  global checked_points
  assert(len(point.values) == len(params))
  probability = 1/len(params)
  # Change each value with probability:
  new_points = []
  while len(new_points) == 0:
    for i in range(len(params)):
      prob = random.random()
      if (prob <= 1/len(params)):
        new_p = copy.deepcopy(point)
        new_p.values[i] = next_value(new_p.values[i], params[i].values)
        assert(new_p != point)
        if new_p not in checked_points:
          checked_points.add(new_p)
          new_points.append(new_p)
  return new_points

if __name__ == '__main__':

  if len(sys.argv) != 5:
    sys.exit('Usage : ' + script_name + ' solver solver-parameters-file cnf-file seed')

  print('Running script ' + script_name + ' of version ' + version)

  solver_name = sys.argv[1]
  param_file_name = sys.argv[2]
  cnf_file_name = sys.argv[3]
  seed = int(sys.argv[4])

  print('solver_name : ' + solver_name)
  print('param_file_name : ' + param_file_name)
  print('cnf_file_name : ' + cnf_file_name)

  params = read_pcs(param_file_name)
  total_val_num = 0
  def_point = Point()
  for p in params:
    total_val_num += len(p.values)
    def_point.values.append(p.default)
  params_num = len(params)
  assert(len(def_point.values) == params_num)
  print(str(params_num) + ' parameters')
  print(str(total_val_num) + ' values in all parameters')

  print('Default point :')
  print(str(def_point) + '\n')

  best_t, command = run_solver(solver_name, cnf_file_name, params, def_point)
  print('Current best solving time : ' + str(best_t))
  print(command + '\n')

  random.seed(seed)

  checked_points = set()

  best_point = copy.deepcopy(def_point)
  while len(checked_points) < 100:
    new_points = oneplusone(best_point, params)
    assert(len(new_points) > 0)
    #print(str(len(new_points)) + ' new points')
    print('Formed ' + str(len(checked_points)) + ' points')
    for new_p in new_points:
      t, command = run_solver(solver_name, cnf_file_name, params, new_p)
      print('Time : ' + str(t))
      if t < best_t:
        best_t = t
        best_point = copy.deepcopy(new_p)
        print('Updated best time : ' + str(best_t))
        print(command + '\n')
