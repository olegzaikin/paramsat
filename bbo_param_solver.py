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
# 
# By default the script works in the estimating mode, where new points are generated
# and processed until a stopping criterion is reached.
# In the solving mode, cpu_num points are generated and processed until on any of them
# a solution is found.
#========================================================================================
#
# TODOs:
# 1. Extend to unsatisfiable CNFs.
# 2. Generate a parallel list of tasks.


script_name = "bbo_param_solver.py"
version = '0.5.4'

import sys
import glob
import os
import time
import random
import copy
import math
import statistics
import string
from datetime import datetime
import multiprocessing as mp

MIN_BEST_COEF = 1.005

def print_usage():
  print('Usage : ' + script_name + ' solver solver-parameters cnfs-folder [Options]')
  print('  Options :\n' +\
  '  -defobj=<float>        - (default : -1)   objective funtion value for the default point' + '\n' +\
  '  -solvertimelim=<float> - (default : -1)   time limit in seconds on solver' + '\n' +\
  '  -maxpoints=<int>       - (default : 1000) maximum number of points to process' + '\n' +\
  '  -pointsfile=<string>   - (default : "")   path to a file with points' + '\n' +\
  '  -cpunum=<int>          - (default : 1)    number of used CPU cores' + '\n' +\
  '  -seed=<int>            - (default : time) seed for pseudorandom generator' + '\n' +\
  '  --solving              - (default : off)  solving mode' + '\n\n' +\
  'Points from the -pointsfile are used along with those which are generated.')

# Input options:
class Options:
	def_point_time = -1
	solver_timelim = -1
	max_points = 1000
	points_file = ''
	cpu_num = 1
	seed = 0
	is_solving = False
	def __init__(self):
		self.def_point_time = -1
		self.solvertimelim = -1
		self.max_points = 1000
		self.points_file = ''
		self.cpu_num = 1
		self.seed = round(time.time() * 1000)
		self.is_solving = False
	def __str__(self):
		s = 'def_point_time  : ' + str(self.def_point_time) + '\n' +\
        'solver_timelim  : ' + str(self.solver_timelim) + '\n' +\
        'max_points      : ' + str(self.max_points) + '\n' +\
        'points_file     : ' + str(self.points_file) + '\n' +\
        'cpu_num         : ' + str(self.cpu_num) + '\n' +\
		    'seed            : ' + str(self.seed) + '\n' +\
		    'is_solving      : ' + str(self.is_solving)
		return s
	def read(self, argv) :
		for p in argv:
			if '-defobj=' in p:
				self.def_point_time = math.ceil(float(p.split('-defobj=')[1]))
			if '-solvertimelim=' in p:
				self.solver_timelim = math.ceil(float(p.split('-solvertimelim=')[1]))
			if '-maxpoints=' in p:
				self.max_points = math.ceil(float(p.split('-maxpoints=')[1]))
			if '-pointsfile=' in p:
				self.points_file = p.split('-pointsfile=')[1]
			if '-cpunum=' in p:
				self.cpu_num = int(p.split('-cpunum=')[1])
			if '-seed=' in p:
				self.seed = int(p.split('-seed=')[1])
			if p == '--solving':
				self.is_solving = True
		assert(self.max_points > 0 and self.cpu_num > 0)
		assert((self.def_point_time > 0 and self.solver_timelim > 0) or (self.def_point_time == -1 and self.solver_timelim == -1))

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

