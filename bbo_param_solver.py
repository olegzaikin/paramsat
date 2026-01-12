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
# 0. Extend to unsatisfiable CNFs.

script_name = "bbo_param_solver.py"
version = '0.8.6'

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

def print_usage():
  print('Usage : ' + script_name + ' solver solver-parameters cnfs-folder [Options]')
  print('  Options :\n' +\
  '  -defobj=<float>        - (default : -1)    objective funtion value for the default point' + '\n' +\
  '  -maxpoints=<int>       - (default : 1000)  maximum number of points to process' + '\n' +\
  '  -maxtime=<int>         - (default : 86400) maximum script wall time' + '\n' +\
  '  -maxsolvertime=<int>   - (default : -1)    maximum SAT solver runtime' + '\n' +\
  '  -pointsfile=<string>   - (default : "")    path to a file with points' + '\n' +\
  '  -origpcsfile=<string>  - (default : "")    path to the original parameters file' + '\n' +\
  '  -cpunum=<int>          - (default : 1)     number of used CPU cores' + '\n' +\
  '  -seed=<int>            - (default : 0)     seed for pseudorandom generator' + '\n' +\
  '  --solving              - (default : off)   solving mode' + '\n\n' +\
  'Points from the -pointsfile are used along with those which are generated.')

# Input options:
class Options:
	def_point_time = -1
	max_points = 1000
	max_time = -1
	max_solver_time = -1
	points_file = ''
	defpcs_file = ''
	cpu_num = 1
	seed = 0
	is_solving = False
	def __init__(self):
		self.def_point_time = -1
		self.max_points = 1000
		self.max_time = 86400
		self.max_solver_time = -1
		self.points_file = ''
		self.origpcs_file = ''
		self.cpu_num = 1
		self.seed = 0
		self.is_solving = False
	def __str__(self):
		s = 'def_point_time  : ' + str(self.def_point_time) + '\n' +\
		'max_points      : ' + str(self.max_points) + '\n' +\
		'max_time        : ' + str(self.max_time) + '\n' +\
		'max_solver_time : ' + str(self.max_solver_time) + '\n' +\
		'points_file     : ' + str(self.points_file) + '\n' +\
		'origpcs_file    : ' + str(self.origpcs_file) + '\n' +\
		'cpu_num         : ' + str(self.cpu_num) + '\n' +\
		'seed            : ' + str(self.seed) + '\n' +\
		'is_solving      : ' + str(self.is_solving)
		return s
	def read(self, argv) :
		for p in argv:
			if '-defobj=' in p:
				self.def_point_time = math.ceil(float(p.split('-defobj=')[1]))
			if '-maxpoints=' in p:
				self.max_points = math.ceil(float(p.split('-maxpoints=')[1]))
			if '-maxtime=' in p:
				self.max_time = math.ceil(float(p.split('-maxtime=')[1]))
			if '-maxsolvertime=' in p:
				self.max_solver_time = math.ceil(float(p.split('-maxsolvertime=')[1]))
			if '-pointsfile=' in p:
				self.points_file = p.split('-pointsfile=')[1]
			if '-origpcsfile=' in p:
				self.origpcs_file = p.split('-origpcsfile=')[1]
			if '-cpunum=' in p:
				self.cpu_num = int(p.split('-cpunum=')[1])
			if '-seed=' in p:
				self.seed = int(p.split('-seed=')[1])
			if p == '--solving':
				self.is_solving = True
		assert(self.max_points > 0 and self.cpu_num > 0)

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
      #print(line)
      words = line.strip().split(' ')
      assert(len(words) > 2)
      #print(words)
      prm = Param()
      prm.name = words[0]
      defstr = line.split('[')[1].split(']')[0]
      prm.default = convert_if_int(defstr)
      valuesstr = line.split('{')[1].split('}')[0].replace(' ', '')
      lst = valuesstr.split(',')
      #print(lst)
      for x in lst:
          prm.values.append(convert_if_int(x))
      assert(len(prm.values) > 1)
      assert(prm.default in ['true', 'false'] or isinstance(prm.default, int))
      #print(str(len(prm.values)))
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
  assert(len(point) == len(params))
  assert(points_num >= 0)
  global random
  global generated_points_strings
  global def_point
  global skipped_repeat_num
  global skipped_impos_num
  if points_num == 0:
    return []
  new_points = []
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
    if strlistrepr(pnt) in generated_points_strings:
      skipped_repeat_num += 1
      #print(str(skipped_repeat_num) + ' repeated points skipped')
    else:
      # New point and possible combination:
      generated_points_strings.add(strlistrepr(pnt))
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
def calc_obj(solver_name : str, sum_time : float, \
  max_instance_time_best_point : float,  cnfs : list, \
  params : list, point : list, is_solving : bool):
  assert(len(params) > 1)
  assert(len(params) == len(point))
  assert(len(cnfs) > 0)
  par10_time = 0.0
  max_time = -1
  is_all_sat = True
  # Solver's time limit on each CNF is the current best obj func value:
  if max_instance_time_best_point > 0:
    solver_time_lim = max_instance_time_best_point
  else:
    solver_time_lim = sum_time
  print('solver_time_lim : ' + str(solver_time_lim))
  # Calculate PAR10 for the solver runtimes: sum(time if solved in lim seconds,
  # otherwise lim*10)
  cnf_num = 0
  sat_num = 0
  for cnf_file_name in cnfs:
    cnf_num += 1
    sys_str = ''
    if solver_time_lim > 0:
      sys_str = solver_name + ' --time=' + str(math.ceil(solver_time_lim)) + ' '
    else:
      sys_str = solver_name + ' '
    for i in range(len(params)):
      sys_str += '--' + params[i].name + '=' + str(point[i]) + ' '
    sys_str += cnf_file_name
    #print(sys_str)
    cdcl_log = os.popen(sys_str).read()
    t, sat = parse_cdcl_result(cdcl_log)
    assert(t > 0)
    assert(sat == -1 or sat == 1)
    if sat == 1:
       sat_num += 1
    if sat == -1 or (solver_time_lim > 0 and t >= solver_time_lim):
      par10_time += solver_time_lim * 10
    else:
      assert(sat == 1) # SAT should be here
      # Only if a CNF is solved in time limit:
      par10_time += t
      max_time = t if max_time < t else max_time
      print('Time : ' + str(t) + ' on CNF ' + cnf_file_name)
      # In solving mode, the CDCL solver's log should be saved:
      if is_solving:
        assert('.cnf' in cnf_file_name)
        cdcl_log_file_name = 'log_' + solver_name.replace('./','') + '_' + os.path.basename(cnf_file_name.split('.cnf')[0])
        now = datetime.now()
        cdcl_log_file_name += '_' + now.strftime("%d-%m-%Y_%H-%M-%S")
        print('Writing CDCL solver log to file ' + cdcl_log_file_name)
        with open(cdcl_log_file_name, 'w') as f:
          f.write(cdcl_log)
    # If current value is already worse than the best one:
    print('sum_time : ' + str(sum_time))
    print('par10_time : ' + str(par10_time))
    if sum_time > 0 and par10_time >= sum_time:
      print('Current value ' + str(par10_time) + ' is already worse than ' + str(sum_time))
      print('Break after processing ' + str(cnf_num) + ' CNFs out of ' + str(len(cnfs)))
      break
  is_all_sat = False
  if sat_num == len(cnfs):
     is_all_sat = True
  #print('PAR10 in calc_obj : ' + str(par10_time))
  return point, par10_time, max_time, is_all_sat, sys_str

