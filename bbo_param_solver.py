#!/usr/bin/bash

# Created on: 11 Jan 2022
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Given a SAT solver's input parameters and a CNF, find a better set of
# parameters' values via blackbox optimization algorithms.
#
# Example:
#   python3 ./bbo_param_solver.py ./kissat3 ./kissat3.pcs ./cnfs/ -seed=1 -cpunum=2
#========================================================================================

script_name = "bbo_param_solver.py"
version = '0.4.0'

import sys
import glob
import os
import time
import random
import copy
import math
import statistics
import string
import multiprocessing as mp

def print_usage():
  print('Usage : ' + script_name + ' solver solver-parameters cnfs-folder [Options]')
  print('  Options :\n' +\
  '-defobj=<float>        - (default : -1)   objective funtion value for the default point' + '\n' +\
  '-solvertimelim=<float> - (default : -1)   time limit in seconds on solver' + '\n' +\
  '-maxpoints=<int>       - (default : 1000) maximum number of points to process' + '\n' +\
  '-cpunum=<int>          - (default : 1)    number of used CPU cores' + '\n' +\
  '-seed=<int>            - (default : time) seed for pseudorandom generator' + '\n')

# Input options:
class Options:
	def_point_time = -1
	solver_timelim = -1
	max_points = 1000
	cpu_num = 1
	seed = 0
	def __init__(self):
		self.def_point_time = -1
		self.solvertimelim = -1
		self.max_points = 1000
		self.cpu_num = 1
		self.seed = round(time.time() * 1000)
	def __str__(self):
		s = 'def_point_time  : ' + str(self.def_point_time) + '\n' +\
        'solver_timelim  : ' + str(self.solver_timelim) + '\n' +\
        'max_points      : ' + str(self.max_points) + '\n' +\
        'cpu_num         : ' + str(self.cpu_num) + '\n' +\
		    'seed            : ' + str(self.seed) + '\n'
		return s
	def read(self, argv) :
		for p in argv:
			if '-defobj' in p:
				self.def_point_time = math.ceil(float(p.split('-defobj=')[1]))
			if '-solvertimelim' in p:
				self.solver_timelim = math.ceil(float(p.split('-solvertimelim=')[1]))
			if '-maxpoints' in p:
				self.max_points = math.ceil(float(p.split('-maxpoints=')[1]))
			if '-cpunum=' in p:
				self.cpu_num = int(p.split('-cpunum=')[1])
			if '-seed=' in p:
				self.seed = int(p.split('-seed=')[1])

# Solver's parameter:
class Param:
  name : str
  default : int
  values : list
  def __init__(self):
    self.name = ''
    self.default = -1
    self.values = []

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
      prm = Param()
      prm.name = words[0]
      #print(p.name)
      defstr = line.split('[')[1].split(']')[0]
      prm.default = convert_if_int(defstr)
      valuesstr = line.split('{')[1].split('}')[0].replace(' ', '')
      lst = valuesstr.split(',')
      #print(lst)
      for x in lst:
          prm.values.append(convert_if_int(x))
      assert(len(prm.values) > 1)
      assert(prm.default in ['true', 'false'] or isinstance(prm.default, int))
      #print(str(len(p.values)))
      for val in prm.values:
        #print(val)
        assert(val in ['true', 'false'] or isinstance(val, int))
      params.append(prm)
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

# Kill a solver:
def kill_solver(solver : str):
  print("Killing solver " + solver)
  sys_str = 'killall -9 ' + solver.replace('./','')
  o = os.popen(sys_str).read()

# Create a copy of a given solver to kill the latter safely:
def create_solver_copy(solver_name : str, random_str : str):
  new_solver_name = solver_name + '_' + random_str
  print("Creating solver " + new_solver_name)
  sys_str = 'cp ' + solver_name + ' ' + new_solver_name
  o = os.popen(sys_str).read()
  return new_solver_name

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

# Whether two given points are equal:
def equalparamval(paramname : str, point1 : list, point2 : list, inddict : dict):
  assert(paramname in inddict)
  return point1[inddict[paramname]] == point2[inddict[paramname]]

# Check if a given point is a possible combination of parameters: 
def possibcomb(new_point : list, def_point : list, params : list):
  assert(len(new_point) > 0)
  assert(len(new_point) == len(def_point))
  assert(len(new_point) == len(params))
  parind = dict()
  for i in range(len(params)):
    parind[params[i].name] = i
  # backbone:
  if 'backbone' in parind and new_point[parind['backbone']] == 0:
    lst = ['backbonerounds']
    for name in lst:
      if not equalparamval(name, new_point, def_point, parind):
        return False
  # definitions:
  if 'definitions' in parind and new_point[parind['definitions']] == 'false':
    lst = ['definitioncores', 'definitionticks']
    for name in lst:
      if not equalparamval(name, new_point, def_point, parind):
        return False
  # eliminate:
  if 'eliminate' in parind and new_point[parind['eliminate']] == 'false':
    lst = ['eliminatebound', 'eliminateclslim', 'eliminateocclim', \
      'eliminaterounds', 'forward']
    for name in lst:
      if not equalparamval(name, new_point, def_point, parind):
        return False
  # substitute:
  if 'substitute' in parind and new_point[parind['substitute']] == 'false':
    lst = ['substituteeffort', 'substituterounds']
    for name in lst:
      if not equalparamval(name, new_point, def_point, parind):
        return False
  # vivify:
  if 'vivify' in parind and new_point[parind['vivify']] == 'false':
    lst = ['vivifytier1', 'vivifytier2']
    for name in lst:
      if not equalparamval(name, new_point, def_point, parind):
        return False
  return True