# Parse a CDCL solver's log:
def parse_cdcl_result(cdcl_log : str):
	t = -1.0
	sat = -1
	refuted_leaves = -1
	lines = cdcl_log.split('\n')
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
def kill_solver(solver : str, num : int):
  assert(solver != '')
  assert(num >= 1)
  print('Killing solver ' + solver + ' ' + str(num) + ' times')
  sys_str = 'killall -9 ' + solver.replace('./','')
  for _ in range(num):
    o = os.popen(sys_str).read()
    time.sleep(1)

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
def possibcomb(new_point : list, def_point : list, params : list, paramsdict : dict):
  assert(len(new_point) > 0)
  assert(len(new_point) == len(def_point))
  assert(len(new_point) == len(params))
  # backbone:
  if 'backbone' in paramsdict and new_point[paramsdict['backbone']] == 0:
    lst = ['backbonerounds']
    for name in lst:
      if name not in paramsdict:
        continue
      if not equalparamval(name, new_point, def_point, paramsdict):
        return False
  # definitions:
  if 'definitions' in paramsdict and new_point[paramsdict['definitions']] == 'false':
    lst = ['definitioncores', 'definitionticks']
    for name in lst:
      if name not in paramsdict:
        continue
      if not equalparamval(name, new_point, def_point, paramsdict):
        return False
  # eliminate:
  if 'eliminate' in paramsdict and new_point[paramsdict['eliminate']] == 'false':
    lst = ['eliminatebound', 'eliminateclslim', 'eliminateocclim', \
      'eliminaterounds', 'forward']
    for name in lst:
      if name not in paramsdict:
        continue
      if not equalparamval(name, new_point, def_point, paramsdict):
        return False
  # substitute:
  if 'substitute' in paramsdict and new_point[paramsdict['substitute']] == 'false':
    lst = ['substituteeffort', 'substituterounds']
    for name in lst:
      if name not in paramsdict:
        continue
      if not equalparamval(name, new_point, def_point, paramsdict):
        return False
  # vivify:
  if 'vivify' in paramsdict and new_point[paramsdict['vivify']] == 'false':
    lst = ['vivifytier1', 'vivifytier2']
    for name in lst:
      if name not in paramsdict:
        continue
      if not equalparamval(name, new_point, def_point, paramsdict):
        return False
  return True

# Generate new points via (1+1)-EA:
def oneplusone(point : list, params : list, paramsdict : dict, points_num : int):
  global random
  global generated_points
  global def_point
  global skipped_repeat_num
  global skipped_impos_num
  assert(len(point) == len(params))
  assert(points_num >= 0)
  new_points = []
  if points_num == 0:
    return new_points
  probability = 1/len(params)
  # Change each value with probability:
  while len(new_points) < points_num:
    pnt = copy.deepcopy(point)
    for i in range(len(params)):
      prob = random.random()
      if (prob <= 1/len(params)):
        oldval = pnt[i]
        pnt[i] = next_value(params[i].values, pnt[i])
        assert(pnt != point)
    # Check if point is impossible combination:
    if not possibcomb(pnt, def_point, params, paramsdict):
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
    return 'The new point is the default one'
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
  params : list, point : list, is_solving : bool):
  assert(len(params) > 1)
  assert(len(params) == len(point))
  assert(len(cnfs) > 0)
  par10_time = 0.0
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
    #print(sys_str)
    cdcl_log = os.popen(sys_str).read()
    t, sat = parse_cdcl_result(cdcl_log)
    assert(t > 0)
    if sat == -1 or (solver_timelim > 0 and t >= solver_timelim):
      par10_time += solver_timelim * 10
    else:
      # Only if a CNF is solved in time limit:
      par10_time += t
      max_time = t if max_time < t else max_time
      #print('Solved in time limit :')
      #print(sys_str)
      print('Time : ' + str(t))
      # In solving mode, the CDCL solver's log should be saved:
      if is_solving:
        assert('.cnf' in cnf_file_name)
        cdcl_log_file_name = 'log_' + solver_name.replace('./','') + '_' + os.path.basename(cnf_file_name.split('.cnf')[0])
        now = datetime.now()
        cdcl_log_file_name += '_' + now.strftime("%d-%m-%Y_%H-%M-%S")
        print('Writing CDCL solver log to file ' + cdcl_log_file_name)
        with open(cdcl_log_file_name, 'w') as f:
          f.write(cdcl_log)

  #print('PAR10 in calc_obj : ' + str(par10_time))
  return point, par10_time, max_time, sat, sys_str

