#!/usr/bin/bash

# Created on: 11 Jan 2022
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Given a SAT solver's input parameters and a CNF, find a better set of
# parameters' values via blackbox optimization algorithms.
#
# Example:
#   python3 ./bbo_param_solver.py kissat3 ./kissat3.pcs ./problem.cnf -seed=1
#==============================================================================

script_name = "bbo_param_solver.py"
version = '0.1.1'

import sys
import os
import time
import random
import copy
import math
import statistics

def print_usage():
  print('Usage : ' + script_name + ' solver solver-parameters-file cnf-file [Options]')
  print('  Options :\n' +\
  '-deftime=<float>    - (default : -1)   runtime for the default point' + '\n' +\
	'-cpunum=<int>       - (default : 1)    number of used CPU cores' + '\n' +\
	'-seed=<int>         - (default : time) seed for pseudorandom generator' + '\n')

# Input options:
class Options:
	cpu_num : 1
	seed : 0
	def_point_time : -1
	def __init__(self):
		self.cpu_num = 1
		self.seed = round(time.time() * 1000)
		self.def_point_time = -1
	def __str__(self):
		s = 'cpu_num        : ' + str(self.cpu_num) + '\n' +\
		    'seed           : ' + str(self.seed) + '\n' +\
        'def_point_time : ' + str(self.def_point_time) + '\n'
		return s
	def read(self, argv) :
		for p in argv:
			if '-cpunum=' in p:
				self.cpu_num = int(p.split('-cpunum=')[1])
			if '-seed=' in p:
				self.seed = int(p.split('-seed=')[1])
			if '-deftime' in p:
				self.def_point_time = math.ceil(float(p.split('-deftime=')[1]))

# Solver's parameter:
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
  def __getitem__(self, key):
    assert(key < len(self.values))
    return self.values[key]
  def __setitem__(self, key, name):
    assert(key < len(self.values))
    self.values[key] = name

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
	sat = -1
	refuted_leaves = -1
	lines = o.split('\n')
	for line in lines:
		if 'c process-time' in line:
			words = line.split()
			assert(len(words) >= 4)
			assert(words[-1] == 'seconds')
			t = float(words[-2])
		assert('s UNSATISFIABLE' not in line)
		if 's SATISFIABLE' in line:
                  sat = 1
	assert(t > 0)
	return t, sat

# Run solver on a given point:
def run_solver(solver_name : str, time_lim : float, cnf_file_name : str, params : list, point : Point):
  assert(len(params) > 1)
  assert(len(params) == len(point.values))
  sys_str = ''
  if time_lim > 0:
    sys_str = solver_name + ' --time=' + str(math.ceil(time_lim) + 1) + ' '
  else:
    sys_str = solver_name + ' '
  for i in range(len(params)):
    sys_str += '--' + params[i].name + '=' + str(point.values[i]) + ' '
  sys_str += cnf_file_name
  o = os.popen(sys_str).read()
  t, sat = parse_cdcl_time(o)
  return t, sat, sys_str

# Randomly choose an element from a given list except given current value.
# The closer index is to the given one, the higher probability is to be chosen.
def next_value(lst : list, cur_val : int):
  indx = lst.index(cur_val)
  assert(indx >= 0 and indx < len(lst))
  weights = [0 for x in lst]
  max_dist_to_left = indx
  max_dist_to_right = len(lst) - indx - 1
  max_dist = max(max_dist_to_left, max_dist_to_right)
  for i in range(indx):
    weights[indx - i - 1] = pow(2, max_dist-1 - i)
  for i in range(indx+1, len(lst)):
    weights[i] = pow(2, max_dist-1 - (i - indx - 1))
  #print('indx : ' + str(indx))
  #print(weights)
  r = random.choices(lst, weights, k=1)
  assert(len(r) == 1)
  assert(r[0] in lst)
  assert(r[0] != cur_val)
  return r[0]

# Find a new record point via (1+1)-EA:
def oneplusone(point : Point, params : list):
  global random
  global checked_points
  assert(len(point.values) == len(params))
  probability = 1/len(params)
  # Change each value with probability:
  new_points = []
  while len(new_points) == 0:
    new_p = copy.deepcopy(point)
    for i in range(len(params)):
      prob = random.random()
      if (prob <= 1/len(params)):
        oldval = new_p.values[i]
        new_p[i] = next_value(params[i].values, new_p[i])
        assert(new_p != point)
    if new_p not in checked_points:
      checked_points.add(new_p)
      new_points.append(new_p)
  return new_points

def points_diff(p1 : Point, p2 : Point, params : list):
  assert(len(p1.values) == len(p2.values))
  assert(len(p1.values) == len(params))
  s = 'Difference from the default point : \n'
  for i in range(len(p1.values)):
    if p1.values[i] != p2.values[i]:
      s += '  ' + params[i].name + ' : ' + str(p1.values[i]) + \
        ' -> ' + str(p2.values[i]) + '\n'
  return s[:-1]

if __name__ == '__main__':

  if len(sys.argv) < 4:
    print_usage()
    exit(1)

  print('Running script ' + script_name + ' of version ' + version)

  solver_name = sys.argv[1]
  param_file_name = sys.argv[2]
  cnf_file_name = sys.argv[3]

  print('solver_name : ' + solver_name)
  print('param_file_name : ' + param_file_name)
  print('cnf_file_name : ' + cnf_file_name)

  op = Options()
  op.read(sys.argv[3:])
  print(op)

  random.seed(op.seed)

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

  command = ''
  if op.def_point_time > 0:
    best_t = op.def_point_time
  else:
    best_t, sat, command = run_solver(solver_name, -1, cnf_file_name, params, def_point)
    assert(sat == 1)
  print('Current best solving time : ' + str(best_t))
  if command != '':
    print(command + '\n')

  checked_points = set()
  checked_points.add(def_point)

  runtime_def_point = best_t
  best_point = copy.deepcopy(def_point)
  best_command = command
  updates_num = 0
  while len(checked_points) < 100:
    new_points = oneplusone(best_point, params)
    assert(len(new_points) > 0)
    #print(str(len(new_points)) + ' new points')
    for new_p in new_points:
      t, sat, command = run_solver(solver_name, best_t, cnf_file_name, params, new_p)
      print('Time : ' + str(t))
      if sat == 1 and t < best_t:
        updates_num += 1
        best_t = t
        best_point = copy.deepcopy(new_p)
        best_command = command
        print('Updated best time : ' + str(best_t))
        print(points_diff(def_point, best_point, params))
        print(best_command + '\n')
    print('Processed ' + str(len(checked_points)) + ' points')

  print('\n' + str(updates_num) + " updates of best point")
  print('Final best time : ' + str(best_t) + ' , so ' + \
    str(runtime_def_point) + ' -> ' + str(best_t))
  print(points_diff(def_point, best_point, params))
  print('Final best command : \n' + best_command)