# Test detection of possible combinations of parameters' values:
def test_possibcomb(def_point : list, params : list):
  new_point = copy.deepcopy(def_point)
  new_point[1] = 0 # backbone
  new_point[2] = 100 # default
  new_point2 = copy.deepcopy(def_point)
  new_point2[1] = 0 # backbone
  new_point2[2] = 1
  assert(possibcomb(def_point, def_point, params) == True)
  assert(possibcomb(new_point, def_point, params) == True)
  assert(possibcomb(new_point2, def_point, params) == False)

# Generate new points via (1+1)-EA:
def oneplusone(point : list, params : list, points_num : int):
  global random
  global generated_points
  global def_point
  global skipped_repeat_num
  global skipped_impos_num
  assert(len(point) == len(params))
  probability = 1/len(params)
  # Change each value with probability:
  new_points = []
  while len(new_points) < points_num:
    pnt = copy.deepcopy(point)
    for i in range(len(params)):
      prob = random.random()
      if (prob <= 1/len(params)):
        oldval = pnt[i]
        pnt[i] = next_value(params[i].values, pnt[i])
        assert(pnt != point)
    # Check if point is impossible combination:
    if not possibcomb(pnt, def_point, params):
      print('Impossible combination:')
      print(strlistrepr(pnt))
      skipped_impos_num += 1
      print(str(skipped_impos_num) + ' impossible points skipped')
      continue
    # If point has been already processed:
    if strlistrepr(pnt) in generated_points:
      skipped_repeat_num += 1
      print(str(skipped_repeat_num) + ' repeated points skipped')
    else:
      # New point and possible combination:
      generated_points.add(strlistrepr(pnt))
      new_points.append(pnt)
  return new_points

# Difference between two given points (empty string if equal points):
def points_diff(p1 : list, p2 : list, params : list):
  assert(len(p1) == len(p2))
  assert(len(p1) == len(params))
  if p1 == p2:
    return ''
  s0 = 'Difference from the default point : \n'
  s = ''
  for i in range(len(p1)):
    if p1[i] != p2[i]:
      s += '  ' + params[i].name + ' : ' + str(p1[i]) + \
        ' -> ' + str(p2[i]) + '\n'
  assert(s != '')
  return s0 + s[:-1]

# Run solver on a given point:
def calc_obj(solver_name : str, solver_timelim : float, cnfs : list, \
  params : list, point : list):
  assert(len(params) > 1)
  assert(len(params) == len(point))
  assert(len(cnfs) > 0)
  par10_time = 0
  max_time = -1
  sat = -1
  # Calculate PAR10 for the solver runtimes: sum(time if solved in lim seconds,
  # otherwise lim*10)
  for cnf_file_name in cnfs:
    sys_str = ''
    if solver_timelim > 0:
      sys_str = solver_name + ' --time=' + str(math.ceil(solver_timelim)) + ' '
    else:
      sys_str = solver_name + ' '
    for i in range(len(params)):
      sys_str += '--' + params[i].name + '=' + str(point[i]) + ' '
    sys_str += cnf_file_name
    o = os.popen(sys_str).read()
    t, sat = parse_cdcl_time(o)
    assert(t > 0)
    if solver_timelim > 0 and t >= solver_timelim:
      par10_time += solver_timelim * 10
    else:
      par10_time += t
      max_time = t if max_time < t else max_time

  return point, par10_time, max_time, sat, sys_str

# Collect a result produxed by solver:
def collect_result(res):
  global updates_num
  global best_par10_time
  global best_solver_timelim
  global best_point
  global best_command
  global def_point
  global params
  global processed_points_num
  global start_time
  assert(len(res) == 5)
  point = res[0]
  par10_time = res[1]
  max_time = res[2]
  sat = res[3]
  command = res[4]
  print('PAR10 time : ' + str(par10_time) + ' seconds')
  print('max_time : ' + str(max_time) + ' seconds')
  processed_points_num += 1
  print(str(processed_points_num) + ' points processed')
  if sat == 1 and par10_time < best_par10_time:
    updates_num += 1
    best_par10_time = par10_time
    best_point = copy.deepcopy(p)
    best_command = command
    elapsed_time = round(time.time() - start_time, 2)
    print('\nUpdated best PAR10 time : ' + str(best_par10_time))
    if max_time < best_solver_timelim:
      best_solver_timelim = max_time
      print('Updated best solver max time : ' + str(best_solver_timelim))
    print('elapsed : ' + str(elapsed_time) + ' seconds')
    print(points_diff(def_point, best_point, params))
    print(best_command + '\n')