# Collect a result produced by solver:
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
  print('PAR10 time in collect_result : ' + str(par10_time) + ' seconds')
  print('max_time : ' + str(max_time) + ' seconds')
  # Slighly better time might be because of CPU, so use a coefficent:
  if sat == 1 and (par10_time*MIN_BEST_COEF < best_par10_time or best_par10_time <= 0):
    updates_num += 1
    best_par10_time = par10_time
    best_point = copy.deepcopy(point)
    best_command = command
    elapsed_time = round(time.time() - start_time, 2)
    print('\nUpdated best PAR10 time : ' + str(best_par10_time))
    if max_time < best_solver_timelim or best_solver_timelim <= 0:
      best_solver_timelim = max_time
      print('New best solver max time : ' + str(best_solver_timelim))
    print('elapsed : ' + str(elapsed_time) + ' seconds')
    print(points_diff(def_point, best_point, params))
    print(best_command + '\n')

# Read all CNFs in a given folder:
def read_cnfs(cnfs_folder_name : str):
  cnfs = list()
  os.chdir('.')
  for f in glob.glob(cnfs_folder_name + '/*.cnf'):
    assert('.cnf' in f)
    cnfs.append(f)
  return cnfs

# String-representation of a given point:
def strlistrepr(lst : list):
  assert(len(lst) > 1)
  s = ''
  for x in lst[:-1]:
    s += str(x) + '-'
  s += str(lst[-1])
  return s

# Writed generated points to a file:
def write_points(points : list, cnfs : list):
  out_name = 'generated_'
  cleared_cnfs = []
  for x in cnfs:
    assert('.cnf' in x)
    out_name += os.path.basename(x.split('.cnf')[0])
    if x != cnfs[-1]:
      out_name += '_'
  print('Writing generated points to file ' + out_name)
  with open(out_name, 'w') as f:
    for p in points:
      f.write(str(p))
      f.write('\n')

# Read points from a text file:
def read_points(points_file_name : str, def_point : list, paramsdict : dict):
  if points_file_name == '':
    return []
  given_points = []
  with open(points_file_name, 'r') as points_file:
    lines = points_file.read().splitlines()
    for line in lines:
      words = line.split()
      point = copy.deepcopy(def_point)
      for word in words:
        param_name = word.split('--')[1].split('=')[0]
        value = word.split('=')[1]
        point[paramsdict[param_name]] = value
      given_points.append(point)
  return given_points

