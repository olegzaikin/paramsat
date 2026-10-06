# Created on: 11 Jan 2022
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Given a SAT solver's input parameters and a CNF, find a better set of
# parameters' values via blackbox optimization algorithms.
#
# Example:
#   python3 ./bbo_param_solver.py ./kissat4 ./kissat4.pcs ./cnfs/ -seed=1
# 
# By default the script works in the estimating mode, where new points are generated
# and processed until a stopping criterion is reached.
#========================================================================================
#
# TODOs:
# 0. Extend to unsatisfiable CNFs.
# 1. Parallel version

script_name = "bbo_param_solver.py"
version = '0.13.3'

# A penalty coefficient for interrupted points:
BOUND_MULTIPLIER = 2
PENALTY_INTERR_CNF = 10 # PAR10 as in ParamILS and SMAC

import sys
import glob
import os
import time
import random
import copy
import math
import string
import subprocess
from enum import Enum
from datetime import datetime
import numpy as np
from skopt import Optimizer
from skopt.space import Categorical

skt_opt = None

optalg_indices = {
    "1+1" : 0,
    "SKOPT-GP" : 1, 
    "SKOPT-RF" : 2, 
    "SKOPT-ET" : 3, 
    "SKOPT-GBRT" : 4
}

class PointStatus(Enum):
    GENERATED = 0 # a point is generated
    STARTED = 1 # a point is generated and the calculation is started on it
    FINISHED = 2 # a point is calculated on all instances
    INTERRUPTED = 3 # a point is calculated, but on at least one instance the SAT solver was interrupted

# Input options:
class Options:
	solver_name = ''
	opt_alg = "1+1"
	def_point_time = -1
	max_points = 1000
	max_wall_time = -1
	max_solver_time = -1
	defpcs_file = ''
	seed = 0
	is_solving = False
	def __init__(self):
		self.def_point_time = -1
		self.max_points = 1000
		self.max_wall_time = 86400
		self.max_solver_time = -1
		self.seed = 0
		self.is_solving = False
	def __str__(self):
		assert(len(self.opt_alg) > 0)
		s = '' +\
    'solver_name     : ' + self.solver_name + '\n' +\
    'opt_alg         : ' + self.opt_alg + '\n' +\
    'def_point_time  : ' + str(self.def_point_time) + '\n' +\
		'max_points      : ' + str(self.max_points) + '\n' +\
		'max_wall_time   : ' + str(self.max_wall_time) + '\n' +\
		'max_solver_time : ' + str(self.max_solver_time) + '\n' +\
		'seed            : ' + str(self.seed) + '\n' +\
		'is_solving      : ' + str(self.is_solving)
		return s
	def read(self, argv) :
		for p in argv:
			if '-optalg=' in p:
				tmp = p.split('-optalg=')[1]
				tmp = tmp.replace("'", "")
				self.opt_alg = tmp.replace('"', '')
				assert(self.opt_alg in ["1+1", "SKOPT-GP", "SKOPT-RF", "SKOPT-ET", "SKOPT-GBRT"])
			if '-defobj=' in p:
				self.def_point_time = math.ceil(float(p.split('-defobj=')[1]))
			if '-maxpoints=' in p:
				self.max_points = math.ceil(float(p.split('-maxpoints=')[1]))
			if '-maxtime=' in p:
				self.max_wall_time = math.ceil(float(p.split('-maxtime=')[1]))
			if '-maxsolvertime=' in p:
				self.max_solver_time = math.ceil(float(p.split('-maxsolvertime=')[1]))
			if '-seed=' in p:
				self.seed = int(p.split('-seed=')[1])
			if p == '--solving':
				self.is_solving = True
		assert(self.max_points > 0)
		assert(self.max_wall_time > 0)

# Solver's parameter:
class Param:
  name : str
  default : int
  values : list
  def __init__(self):
    self.name = ''
    self.default = -1
    self.values = []