# Read all CNFs in a given folder:
def read_cnfs(cnfs_folder_name : str):
  cnfs = list()
  os.chdir('.')
  for file in glob.glob(cnfs_folder_name + '/*.cnf'):
    cnfs.append(file)
  return cnfs

# String-representation of a given point:
def strlistrepr(lst : list):
  assert(len(lst) > 1)
  s = ''
  for x in lst[:-1]:
    s += str(x) + '-'
  s += str(lst[-1])
  return s

if __name__ == '__main__':
  if len(sys.argv) < 4:
    print_usage()
    exit(1)

  print('Running script ' + script_name + ' of version ' + version)

  start_time = time.time()

  solver_name = sys.argv[1]
  param_file_name = sys.argv[2]
  cnfs_folder_name = sys.argv[3]

  print('solver_name : ' + solver_name)
  print('param_file_name : ' + param_file_name)
  print('cnfs_folder_name : ' + cnfs_folder_name)

  op = Options()
  op.read(sys.argv[3:])
  print(op)

  random.seed(op.seed)

  random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 10))    
  print("The randomly generated string is : " + str(random_str))
  new_solver_name = create_solver_copy(solver_name, random_str)
  solver_name = new_solver_name
  print('Solver name changed to ' + new_solver_name)

  params = read_pcs(param_file_name)
  total_val_num = 0
  def_point = list()
  for prm in params:
    total_val_num += len(prm.values)
    def_point.append(prm.default)
  params_num = len(params)
  assert(len(def_point) == params_num)
  print(str(params_num) + ' parameters')
  print(str(total_val_num) + ' values in all parameters')

  print('Default point :')
  print(str(def_point) + '\n')

  cnfs = []
  cnfs = read_cnfs(cnfs_folder_name)
  assert(len(cnfs) > 0)
  print(str(len(cnfs)) + ' CNFs were read :')
  for cnf in cnfs:
    print(cnf)

  # Test:
  test_possibcomb(def_point, params)

  best_par10_time = -1
  best_solver_timelim = op.solver_timelim

  command = ''
  if op.def_point_time > 0:
    best_par10_time = op.def_point_time
  else:
    p, best_par10_time, best_solver_timelim, sat, command = calc_obj(solver_name, -1, cnfs, params, def_point)
    assert(sat == 1)
    assert(p == def_point)
  print('Current best PAR10 time : ' + str(best_par10_time))
  if command != '':
    print(command + '\n')

  elapsed_time = round(time.time() - start_time, 2)
  print('elapsed : ' + str(elapsed_time) + ' seconds')

  generated_points = set()
  generated_points.add(strlistrepr(def_point))
  processed_points_num = 1 # the default point is processed
  runtime_def_point = best_par10_time
  best_point = copy.deepcopy(def_point)
  best_command = command
  skipped_repeat_num = 0
  skipped_impos_num = 0
  updates_num = 0

  while True:
    # Generate 1 point for each CPU core:
    new_points = oneplusone(best_point, params, op.cpu_num)
    assert(len(new_points) == op.cpu_num)
    # Process all points in parallel:
    pool = mp.Pool(op.cpu_num)
    for p in new_points:
      pool.apply_async(calc_obj, args=(solver_name, best_solver_timelim, cnfs, params, p), callback=collect_result)
    while len(pool._cache) == op.cpu_num: # While all CPU cores are busy,
      time.sleep(2)                       # wait.
    # Here at least 1 task is completed. It might be because of the best
    # time's update or because the time limit is reached. Anyway, kill all
    # remaining cpunum-1 solver's runs.   
    kill_solver(solver_name)
    pool.close()
    pool.join()
    if processed_points_num >= op.max_points:
      print('The limit on the number of points is reached, break.')
      break

  elapsed_time = round(time.time() - start_time, 2)
  print('\nelapsed : ' + str(elapsed_time) + ' seconds')
  print(str(updates_num) + " updates of best point")
  print(str(skipped_repeat_num + skipped_impos_num) + ' skipped points, of them:')
  print('  ' + str(skipped_repeat_num ) + ' repeated points')
  print('  ' + str(skipped_impos_num) + ' impossible-combination points')
  print(str(processed_points_num) + ' processed points')
  print('Final best PAR10 time : ' + str(best_par10_time) + ' , so ' + \
    str(runtime_def_point) + ' -> ' + str(best_par10_time))
  if updates_num > 0:
    print(points_diff(def_point, best_point, params))
  print('Final best command : \n' + best_command)