# Collect a result produced by solver:
def collect_result(res):
  global updates_num
  global best_sum_time
  global best_point
  global best_command
  global max_instance_time_best_point
  global def_point
  global params
  global processed_points_num
  global start_time
  global is_updated
  assert(len(res) == 5)
  point = res[0]
  par10_time = res[1]
  max_time = res[2]
  is_all_sat = res[3]
  command = res[4]
  print('PAR10 time in collect_result : ' + str(par10_time) + ' seconds')
  print('max_time : ' + str(max_time) + ' seconds')
  # If a new record point is found:
  if is_all_sat == True and (par10_time < best_sum_time or best_sum_time <= 0):
    is_updated = True
    updates_num += 1
    best_sum_time = par10_time
    best_point = copy.deepcopy(point)
    best_command = command
    max_instance_time_best_point = max_time
    elapsed_time = round(time.time() - start_time, 2)
    print('\nUpdated best sum time : ' + str(best_sum_time))
    print('max_instance_time_best_point : ' + str(max_instance_time_best_point))
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
  out_name = 'generated_points'
  #cleared_cnfs = []
  #for x in cnfs:
    #assert('.cnf' in x)
    #out_name += os.path.basename(x.split('.cnf')[0])
    #if x != cnfs[-1]:
    #  out_name += '_'
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
        if param_name in paramsdict:
          value = convert_if_int(word.split('=')[1])
          point[paramsdict[param_name]] = value
      assert(len(point) == len(def_point))
      given_points.append(point)
  return given_points