def print_usage():
  print('Usage : ' + script_name + ' solver solver-parameters cnfs-dir [Options]')
  print('  Options :\n' +\
  '  -optalg=["1+1", "SKOPT-GP", "SKOPT-RF", "SKOPT-ET", "SKOPT-GBRT"] - (default : "1+1") type of optimization algorithm' + '\n' +\
  '  -defobj=<float>        - (default : -1)    objective funtion value for the default point' + '\n' +\
  '  -maxpoints=<int>       - (default : 1000)  maximum number of points to process' + '\n' +\
  '  -maxtime=<int>         - (default : 86400) maximum script wall time' + '\n' +\
  '  -maxsolvertime=<int>   - (default : -1)    maximum SAT solver runtime' + '\n' +\
  '  -seed=<int>            - (default : 0)     seed for pseudorandom generator' + '\n' +\
  '  --solving              - (default : off)   solving mode' + '\n' +\
  'NB: Points from the -pointsfile are used along with those which are generated.')


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
	t = 0
	sat = -1
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
	if t <= 0:
		print('WARNING. Invalid solver output:')
		print(cdcl_log)
	assert(t >= 0)
	return t, sat


# Kill a solver:
def kill_solver(solver_name : str):
  assert(solver_name != '')
  # Form a command line to kill all solver species:
  print('Killing solver ' + solver_name)
  sys_str = 'killall -9 ' + solver_name.replace('./','')
  subprocess.run(sys_str, shell=True)
  time.sleep(1)


# Create a copy of a given solver to kill the latter safely:
def create_solver_copy(solver_name : str, random_str : str):
  new_solver_name = solver_name + '_' + random_str
  print("Creating solver " + new_solver_name)
  sys_str = 'cp ' + solver_name + ' ' + new_solver_name
  subprocess.run(sys_str, shell=True)
  return new_solver_name


# Randomly choose an element from a given list except given current value.
# The closer index is to the given one, the higher probability is to be chosen.
def next_value(lst : list, cur_val : int):
  indx = lst.index(cur_val)
  assert(indx >= 0 and indx < len(lst))
  weights = [0 for _ in lst]
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


# Generate new points via (1+1)-EA or ask-tell interface:
def ask_points(skt_opt, points_num_to_gen : int):
  global random
  global def_point
  global skipped_points_num
  global generated_points
  global params
  global paramsdict
  global op
  global best_point
  assert(len(best_point) == len(params))
  assert(points_num_to_gen >= 0)
  if points_num_to_gen == 0:
    return []
  new_points = []
  if op.opt_alg == "1+1":
     # Change each value with probability:
    while len(new_points) < points_num_to_gen:
        pnt = copy.deepcopy(best_point)
        # With probability 36 % the point is the same, so do until it is a new one:
        while pnt == best_point:
          for i in range(len(params)):
            prob = random.random()
            if (prob <= 1/len(params)):
              pnt[i] = next_value(params[i].values, pnt[i])
        assert(pnt != best_point)
        point_tuple = tuple(pnt)
        # If point has been already generated:
        if point_tuple in generated_points:
          # The calculation is finished or the point is just generated:
          skipped_points_num += 1
          #print(str(skipped_points_num) + ' repeated points skipped')
        else:
          # New point and possible combination:
          generated_points[point_tuple] = PointStatus.GENERATED
          new_points.append(pnt)
  elif op.opt_alg != "1+1": # "SKOPT-GP", "SKOPT-RF", "SKOPT-ET", "SKOPT-GBRT"
    new_points_npint64 = skt_opt.ask(n_points=points_num_to_gen)
    #print(generated_points)
    #print(new_points_npint64)
    assert(len(new_points_npint64) == points_num_to_gen)
    new_points = []
    # Convert from numpy in64 to int:
    for p in new_points_npint64:
      new_points.append([int(x) for x in p])
    for p in new_points:
      assert(p != best_point)
      point_tuple = tuple(p)
      # Each ask must be completed by tell, so no same points:
      assert(point_tuple not in generated_points)
      generated_points[point_tuple] = PointStatus.GENERATED
    #
  return new_points


# Difference between two given points (empty string if equal points):
def points_diff(p1 : list, p2 : list, params : list):
  assert(len(p1) == len(p2))
  assert(len(p1) == len(params))
  res_str = ''
  if p1 != p2:
    for i in range(len(p1)):
      if p1[i] != p2[i]:
        res_str += '  ' + params[i].name + ' : ' + str(p1[i]) + \
          ' -> ' + str(p2[i]) + '\n'
    res_str = res_str[:-1]  
  return res_str


# Calc objective function and process results:
def calc_obj_collect_result(point : list):
    res = calc_obj(point)
    collect_result(res)