# Main function:
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
  params_num = len(params)
  print(str(params_num) + ' parameters')
  print(str(total_val_num) + ' values in all parameters')

  paramsdict = dict()
  for i in range(len(params)):
    paramsdict[params[i].name] = i
  print('Dictionary of parameters :')
  print(paramsdict)

  def_point = list()
  for prm in params:
    total_val_num += len(prm.values)
    def_point.append(prm.default)
  assert(len(def_point) == params_num)
  print('Default point :')
  print(str(def_point) + '\n')

  # SAT point, i.e. --target=2 --restartint=50:
  sat_point = copy.deepcopy(def_point)
  sat_point[paramsdict['target']] = 2
  sat_point[paramsdict['restartint']] = 50
  assert(sat_point != def_point)
  print('SAT-params point :')
  print(str(sat_point) + '\n')

  # UNSAT point, i.e. --stable=0:
  unsat_point = copy.deepcopy(def_point)
  unsat_point[paramsdict['stable']] = 0
  assert(unsat_point != def_point and unsat_point != sat_point)
  print('UNSAT-params point :')
  print(str(unsat_point) + '\n')

  # Read points which are given in a text file:
  given_points = read_points(op.points_file, def_point, paramsdict)

  cnfs = []
  cnfs = read_cnfs(cnfs_folder_name)
  assert(len(cnfs) > 0)
  print(str(len(cnfs)) + ' CNFs were read :')
  for cnf in cnfs:
    print(cnf)

  # Here best_solver_timelim is the runtime on default point
  best_solver_timelim = op.solver_timelim 
  default_solver_timelim = op.solver_timelim
  best_par10_time = op.def_point_time
  default_par10_time = op.def_point_time
  print('Current best PAR10 time : ' + str(best_par10_time))
  print('Current best solver time limit : ' + str(best_solver_timelim))

  elapsed_time = round(time.time() - start_time, 2)
  print('Elapsed : ' + str(elapsed_time) + ' seconds')

  processed_points_num = 0
  generated_points = set()
  # In runtime of default point is given, mark it as generated and processed:
  if best_solver_timelim > 0:
    processed_points_num = 1 # the default point is processed
    generated_points.add(strlistrepr(def_point))
    assert(len(generated_points) == 1)
    assert(best_solver_timelim > 0)
    assert(default_par10_time > 0)
  best_point = copy.deepcopy(def_point)
  # Command for default point:
  best_command = solver_name + ' ' + cnfs[0]
  skipped_repeat_num = 0
  skipped_impos_num = 0
  updates_num = 0
  iter = 0

  while True:
    # If default point's runtime is not given: 
    if best_solver_timelim == -1:
      assert(iter == 0)
      print('Runtime for default point is not given, process it.')
      new_points = [copy.deepcopy(def_point)]
      generated_points.add(strlistrepr(def_point))
      if op.cpu_num > 1:
        new_points.append(sat_point)
        generated_points.add(strlistrepr(sat_point))
        print('... and SAT-params point')
        print(sat_point)
      if op.cpu_num > 2:
        new_points.append(unsat_point)
        generated_points.add(strlistrepr(unsat_point))
        print('... and UNSAT-params point')
        print(unsat_point)
      if op.cpu_num > 3:
        for p in given_points:
          new_points.append(p)
          generated_points.add(strlistrepr(p))
          print('... and given point')
          print(p)
          if len(new_points) == op.cpu_num:
            break
      assert(len(new_points) <= op.cpu_num)
      gen_points = oneplusone(best_point, params, paramsdict, op.cpu_num - len(new_points))
      print('Generated ' + str(len(gen_points)) + ' points by (1+1)-EA')
      for p in gen_points:
        new_points.append(copy.deepcopy(p))
    else:
      new_points = oneplusone(best_point, params, paramsdict, op.cpu_num)    
    assert((iter == 0 and len(new_points) == len(generated_points)) or (iter > 0 and len(new_points) < len(generated_points)))
    # Run 1 point on each CPU core:
    assert(len(new_points) == op.cpu_num)
    # Process all points in parallel:
    pool = mp.Pool(op.cpu_num)
    for p in new_points:
      pool.apply_async(calc_obj, args=(solver_name, best_solver_timelim, cnfs, params, p, op.is_solving), callback=collect_result)
    while len(pool._cache) == op.cpu_num: # While all CPU cores are busy,
      time.sleep(2)                       # wait.
    # Here at least 1 task is completed. It might be because of the best
    # time's update or because the time limit is reached. Anyway, kill all
    # remaining cpunum-1 solver's runs.
    processed_points_num += len(new_points)
    print(str(processed_points_num) + ' points processed')
    kill_solver(solver_name, len(cnfs))
    pool.close()
    pool.join()
    assert(best_solver_timelim > 0)
    assert(best_par10_time > 0)
    iter += 1
    # Write generated points:
    write_points(generated_points, cnfs)
    #
    if processed_points_num >= op.max_points:
      print('The limit on the number of points is reached, break.')
      break
    if op.is_solving:
      # Only 1 iteration in the solving mode:
      print('Breaking the main loop because of solving mode')
      assert(iter == 1)
      break

  elapsed_time = round(time.time() - start_time, 2)
  print('\nElapsed : ' + str(elapsed_time) + ' seconds')
  print(str(iter) + ' iterations')
  print(str(updates_num) + " updates of best point")
  print(str(skipped_repeat_num + skipped_impos_num) + ' skipped points, of them:')
  print('  ' + str(skipped_repeat_num ) + ' repeated points')
  print('  ' + str(skipped_impos_num) + ' impossible-combination points')
  print(str(len(generated_points)) + ' generated points')
  print(str(processed_points_num) + ' processed points')
  print('Final best solver time limit : ' + str(best_solver_timelim) + ' , so ' + \
    str(default_solver_timelim) + ' -> ' + str(best_solver_timelim))
  print('Final best PAR10 time : ' + str(best_par10_time) + ' , so ' + \
    str(default_par10_time) + ' -> ' + str(best_par10_time))
  if updates_num > 0:
    print(points_diff(def_point, best_point, params))
  print('Final best command : \n' + best_command)