# Write final best point as a pcs file:
def write_final_pcs(best_point : list, params : list, cnfs : list):
  assert(len(best_point) == len(params))
  outname = 'final_best.pcs'
  #for x in cnfs:
    #assert('.cnf' in x)
    #outname += os.path.basename(x.split('.cnf')[0])
    #if x != cnfs[-1]:
      #outname += '_'
  #outname += '.pcs'
  with open(outname, 'w') as ofile:
    for i in range(len(best_point)):
      ofile.write(params[i].name + ' {')
      for v in params[i].values[:-1]:
        ofile.write(str(v) + ', ')
      ofile.write(str(params[i].values[-1]) + '}')
      ofile.write('[' + str(best_point[i]) + ']\n')

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

  def_point = list()
  total_val_num = 0
  for prm in params:
    total_val_num += len(prm.values)
    def_point.append(prm.default)
  print(str(total_val_num) + ' values in all parameters')
  assert(total_val_num > 0)
  assert(len(def_point) == len(params))
  print('Default point :')
  print(str(def_point))

  # Read original parameters if given:
  orig_params = []
  orig_point = []
  if op.origpcs_file != '':
    orig_params = read_pcs(op.origpcs_file)
    orig_val_num = 0
    for prm in orig_params:
      orig_val_num += len(prm.values)
      orig_point.append(prm.default)
    print(str(orig_val_num) + ' values in original parameters')
    assert(orig_val_num > 0)
    assert(orig_val_num == total_val_num)
    assert(len(orig_point) == len(params))
    print('Original point :')
    print(str(orig_point))

  total_val_num = 0
  print(str(len(params)) + ' parameters')

  paramsdict = dict()
  for i in range(len(params)):
    paramsdict[params[i].name] = i
  print('DictionaryA of parameters :')
  print(paramsdict)  

  # Read points which are given in a text file:
  given_points = read_points(op.points_file, def_point, paramsdict)
  print(str(len(given_points)) + " points are given in a file :")
  for p in given_points:
    print(str(p))
  print('')

  cnfs = []
  cnfs = read_cnfs(cnfs_folder_name)
  assert(len(cnfs) > 0)
  print(str(len(cnfs)) + ' CNFs were read :')
  for cnf in cnfs:
    print(cnf)

  best_point = copy.deepcopy(def_point)
  # Command for default point:
  best_command = solver_name + ' ' + cnfs[0]

  default_sum_time = op.def_point_time
  best_sum_time = op.def_point_time
  print('Current best sum time : ' + str(best_sum_time))

  elapsed_time = round(time.time() - start_time, 2)
  print('Elapsed : ' + str(elapsed_time) + ' seconds')

  processed_points_num = 0
  generated_points_strings = set()
  start_points = []

  
  start_points.append(def_point)
  # In runtime on default point is given, mark it as generated and processed:
  if default_sum_time > 0:
    processed_points_num = 1 # the default point is processed
    assert(len(generated_points_strings) == 1)
    assert(default_sum_time > 0)
  # If default point's runtime is not given, generate default points:
  else:
    assert(default_sum_time == -1)
    print('Runtime for default point is not given, process it:')
    print(str(def_point))
    # SAT point, i.e. --target=2 --restartint=50:
    sat_point = copy.deepcopy(def_point)
    sat_point[paramsdict['target']] = 2
    sat_point[paramsdict['restartint']] = 50
    assert(len(sat_point) == len(params))
    if (sat_point not in start_points):
      start_points.append(sat_point)
      print('... and SAT-params point :')
      print(str(sat_point))
    else:
      print('SAT-point already exists')
    if len(orig_point) > 0:
      # Original default point:
      if orig_point not in start_points:
        start_points.append(orig_point)
        print('... and original default point :')
        print(str(orig_point))
      else:
        print('orig-point already exists')
      # original SAT point, i.e. orig with --target=2 --restartint=50:
      sat_orig_point = copy.deepcopy(orig_point)
      sat_orig_point[paramsdict['target']] = 2
      sat_orig_point[paramsdict['restartint']] = 50
      assert(len(sat_orig_point) == len(orig_params))
      if (sat_orig_point not in start_points):
        start_points.append(sat_orig_point)
        print('... and SAT-orig-params point :')
        print(str(sat_orig_point))
      else:
        print('SAT-point already exists')
  
  if op.cpu_num < len(start_points):
    start_points = start_points[:op.cpu_num]
    print('start_points was reduced to ' + str(len(start_points)))

  skipped_repeat_num = 0
  skipped_impos_num = 0
  updates_num = 0
  iter = 0
  max_instance_time_best_point = op.max_solver_time
  is_extern_break = False
  elapsed_time = 0

  # Repeat until all points a processed:
  while processed_points_num < op.max_points and elapsed_time < op.max_time:
    print('\n*** iter : ' + str(iter))
    elapsed_time = round(time.time() - start_time, 2)
    print('elapsed : ' + str(elapsed_time) + ' seconds')
    points_to_process = []
    if best_sum_time == -1:
      assert(iter == 0)
      # Only def and sat points:
      assert(len(start_points) <= 4)
      for p in start_points:
        assert(len(p) == len(params))
        points_to_process.append(p)
        generated_points_strings.add(strlistrepr(p))
    oneplusone_points = oneplusone(best_point, params, paramsdict, op.cpu_num - len(points_to_process))
    print('Generated ' + str(len(oneplusone_points)) + ' oneplusone points')
    for p in oneplusone_points:
       assert(len(p) == len(params))
       points_to_process.append(p)
    assert(len(points_to_process) == op.cpu_num)
    pool = mp.Pool(op.cpu_num)
    for p in points_to_process:
      assert(len(p) == len(params))
      pool.apply_async(calc_obj, args=(solver_name, best_sum_time, max_instance_time_best_point, cnfs, params, p, op.is_solving), callback=collect_result)
    is_updated = False
    is_inner_break = False
    # Repeat until a new record is found or the processed points limit is reached:
    while True:
      while len(pool._cache) >= op.cpu_num: # wait until any CPU core is free
        time.sleep(1)
      processed_points_num += 1
      print('processed_points_num : ' + str(processed_points_num))
      elapsed_time = round(time.time() - start_time, 2)
      print('elapsed : ' + str(elapsed_time) + ' seconds')
      if processed_points_num >= op.max_points:
        print('The limit on the number of points is reached, break.')
        is_inner_break = True
      elif elapsed_time >= op.max_time:
        print('The time limit is reached, break.')
        is_inner_break = True
      if is_updated:
        assert(best_sum_time > 0)
        if op.is_solving:
          # 1 solution is enough in the solving mode:
          print('Breaking the main loop because a solution is found in the solving mode.')
          assert(iter == 0)
          is_extern_break = True
        is_updated = False
        is_inner_break = True
      if is_inner_break:
        print('Break inner loop.')
        kill_solver(solver_name, len(cnfs))
        time.sleep(1)
        assert(len(pool._cache) == 0)
        assert(len(points_to_process) == op.cpu_num)
        processed_points_num += op.cpu_num - 1
        print('processed_points_num : ' + str(processed_points_num))
        pool.close()
        pool.join()
        break
      # A CPU core is free, so generate a new point and process it:
      one_point_list = oneplusone(best_point, params, paramsdict, 1)
      assert(len(one_point_list) == 1)
      pool.apply_async(calc_obj, args=(solver_name, best_sum_time, max_instance_time_best_point, cnfs, params, one_point_list[0], op.is_solving), callback=collect_result)
    if is_extern_break:
       print('Break main loop')
       break
    iter += 1

  # Write generated points:
  write_points(generated_points_strings, cnfs)

  # Write final pcs file:
  write_final_pcs(best_point, params, cnfs)

  # Print statistics:
  elapsed_time = round(time.time() - start_time, 2)
  print('\nElapsed : ' + str(elapsed_time) + ' seconds')
  print(str(iter) + ' iterations')
  print(str(updates_num) + " updates of best point")
  print(str(skipped_repeat_num + skipped_impos_num) + ' skipped points, of them:')
  print('  ' + str(skipped_repeat_num ) + ' repeated points')
  print('  ' + str(skipped_impos_num) + ' impossible-combination points')
  print(str(len(generated_points_strings)) + ' generated points')
  print(str(processed_points_num) + ' processed points')
  print('Final best sum time : ' + str(best_sum_time) + ' , so ' + \
    str(default_sum_time) + ' -> ' + str(best_sum_time))
  if updates_num > 0:
    print(points_diff(def_point, best_point, params))
  print('Final best command : \n' + best_command)