# Run solver on a given point:
def calc_obj(point : list):
  global op
  global params
  global start_time
  global generated_points
  assert(len(params) > 1)
  assert(len(params) == len(point))
  assert(len(cnfs) > 0)
  assert(len(op.solver_name) > 0)
  # A point to calculate must be marked as GENERATED:
  tuple_point = tuple(point)
  assert(generated_points[tuple_point] == PointStatus.GENERATED)
  # Mark that the calculation is STARTED:
  generated_points[tuple_point] = PointStatus.STARTED
  cur_sum_time = 0.0
  max_instance_time = -1
  # Calculate sum for the solver runtimes:
  sat_num = 0
  sys_str = ''
  assert(op.max_solver_time <= op.max_wall_time)
  # Calculate a basic time limit for the solver:
  solver_time_lim = op.max_wall_time
  if op.max_solver_time > 0:
    assert(op.max_solver_time < op.max_wall_time)
    solver_time_lim = op.max_solver_time
  # Process each CNF from the sample:
  cnf_num = 0
  is_interrupted_point = False
  for cnf_file_name in cnfs:
    assert('.cnf' in cnf_file_name)
    cnf_num += 1
    sys_str = ''
    # If any current best sum time is known, additionally limit the solver;
    # give it t+1 seconds where t is time for reaching the current best sum time:
    if best_sum_time > 0:
       elapsed_time_best_sum_time = best_sum_time - cur_sum_time
       if elapsed_time_best_sum_time < solver_time_lim:
          solver_time_lim = elapsed_time_best_sum_time
    # Check the left time:
    elapsed_time = round(time.time() - start_time, 2)
    avail_time = op.max_wall_time - elapsed_time
    # If no time is left, do not run the solver:
    t, sat = 0, 1
    cdcl_log = ''
    # Enough time, run the solver:
    if avail_time > 0:
      # Update the solver limit to not exceed the wall limit:
      if avail_time < solver_time_lim:
        solver_time_lim = avail_time
      assert(solver_time_lim > 0)
      rounded_solver_time_lim = math.ceil(solver_time_lim)
      assert(rounded_solver_time_lim > 0)
      sys_str = op.solver_name + ' --time=' + str(rounded_solver_time_lim) + ' '
      for i in range(len(params)):
        sys_str += '--' + params[i].name + '=' + str(point[i]) + ' '
      sys_str += cnf_file_name
      #print(sys_str)
      cdcl_log = subprocess.run(sys_str, shell=True, capture_output=True, text=True).stdout
      t, sat = parse_cdcl_result(cdcl_log)
    assert(t >= 0)
    # Expect SAT or INTERR, while UNSAT is not a valid answer: 
    assert(sat == -1 or sat == 1)
    # If the solver is interrupted at least once,
    if sat == -1 or (solver_time_lim > 0 and t >= solver_time_lim):
      # PAR10 penalty for an interrupted CNF:
      t = op.max_solver_time * PENALTY_INTERR_CNF 
    else:
      assert(sat == 1) # SAT should be here
      sat_num += 1
      max_instance_time = t if max_instance_time < t else max_instance_time
      #print('Time : ' + str(t) + ' on CNF ' + cnf_file_name)
      # In solving mode, the CDCL solver's log should be saved for each CNF:
      if op.is_solving:
        cdcl_log_file_name = 'log_' + op.solver_name.replace('./','') + '_' + os.path.basename(cnf_file_name.split('.cnf')[0])
        now = datetime.now()
        cdcl_log_file_name += '_' + now.strftime("%d-%m-%Y_%H-%M-%S")
        print('Writing CDCL solver log to file ' + cdcl_log_file_name)
        with open(cdcl_log_file_name, 'w') as f:
          f.write(cdcl_log)
    # SAT or interrupted, add the time:
    cur_sum_time += t
    # If at least one CNF is not yet processed:
    if cnf_num < len(cnfs):
      # If the current value is already worse than the best one
      if best_sum_time > 0 and cur_sum_time >= best_sum_time * BOUND_MULTIPLIER:
        print('Current obj func value ' + str(cur_sum_time) + ' is already worse than ' + \
              str(BOUND_MULTIPLIER) + 'x ' + str(best_sum_time))
        print('Break after processing ' + str(cnf_num) + ' CNFs out of ' + str(len(cnfs)))
        is_interrupted_point = True
        break
      elapsed_time = round(time.time() - start_time, 2)
      # If time limit for the script is reached:
      if elapsed_time >= op.max_wall_time:
        print('Wall time limit is reached while calculating objective function')
        print('Break after processing ' + str(cnf_num) + ' CNFs out of ' + str(len(cnfs)))
        is_interrupted_point = True
        break
  # end of loop 'for cnf_file_name in cnfs'
  #print('Obj func value : ' + str(cur_sum_time))
  return point, cur_sum_time, max_instance_time, sys_str, is_interrupted_point

# Collect a result produced by solver:
def collect_result(res : tuple):
  global def_point
  global default_sum_time
  global max_instance_time_best_point
  global best_sum_time
  global best_point
  global best_command
  global updates_num
  global params
  global start_time
  global is_updated
  global generated_points
  global op 
  global skt_opt
  global cnfs_num
  global worse_than_best_but_calc_points_num

  point = res[0]
  cur_sum_time = res[1]
  max_instance_time = res[2]
  command = res[3]
  is_interrupted_point = res[4]

  assert(cnfs_num > 0)
  # If interrupted, then not all instances are satisfiable:
  assert(cur_sum_time >= 0)
  #print('Sum time in collect_result : ' + str(cur_sum_time) + ' seconds')
  #print('max_wall_time : ' + str(max_wall_time) + ' seconds')
  tuple_point = tuple(point)
  assert(generated_points[tuple_point] == PointStatus.STARTED)
  finished_points_num = finished(generated_points)
  interrupted_points_num = interrupted(generated_points)
  elapsed_sec = time.time() - start_time
  s = str(finished_points_num) + ' finished points, ' + str(interrupted_points_num) + ' interrupted points, ' + \
    'elapsed ' + str(elapsed_sec)
  print(s)
  # If a new record point is found:
  if cur_sum_time > 0 and (cur_sum_time < best_sum_time or best_sum_time <= 0):
    is_updated = True
    updates_num += 1
    best_sum_time = cur_sum_time
    best_point = copy.deepcopy(point)
    best_command = command
    max_instance_time_best_point = max_instance_time
    elapsed_time = round(time.time() - start_time, 2)
    print('*** Updated best sum time : ' + str(best_sum_time))
    print('max_instance_time_best_point : ' + str(max_instance_time_best_point))
    print('elapsed : ' + str(elapsed_time) + ' seconds')
    print(best_command + '\n')
    if def_point == best_point:
      print('The new record point is the default one')
      if default_sum_time == -1:
        default_sum_time = best_sum_time
    else:
      diff_str = points_diff(def_point, best_point, params)
      assert(diff_str != '')
      print('Difference from the default point :')
      print(diff_str + '\n')
  # Calculate a 2 x cur-best-time penalty for interuupted points as in ParamILS and SMAC:
  assert(best_sum_time > 0)
  # Two cases:
  # 1) The point is calculated, and the point is marked STARTED, so STARTED -> FINISHED
  # 2) A point is interrupted, so STARTED -> INTERRUPTED
  tell_time = cur_sum_time
  if is_interrupted_point == False:
    assert(cur_sum_time > 0)
    generated_points[tuple_point] = PointStatus.FINISHED
    if cur_sum_time > best_sum_time:
       worse_than_best_but_calc_points_num += 1
    print('Finished point with sum_time ' + str(cur_sum_time) + ' , max_inst_time ' + str(max_instance_time))
  else:
    penalty_sum_time = best_sum_time * BOUND_MULTIPLIER
    tell_time = penalty_sum_time
    assert(penalty_sum_time > 0)
    generated_points[tuple_point] = PointStatus.INTERRUPTED
  # Tell SKOPT the objective function value:
  if 'SKOPT-' in op.opt_alg:
    res = skt_opt.tell(point, tell_time)


# Read all CNFs in a given dir:
def read_cnfs(cnfs_dir_name : str):
  cnfs = list()
  os.chdir('.')
  for f in glob.glob(cnfs_dir_name + '/*.cnf'):
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
def write_points(points : dict, cnfs : list):
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


def processed(generated_points : dict):
  res = 0
  for point_tuple in generated_points:
     if generated_points[point_tuple] == PointStatus.FINISHED or \
     generated_points[point_tuple] == PointStatus.INTERRUPTED:
        res += 1
  return res


def finished(generated_points : dict):
  res = 0
  for point_tuple in generated_points:
     if generated_points[point_tuple] == PointStatus.FINISHED:
        res += 1
  return res


def interrupted(generated_points : dict):
  res = 0
  for point_tuple in generated_points:
     if generated_points[point_tuple] == PointStatus.INTERRUPTED:
        res += 1
  return res


def stat(generated_points : dict):
  res = ''
  generated_num = 0
  started_num = 0
  finished_num = 0
  interrupted_num = 0
  for point_tuple in generated_points:
      if generated_points[point_tuple] == PointStatus.GENERATED:
         generated_num += 1
      elif generated_points[point_tuple] == PointStatus.STARTED:
         started_num += 1
      elif generated_points[point_tuple] == PointStatus.FINISHED:
         finished_num += 1
      elif generated_points[point_tuple] == PointStatus.INTERRUPTED:
         interrupted_num += 1
  res = str(generated_num) + ' only generated\n' + \
    str(started_num) + ' started\n' + \
    str(finished_num) + ' finished\n' + \
    str(interrupted_num) + ' interrupted\n'
  return res


# Main function:
if __name__ == '__main__':
  if len(sys.argv) < 4:
    print_usage()
    exit(1)

  print('Running script ' + script_name + ' of version ' + version)

  start_time = time.time()

  # Solver name is taken from argv[1] inside Options read():
  solver_name = sys.argv[1]
  param_file_name = sys.argv[2]
  cnfs_dir_name = sys.argv[3]

  print('solver_name      : ' + solver_name)
  print('param_file_name  : ' + param_file_name)
  print('cnfs_dir_name    : ' + cnfs_dir_name)

  op = Options()
  op.read(sys.argv[3:])
  print(op)

  # Force the seed depend on wall time and number of CPU cores.
  # + 1 is needed to avoid multiplying by 0 if the base seed is 0.
  seed = (op.seed + 1) * op.max_wall_time + optalg_indices[op.opt_alg]
  random.seed(seed)
  print('Seed ' + str(seed) + ' is formed on the base of initial seed ' + str(op.seed) )
  random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 10))    
  print("The randomly generated string is : " + str(random_str))
  assert(len(solver_name) > 0)
  new_solver_name = create_solver_copy(solver_name, random_str)
  print('Solver name is changed to ' + new_solver_name)
  op.solver_name = new_solver_name
  # Make this string empty to use only solver name from Options:
  solver_name = ''

  params = read_pcs(param_file_name)

  # Form a default point:
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
  # Form a dictionary of parameters' indices:
  total_val_num = 0
  print(str(len(params)) + ' parameters')
  paramsdict = dict()
  for i in range(len(params)):
    paramsdict[params[i].name] = i
  print('Dictionary of parameters :')
  print(paramsdict)  

  # Read CNFs:
  cnfs = []
  cnfs = read_cnfs(cnfs_dir_name)
  cnfs_num = len(cnfs)
  assert(len(cnfs) > 0)
  print(str(len(cnfs)) + ' CNFs were read :')
  for cnf in cnfs:
    print(cnf)

  best_point = copy.deepcopy(def_point)
  # Command for default point:
  best_command = op.solver_name + ' ' + cnfs[0]

  default_sum_time = op.def_point_time
  best_sum_time = op.def_point_time
  print('Current best sum time : ' + str(best_sum_time))

  elapsed_time = round(time.time() - start_time, 2)
  print('Elapsed : ' + str(elapsed_time) + ' seconds')

  # Initialize sktopt optimizer if needed:
  if op.opt_alg == "1+1":
     BOUND_MULTIPLIER = 1
  elif op.opt_alg != "1+1":
     BOUND_MULTIPLIER = 2 # worse points are needed for surrogate models
     skt_opt_space=[]
     # space.append(Integer(0, 10, name='x2'))
     for param in params:
        skt_opt_space.append(Categorical(param.values, name=param.name))
     estimator_type = op.opt_alg
     print('sktopt estimator type : ' + estimator_type)
     # As recommended, the number of initial points is d+1, where d is the number of variables:
     init_points_num = len(params) + 1
     print('init_points_num : ' + str(init_points_num))
     skt_opt = Optimizer(skt_opt_space, base_estimator=estimator_type.replace('SKOPT-', ''), n_initial_points=init_points_num, random_state=seed)

  print('BOUND_MULTIPLIER : ' + str(BOUND_MULTIPLIER))

  updates_num = 0
  max_instance_time_best_point = -1

  # A dictionary of generated points, where a tuple representation of the
  # point's parameters values is an ID, while the VALUE is a point's status:
  generated_points = dict()
  # If runtime on default point is given, mark it as finished:
  point_tuple = tuple(def_point)
  # If time for default point is given, update penalty sum time:
  if default_sum_time > 0:
    generated_points[point_tuple] = PointStatus.FINISHED
    print('The default point is given, so it is marked as finished.')
    assert(op.max_solver_time > 0)
  else:
    # otherwise, add the default point to the queue for processing:
    generated_points[point_tuple] = PointStatus.GENERATED
    print('Calculating objective function in the default point')
    calc_obj_collect_result(def_point)
    assert(max_instance_time_best_point > 0)
    assert(max_instance_time_best_point < op.max_wall_time)

  # If maximum solver time is not set, assing what is available:
  if op.max_solver_time < 0:
    if max_instance_time_best_point > 0:
      op.max_solver_time = max_instance_time_best_point
    else:
      op.max_solver_time = op.max_wall_time
  print('max_solver_time is not set, so it was changed to ' + str(op.max_solver_time))

  assert(len(generated_points) == 1)
  assert(op.max_solver_time > 0)

  skipped_points_num = 0
  prev_processed_points_num = 0
  worse_than_best_but_calc_points_num = 0
  processed_points_num = 0
  iter = 1 # iter 0 is the default point
  elapsed_time = 0
  print('*** iter 0 was spent on the default point')

  # Repeat until all points are processed:
  while processed_points_num < op.max_points and elapsed_time < op.max_wall_time:
    print('*** iter : ' + str(iter))
    elapsed_time = round(time.time() - start_time, 2)
    print('elapsed : ' + str(elapsed_time) + ' seconds')
    # Ask for a new point:
    points_to_process = ask_points(skt_opt, 1)
    assert(len(points_to_process) == 1)
    is_updated = False
    # Check the point's status:
    tuple_point = tuple(points_to_process[0])
    calc_obj_collect_result(points_to_process[0])
    iter += 1
    elapsed_time = round(time.time() - start_time, 2)
    processed_points_num = processed(generated_points)
    if processed_points_num % 100 == 0 and processed_points_num != prev_processed_points_num:
      assert(processed_points_num > prev_processed_points_num)
      print(str(processed_points_num) + ' points are processed;  elapsed : ' + str(elapsed_time) + ' seconds')
      #print(stat(generated_points))
      prev_processed_points_num = processed_points_num
    if processed_points_num >= op.max_points:
      print('The limit on the number of points is reached, break.')
      break
    if elapsed_time >= op.max_wall_time:
      print('The time limit is reached, break.')
      break

  # Write generated points:
  write_points(generated_points, cnfs)

  # Write final pcs file:
  write_final_pcs(best_point, params, cnfs)

  # Kill all solver species if they still exist:
  kill_solver(op.solver_name)

  # Print statistics:
  elapsed_time = round(time.time() - start_time, 2)
  best_sum_time = round(best_sum_time, 2)
  max_instance_time_best_point = round(max_instance_time_best_point, 2)
  print('')
  print('Elapsed : ' + str(elapsed_time) + ' seconds')
  print(str(iter) + ' iterations')
  print(str(updates_num) + " updates of best point")
  print(str(processed_points_num) + ' processed points')
  print(str(skipped_points_num) + ' skipped points')
  print(str(worse_than_best_but_calc_points_num) + ' calculated points which were worse than the current best')
  print(str(len(generated_points)) + ' generated points, of them:')
  print(stat(generated_points))
  print('Final best max time : ' + str(max_instance_time_best_point))
  print('Final best sum time : ' + str(best_sum_time) + ' , so ' + \
    str(default_sum_time) + ' -> ' + str(best_sum_time))
  if updates_num > 0:
    if best_point == def_point:
        print('The best point is the default one')
    else:
      diff_str = points_diff(def_point, best_point, params)
      assert(diff_str != '')
      print('Difference from the default point:')
      print(diff_str)
  print('Final best command : \n' + best_command)
