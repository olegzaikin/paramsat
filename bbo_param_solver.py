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

script_name = "bbo_param_solver.py"
version = '0.2.3'

# Like in ParamILS, give BOUND_MULTIPLIER x t time where t is the current best time:
BOUND_MULTIPLIER = 2
# A penalty coefficient for interrupted CNFs and points:
CNF_PENALTY_INTERR = 10 # PAR10 as in ParamILS and SMAC
# For this number of a variable values and lower, always use categorical distribution: 
MAX_VALUES_NUM_CATEGORICAL = 10

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
import types
import hashlib
import optuna
import optuna.distributions
import optuna.trial
import optunahub
import nevergrad

optuna_study = None
optuna_trial = None
nevergrad_trial = None
nevergrad_optimizer = None

optalg_indices = {
    "Optuna-TPE" : 0,
    "Optuna-HillClimbing" : 1,
    "Nevergrad-PortfolioDiscreteOnePlusOne" : 2,
    "Nevergrad-DiscreteOnePlusOne" : 3,
    "Nevergrad-NGOpt" : 4
}

# Point status:
class PointStatus(Enum):
    GENERATED = 0 # a point is generated
    STARTED = 1 # a point is generated and the calculation is started on it
    FINISHED = 2 # a point is calculated on all instances
    INTERRUPTED = 3 # a point is calculated, but on at least one instance the SAT solver was interrupted

# Point result:
class PointResult:
  status : PointStatus
  value : float
  def __init__(self, status=PointStatus.GENERATED, value=None):
    self.status = status
    self.value = value

# Solver's parameter:
class Param:
  name : str
  default : int
  values : list
  def __init__(self):
    self.name = ''
    self.default = -1
    self.values = []
  def __str__(self):
    s = self.name + ' default : ' + str(self.default) + ' ; values : ['
    for x in self.values:
       s += str(x) + ' '
    return s[:-1] + ']'

# Input options:
class Options:
	solver_name : str
	opt_alg : str
	space_type : str
	def_point_time : float
	max_points : int
	max_wall_time : float
	max_solver_time : float
	seed : int
	is_solving : bool
	def __init__(self):
		self.solver_name = ''
		self.opt_alg = 'Optuna-TPE'
		self.space_type = 'categ'
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
    'space_type      : ' + self.space_type + '\n' +\
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
				assert(self.opt_alg in ["Optuna-TPE", "Optuna-HillClimbing",\
                                "Nevergrad-PortfolioDiscreteOnePlusOne", "Nevergrad-DiscreteOnePlusOne",\
                                "Nevergrad-NGOpt"])
			if '-spacetype=' in p:
				self.space_type = p.split('-spacetype=')[1]
        # 3, > 200, > 10000, > 1073741824
				assert(self.space_type in ['categ', 'interval', 'log1', 'log2', 'log3', 'log4'])
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

def print_usage():
  print('Usage : ' + script_name + ' solver solver-parameters cnfs-dir [Options]')
  print('  Options :\n' +\
  '  -optalg=[Optuna-TPE, Optina-HillClimbing,' + '\n' +\
  '           Nevergrad-PortfolioDiscreteOnePlusOne, Nevergrad-DiscreteOnePlusOne, Nevergrad-NGOpt]' + '\n' +\
  '     (default : "Optuna-TPE") type of optimization algorithm' + '\n' +\
  '  -spacetype=<string>    - (default : categ) categ|interval|log1|log2|log3|log4' + '\n' +\
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
      # Example: backbone {0, 1, 2}[1]
      defstr = line.split('[')[1].split(']')[0]
      prm.default = convert_if_int(defstr)
      lst = line.split('{')[1].split('}')[0].replace(' ', '')
      valuesstr = lst.split(',')
      assert(len(lst) >= 2)
      #print(lst)
      for x in valuesstr:
        prm.values.append(convert_if_int(x))
      assert(len(prm.values) >= 2)
      for val in prm.values:
        assert(val in ['true', 'false'] or isinstance(val, int))
      assert(prm.default in prm.values)
      assert(prm.values[0] <= prm.default <= prm.values[-1])
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
		if 's SATISFIABLE' in line:
			sat = 1
		elif 's UNSATISFIABLE' in line:
			sat = 2
	if sat == -1 and t <= 0:
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
def create_solver_copy(solver_name : str, space_type : str, random_str : str):
  new_solver_name = solver_name + '_' + space_type + '_' + random_str
  print("Creating solver " + new_solver_name)
  sys_str = 'cp ' + solver_name + ' ' + new_solver_name
  subprocess.run(sys_str, shell=True)
  return new_solver_name

# Whether two given points are equal:
def equalparamval(paramname : str, point1 : list, point2 : list, inddict : dict):
  assert(paramname in inddict)
  return point1[inddict[paramname]] == point2[inddict[paramname]]

# Get a point (array of values) from Optuna trial:
def point_from_optuna_trial(optuna_trial, params : list):
  return [optuna_trial.params[p.name] for p in params]

# Generate new points via ask-tell interface:
def ask_point(params : list, op : Options, log_threshold : int):
  # Here are only global variables which are changed in this function: 
  global skipped_points_num
  global generated_points
  global optuna_study
  global optuna_trial
  global nevergrad_optimizer
  global nevergrad_trial
  assert(len(best_point) == len(params))
  new_point = None
  if 'Optuna' in op.opt_alg: # Optuna-TPE, Optuna-HillCLimbing
    # Check whether Optuna initializatoin was done:
    assert(type(optuna_study) != types.NoneType)
    # Take a new point from Optuna.
    # Some Optuna algorithms (e.g. HillCLimbing) can return the same point again.
    # In this case tell the Optuna that this point is pruned 
    # (this will not erease the existing result for this point).
    # That is why a loop is used here:
    while True:
      optuna_trial = optuna_study.ask(optuna_search_space)
      pnt = point_from_optuna_trial(optuna_trial, params)
      assert(len(pnt) == len(params))
      point_tuple = tuple(pnt)
      if point_tuple in generated_points:
        # The same point again, skip it.
        # Here tell() is needed since each ask() must be paired with tell():
        optuna_study.tell(optuna_trial, state=optuna.trial.TrialState.PRUNED)
        skipped_points_num += 1
        print('Same point again, skip it.')
      else:
        new_point = pnt
        break
  elif 'Nevergrad' in op.opt_alg:
    while True:
      nevergrad_trial = nevergrad_optimizer.ask()
      # Extract values in the same order as in params:
      pnt = []
      assert(len(params) > 0)
      for param in params:
        # Access the suggested value by the parameter's name
        val = nevergrad_trial.kwargs[param.name]
        assert(val >= param.values[0] and val <= param.values[-1])
        pnt.append(val)
      point_tuple = tuple(pnt)
      if point_tuple in generated_points:
        # The same point again, skip it.
        # Here tell() is needed since each ask() must be paired with tell():
        repeated_pnt = generated_points[point_tuple]
        assert(repeated_pnt.status == PointStatus.FINISHED or repeated_pnt.status == PointStatus.INTERRUPTED)
        # In case interrupted points are given from outside the program:
        if repeated_pnt.status == PointStatus.INTERRUPTED:
          repeated_value = len(cnfs) * op.max_solver_time * BOUND_MULTIPLIER
        else:
          repeated_value = repeated_pnt.value
        nevergrad_optimizer.tell(nevergrad_trial, repeated_value)
        skipped_points_num += 1
        print('Same point again, skip it.')
      else:
        new_point = pnt
        break
  assert(type(new_point) != types.NoneType)
  assert(len(new_point) == len(params))
  assert(new_point != best_point)
  point_tuple = tuple(new_point)
  assert(point_tuple not in generated_points)
  # At the moment function's value is None:
  generated_points[point_tuple] = PointResult(PointStatus.GENERATED, None)
  return new_point

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
  global generated_points
  assert(len(params) > 1)
  assert(len(params) == len(point))
  assert(len(cnfs) > 0)
  assert(len(op.solver_name) > 0)
  # A point to calculate must be marked as GENERATED:
  tuple_point = tuple(point)
  assert(generated_points[tuple_point].status == PointStatus.GENERATED)
  # Mark that the calculation is STARTED:
  generated_points[tuple_point] = PointResult(PointStatus.STARTED, None)
  cur_sum_time = 0.0
  max_instance_time = -1
  # Calculate sum for the solver runtimes:
  sat_num = 0
  sys_str = ''
  assert(op.max_solver_time <= op.max_wall_time)
  # Calculate a basic time limit for the solver:
  solver_time_lim = op.max_wall_time
  if op.max_solver_time > 0:
    assert(op.max_solver_time <= op.max_wall_time)
    solver_time_lim = op.max_solver_time
  # Process each CNF from the sample:
  cnf_num = 0
  is_interrupted_point = False
  for cnf_file_name in cnfs:
    assert('.cnf' in cnf_file_name)
    cnf_num += 1
    sys_str = ''
    # Check the left time:
    elapsed_time = round(time.time() - start_time, 2)
    avail_wall_time = op.max_wall_time - elapsed_time
    # If no time is left, do not run the solver:
    if avail_wall_time <= 0:
      print('Break: negative available wall time ' + str(avail_wall_time))
      break
    # Update the solver limit to not exceed the wall limit:
    if best_sum_time > 0 and (avail_wall_time > 0 and avail_wall_time < solver_time_lim):
      print('Changing solver time limit to available wall time ' + str(avail_wall_time))
      solver_time_lim = avail_wall_time
    # Calculate the remaining time for the current point:
    if best_sum_time > 0:
      remaining_point_time = best_sum_time * BOUND_MULTIPLIER - cur_sum_time
      # Process a very small elapsed value - ceil() must give at least one second:
      remaining_point_time = max(remaining_point_time, 0.5)
      assert(remaining_point_time > 0)
      if solver_time_lim > remaining_point_time:
        solver_time_lim = remaining_point_time
        print('solver_time_lim was decreased to remaining point time ' + str(solver_time_lim))
    assert(solver_time_lim > 0)
    rounded_solver_time_lim = math.ceil(solver_time_lim)
    assert(rounded_solver_time_lim > 0)
    sys_str = op.solver_name
    if 'kissat' in op.solver_name:
      sys_str += ' -n' # do not print satisfying assignment to save time
    sys_str += ' --time=' + str(rounded_solver_time_lim) + ' '
    for i in range(len(params)):
      sys_str += '--' + params[i].name + '=' + str(point[i]) + ' '
    sys_str += cnf_file_name
    #print(sys_str)
    cdcl_log = ''
    t, sat = -1, 0
    #cdcl_log = subprocess.run(sys_str, shell=True, capture_output=True, text=True).stdout
    try:
      completed = subprocess.run(
        sys_str,
        shell=True,
        capture_output=True,
        text=True,
        timeout=rounded_solver_time_lim + 5,  # Give the solver 5 extra seconds
        start_new_session=True,               # Kill the whole process group on timeout
      )
      if completed.returncode not in (0, 10, 20):
        print(f'WARNING: solver exit code {completed.returncode} on {cnf_file_name}')
      cdcl_log = completed.stdout
      #returncode = completed.returncode
      t, sat = parse_cdcl_result(cdcl_log)
    except subprocess.TimeoutExpired:
      #cdcl_log = ""
      #returncode = None
      # The process group was already signalled. Treat as an interrupted run.
      t, sat = rounded_solver_time_lim, -1
    assert(t >= 0)
    # Expect SAT or INTERR, while UNSAT is not a valid answer: 
    assert(sat == -1 or sat == 1 or sat == 2)
    # Normal situation is that the solver is not interrupted on the default point:
    if sat == -1 and best_sum_time <= 0:
      print('Error. A solver is interrupted on the default point, t : ' + str(t))
      assert(default_sum_time <= 0)
      sys.exit()
    # If the solver is interrupted at least once,
    if sat == -1 or (solver_time_lim > 0 and t > solver_time_lim):
      # PAR10 penalty for an interrupted CNF:
      assert(op.max_solver_time > 0)
      t = op.max_solver_time * CNF_PENALTY_INTERR
    else:
      assert(sat == 1 or sat == 2) # SAT or UNSAT should be here
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
        print('Current obj func value ' + str(round(cur_sum_time, 2)) + ' is already worse than ' + \
          str(BOUND_MULTIPLIER) + 'x ' + str(best_sum_time))
        print('Break after processing ' + str(cnf_num) + ' CNFs out of ' + str(len(cnfs)))
        break
      elapsed_time = round(time.time() - start_time, 2)
      # If time limit for the script is reached:
      if elapsed_time >= op.max_wall_time:
        print('Wall time limit is reached while calculating objective function')
        print('Break after processing ' + str(cnf_num) + ' CNFs out of ' + str(len(cnfs)))
        break
  # end of loop 'for cnf_file_name in cnfs'
  # It is possible that is_interrupted_point is False here and sat_num < len(cnfs)
  # if on the last CNF the solver is interrupted. If the solver was interrupted on
  # any but the last CNF, then is_interrupted_point is already True here:
  if sat_num < len(cnfs):
    is_interrupted_point = True
    # Tell Optuna the intermediate result for a point that will be soon PRUNEd:
    if 'Optuna' in op.opt_alg:
      optuna_trial.report(cur_sum_time, step=cnf_num)
  #print('Obj func value : ' + str(cur_sum_time))
  cur_sum_time = round(cur_sum_time, 2)
  assert(cur_sum_time >= 0)
  # Replace too tiny value:
  cur_sum_time = max(cur_sum_time, 0.01)
  return point, cur_sum_time, max_instance_time, sys_str, is_interrupted_point

# Collect a result produced by solver:
def collect_result(res : tuple):
  global default_sum_time
  global max_instance_time_best_point
  global best_sum_time
  global best_point
  global best_command
  global updates_num
  global generated_points
  global worse_than_best_but_calc_points_num
  global optuna_study
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
  assert(generated_points[tuple_point].status == PointStatus.STARTED)
  # If a new record point is found:
  if (is_interrupted_point == False and cur_sum_time >= 0) and (cur_sum_time < best_sum_time or best_sum_time <= 0):
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
  # Two cases:
  # 1) The point is calculated, and the point is marked STARTED, so STARTED -> FINISHED
  # 2) A point is interrupted, so STARTED -> INTERRUPTED
  tell_time = cur_sum_time
  if is_interrupted_point == False:
    assert(cur_sum_time >= 0)
    generated_points[tuple_point] = PointResult(PointStatus.FINISHED, cur_sum_time)
    if cur_sum_time > best_sum_time and best_sum_time > 0:
      worse_than_best_but_calc_points_num += 1
    print('Finished point with sum_time ' + str(cur_sum_time) + ' , max_inst_time ' + str(max_instance_time))
  else:
    # Calculate a 2 x cur-best-time penalty for interuupted points as in ParamILS and SMAC:
    assert(best_sum_time >= 0)
    assert(BOUND_MULTIPLIER >= 1)
    penalty_sum_time = round(best_sum_time * CNF_PENALTY_INTERR, 2)
    assert(penalty_sum_time > 0)
    generated_points[tuple_point] = PointResult(PointStatus.INTERRUPTED, penalty_sum_time)
    tell_time = penalty_sum_time
  assert(tell_time >= 0)
  # Tell Optuna the objective function value:
  if 'Optuna' in op.opt_alg:
    assert(type(optuna_trial) != types.NoneType)
    # Give an actual function value only if not interrupted:
    if is_interrupted_point:
      optuna_study.tell(optuna_trial, state=optuna.trial.TrialState.PRUNED)
    else:
      optuna_study.tell(optuna_trial, tell_time)
  # Tell Nevergrad the objective function value:
  elif 'Nevergrad' in op.opt_alg:
    assert(type(nevergrad_trial) != types.NoneType)
    # Nevegrad can not mark a point as PRUNED like Optuna, so
    # give an actual function value (penalized if interrupted);
    if is_interrupted_point:
      # Stationary, on the same scale as the summed objective.
      tell_time = len(cnfs) * op.max_solver_time * BOUND_MULTIPLIER
    nevergrad_optimizer.tell(nevergrad_trial, tell_time)
  assert(best_sum_time >= 0)

# Read all CNFs in a given dir:
def read_cnfs(cnfs_dir_name : str):
  cnfs = list()
  os.chdir('.')
  for f in glob.glob(cnfs_dir_name + '/*.cnf'):
    assert('.cnf' in f)
    cnfs.append(f)
  cnfs.sort()
  return cnfs

# Write generated points to a file:
def write_points(points : dict, opt_alg : str, seed: int):
  out_name = 'generated_points_' + opt_alg + '_seed=' + str(seed)
  print('Writing generated points to file ' + out_name)
  with open(out_name, 'w') as f:
    for p, pr in points.items():
      f.write(f"{p} {pr.status.name} {pr.value}\n")

# Write final best point as a pcs file:
def write_final_pcs(best_point : list, params : list, opt_alg : str, seed : int):
  assert(len(best_point) == len(params))
  outname = 'final_best_' + opt_alg + '_seed=' + str(seed) + '.pcs'
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
     if generated_points[point_tuple].status == PointStatus.FINISHED or \
     generated_points[point_tuple].status == PointStatus.INTERRUPTED:
        res += 1
  return res

def finished(generated_points : dict):
  res = 0
  for point_tuple in generated_points:
    if generated_points[point_tuple].status == PointStatus.FINISHED:
      res += 1
  return res

def interrupted(generated_points : dict):
  res = 0
  for point_tuple in generated_points:
    if generated_points[point_tuple].status == PointStatus.INTERRUPTED:
      res += 1
  return res

def stat(generated_points : dict):
  res = ''
  generated_num = 0
  started_num = 0
  finished_num = 0
  interrupted_num = 0
  for point_tuple in generated_points:
      if generated_points[point_tuple].status == PointStatus.GENERATED:
         generated_num += 1
      elif generated_points[point_tuple].status == PointStatus.STARTED:
         started_num += 1
      elif generated_points[point_tuple].status == PointStatus.FINISHED:
         finished_num += 1
      elif generated_points[point_tuple].status == PointStatus.INTERRUPTED:
         interrupted_num += 1
  res = str(generated_num) + ' only generated\n' + \
    str(started_num) + ' started\n' + \
    str(finished_num) + ' finished\n' + \
    str(interrupted_num) + ' interrupted\n'
  return res

def print_optuna_trials():
  # View summary of all trials:
  df = optuna_study.trials_dataframe(attrs=('number', 'value', 'params', 'state'))
  complete_count = len(optuna_study.get_trials(states=(optuna.trial.TrialState.COMPLETE,)))
  pruned_count = len(optuna_study.get_trials(states=(optuna.trial.TrialState.PRUNED,)))
  print(f"COMPLETED: {complete_count}, PRUNED: {pruned_count}")
  print('Completed trials :')
  print(df[df["state"] == "COMPLETE"].to_string())

def print_nevergrad_trials():
  assert(nevergrad_optimizer != None)
  print(f"Nevergrad archive contains {len(nevergrad_optimizer.archive.bytesdict)} unique points (some could be pruned) :")
  for byte_key, value_obj in nevergrad_optimizer.archive.bytesdict.items():
    # Convert the byte key back to a numpy array of parameter values
    #point_array = np.frombuffer(byte_key)
    #print(f"Point: {point_array}")
    print(f"Function's value: {value_obj.mean}") # 1 evaluation so 'mean' here is the function's value 
    #print(f"  Count: {value_obj.count}") # Number of times this point was evaluated[reference:6]

# Returns True iff param.values is not exactly [low, low+1, ..., high].
def pcs_values_are_sparse(param : Param) -> bool:
  if not all(isinstance(v, int) for v in param.values):
    return False
  low = param.values[0]
  high = param.values[-1]
  if len(param.values) != high - low + 1:
    return True
  return any(param.values[i] != low + i for i in range(len(param.values)))

# Print warning if values are sparse:
def check_if_sparse(param : Param, space_type : str):
  if pcs_values_are_sparse(param):
    print(f'WARNING [{space_type}]: {param.name} PCS values are sparse; '
          f'{space_type} mode searches the full interval '
          f'[{param.values[0]}, {param.values[-1]}]')

# Form Optuna variable with proper distribution:
def optuna_var(param : Param, space_type : str, log_threshold : int):
  assert(len(param.values) >= 2)
  assert(space_type != '')
  assert(log_threshold >= -1)
  low = param.values[0]
  high = param.values[-1]
  # Count the number of integer values for integer distribution: 
  values_num = high - low + 1
  opt_var = None
  # If 10 values and lower, always use categorical distribution:
  if space_type == 'categ' or values_num <= MAX_VALUES_NUM_CATEGORICAL:
    opt_var = optuna.distributions.CategoricalDistribution(param.values)
  elif space_type == 'interval' or (log_threshold >= 0 and high <= log_threshold):
    check_if_sparse(param, space_type)
    opt_var = optuna.distributions.IntDistribution(low, high, log=False)
  elif 'log' in space_type:
    assert(log_threshold >= 0)
    assert(values_num > MAX_VALUES_NUM_CATEGORICAL)
    assert(high > log_threshold)
    print('Log mode for Optuna variable, ' + str(param))
    if low == 0: # 0 is prohibited in log mode:
      low = 1
      if param.default == 0:
        param.default = 1
      print('New low value is ' + str(low) + ' ; 0 is not allowed in Log mode')
    opt_var = optuna.distributions.IntDistribution(low, high, log=True)
  assert(low <= param.default and param.default <= high)
  assert(opt_var != None)
  return opt_var

# Make a parameter-variable for Nevegrad's search space:
def nevegrad_var(param : Param, space_type : str, log_threshold : int):
  assert(len(param.values) >= 2)
  assert(space_type != '')
  assert(log_threshold >= -1)
  assert(len(param.values) >= 2)
  low = param.values[0]
  high = param.values[-1]
  values_num = high - low + 1
  assert(values_num >= 2)
  int_param = None
  low = param.values[0]
  high = param.values[-1]
  if space_type == 'categ' or values_num <= MAX_VALUES_NUM_CATEGORICAL:
    int_param = nevergrad.p.TransitionChoice(param.values)
  elif space_type == 'interval' or (log_threshold >= 0 and high <= log_threshold):
    check_if_sparse(param, space_type)
    int_param = nevergrad.p.Scalar(
              init=param.default, lower=low, upper=high
            ).set_integer_casting()
  elif 'log' in space_type:
    assert(log_threshold >= 0)
    assert(values_num > MAX_VALUES_NUM_CATEGORICAL)
    assert(high > log_threshold)
    print('Log mode for Nevergrad variable, ' + str(param))
    if low == 0: # 0 is prohibited in log mode:
      low = 1
      if param.default == 0:
        param.default = 1
      print('New low value is ' + str(low) + ' ; 0 is not allowed in Log mode')
    int_param =  nevergrad.p.Log(
      init=param.default, lower=low, upper=high
    ).set_integer_casting()
  assert(int_param != None)
  assert(low <= param.default and param.default <= high)
  return int_param

# Max parameters values are:
# [2 3] [25 100 200] [1000 8192 10000] [32768 1000000 100000000 1073741824] [2147483647]
# So threshold for Log=True are : > 3, > 200, > 10000, > 1073741824
def log_threshold_from_space_type(space_type : str):
  assert('log' in space_type)
  log_threshold = -1
  if '1' in space_type:
    log_threshold = 3
  elif '2' in space_type:
    log_threshold = 200
  elif '3' in space_type:
    log_threshold = 10000
  elif '4' in space_type:
    log_threshold = 1073741824
  assert(log_threshold >= 0)
  return log_threshold

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
  print('BOUND_MULTIPLIER : ' + str(BOUND_MULTIPLIER))
  print('solver_name      : ' + solver_name)
  print('param_file_name  : ' + param_file_name)
  print('cnfs_dir_name    : ' + cnfs_dir_name)
  op = Options()
  op.read(sys.argv[3:])
  # Read CNFs:
  cnfs = []
  cnfs = read_cnfs(cnfs_dir_name)
  cnfs_num = len(cnfs)
  assert(len(cnfs) > 0)
  print(str(len(cnfs)) + ' CNFs were read :')
  for cnf in cnfs:
    print(cnf)
  # Read parameters and their values:
  params = read_pcs(param_file_name)
  # Force the seed depend solver, pcs name, CNFs names, and user's seed, 
  # Algorithm index is not used here to have same seeds for all algorithms for comparison.
  all_params_string = ''
  for p in params:
    #print(p)
    values_string = [str(x) for x in p.values]
    all_params_string += p.name + ':' + "".join(values_string)
  #print('all_params_string : ' + all_params_string)
  basenames_cnfs = [os.path.basename(name) for name in cnfs]
  seed_string = os.path.basename(solver_name) + "".join(basenames_cnfs) + all_params_string
  #print('seed_string : ' + seed_string)
  hash = hashlib.sha256(seed_string.encode("utf-8"))
  hex_hash = hash.hexdigest()
  int_hash = int(hex_hash, 16)
  print('int hash of seed string : ' + str(int_hash))
  # % (2**32) is needed since a seed myst be between 0 and 2**32 - 1
  op.seed = (op.seed + int_hash) % (2**32)
  print('Updated seed : ' + str(op.seed))
  # random is used in the script:
  random.seed(op.seed)
  # np.random is used by Nevegrad:
  np.random.seed(op.seed)
  random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 10))
  random_str += '_' + op.opt_alg
  print("The randomly generated string for algorithm " + op.opt_alg + " is : " + str(random_str))
  assert(len(solver_name) > 0)
  new_solver_name = create_solver_copy(solver_name, op.space_type, random_str)
  print('Solver name is changed to ' + new_solver_name)
  op.solver_name = new_solver_name
  # Print the final options:
  print(op)
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
  best_point = copy.deepcopy(def_point)
  # Command for default point:
  best_command = op.solver_name + ' ' + cnfs[0]
  default_sum_time = op.def_point_time
  best_sum_time = op.def_point_time
  print('Current best sum time : ' + str(best_sum_time))
  elapsed_time = round(time.time() - start_time, 2)
  print('Elapsed : ' + str(elapsed_time) + ' seconds')
  #init_points_num = len(params) + 1
  # At least 10 and at most 30 initial points, by default it is 10 % of the max points lim.
  init_points_num = max(10, min(30, op.max_points // 10))
  print('init_points_num for ask-and-tell algorithm : ' + str(init_points_num))
  log_threshold = -1
  if 'log' in op.space_type:
    log_threshold = log_threshold_from_space_type(op.space_type)
  print('log_threshold : ' + str(log_threshold))
  optuna_search_space = {}
  # Initialize optimizer if needed:
  if 'Optuna' in op.opt_alg:
    # Form the search space - all variables with proper distributions:
    for param in params:
      optuna_search_space[param.name] = optuna_var(param, op.space_type, log_threshold)
    if op.opt_alg == 'Optuna-TPE':
      sampler = optuna.samplers.TPESampler(n_startup_trials=init_points_num, multivariate=True, seed=op.seed)
      optuna_study = optuna.create_study(sampler=sampler, direction="minimize")
    elif op.opt_alg == 'Optuna-HillClimbing':
      mod = optunahub.load_module("samplers/hill_climbing")
      # Set the limit of restarts to the limit of points to stay in HillClimbing mode,
      # otherwise HillClimbing can switch to Random search.
      # neighbor_size can be also changed here:
      sampler = mod.HillClimbingSampler(search_space=optuna_search_space, max_restarts=op.max_points, seed=op.seed) 
      optuna_study = optuna.create_study(sampler=sampler, direction="minimize")
  elif 'Nevergrad' in op.opt_alg:
    kwargs = dict()
    for param in params:
      kwargs[param.name] = nevegrad_var(param, op.space_type, log_threshold)
    parametrization = nevergrad.p.Instrumentation(**kwargs)
    assert(parametrization != None)
    #print(parametrization)
    # If the maximum number of points is given, use it as bugdet, otherwise None:
    # If budget is not None, than at most budget points will be processed,
    # so op.max_points must be an upper bound (say, 100 thousand):
    budget = op.max_points if op.max_points > 0 else None
    if op.opt_alg == 'Nevergrad-PortfolioDiscreteOnePlusOne':
      nevergrad_optimizer = nevergrad.optimizers.PortfolioDiscreteOnePlusOne(
        parametrization=parametrization,
        budget=budget,
        num_workers=1  # Sequential ask-and-tell
      )
    elif op.opt_alg == 'Nevergrad-DiscreteOnePlusOne':
      nevergrad_optimizer = nevergrad.optimizers.DiscreteOnePlusOne(
        parametrization=parametrization,
        budget=budget,
        num_workers=1  # Sequential ask-and-tell
      )
    elif op.opt_alg == 'Nevergrad-NGOpt':
       nevergrad_optimizer = nevergrad.optimizers.NGOpt(
        parametrization=parametrization,
        budget=budget,
        num_workers=1  # Sequential ask-and-tell
      )
    assert(nevergrad_optimizer != None)
  updates_num = 0
  max_instance_time_best_point = -1
  skipped_points_num = 0
  prev_processed_points_num = 1
  worse_than_best_but_calc_points_num = 0
  processed_points_num = 1 # 1 since the default point is processed before the main loop:
  iter = 1 # iter 0 is the default point
  elapsed_time = 0
  # A dictionary of generated points, where a tuple representation of the
  # point's parameters values is an ID, while the VALUE is a point's status:
  generated_points = dict()
  # If runtime on default point is given, mark it as finished:
  point_tuple = tuple(def_point)
  # Add the default point to Optuna's queue and ask() this point:
  trial_params = {param.name: val for param, val in zip(params, def_point)}
  if 'Optuna' in op.opt_alg:
    assert(len(trial_params) == len(def_point))
    optuna_study.enqueue_trial(trial_params)
    optuna_trial = optuna_study.ask(optuna_search_space)
    # These suggest_categorical() are required by Optuna for every asked point:
    pnt = point_from_optuna_trial(optuna_trial, params)
  elif 'Nevergrad' in op.opt_alg:
    # Give the default point and ask() for it:
    nevergrad_optimizer.suggest(**trial_params)
    nevergrad_trial = nevergrad_optimizer.ask()
  # If time for default point is given, update penalty sum time:
  if default_sum_time > 0:
    generated_points[point_tuple] = PointResult(PointStatus.FINISHED, default_sum_time)
    print('The default point is given, so it is marked as finished.')
    assert(op.max_solver_time > 0)
    assert(optuna_trial != types.NoneType)
    if 'Optuna' in op.opt_alg:
      optuna_study.tell(optuna_trial, default_sum_time)
    elif 'Nevergrad' in op.opt_alg:
      nevergrad_optimizer.tell(nevergrad_trial, default_sum_time)
  else:
    # otherwise, add the default point to the queue for processing:
    generated_points[point_tuple] = PointResult(PointStatus.GENERATED, None)
    print('Calculating objective function in the default point')
    calc_obj_collect_result(def_point)
    assert(max_instance_time_best_point > 0)
    assert(max_instance_time_best_point < op.max_wall_time)
  # Here the default time must be known or calculated and the best time is the default:
  assert(default_sum_time >= 0 and best_sum_time >= 0)
  assert(default_sum_time == best_sum_time)
  # If maximum solver time is not set, use the default point's result:
  if op.max_solver_time <= 0:
    if max_instance_time_best_point > 0:
      op.max_solver_time = max_instance_time_best_point * BOUND_MULTIPLIER
    # If default objective function value is given but max solver time is not:
    elif default_sum_time > 0:
      op.max_solver_time = math.ceil(default_sum_time)
    else:
      op.max_solver_time = op.max_wall_time
    print('max_solver_time is not set, so it was changed to ' + str(op.max_solver_time))
  assert(len(generated_points) == 1)
  assert(op.max_solver_time > 0)
  print('*** iter 0 was spent on the default point')
  # Repeat until all points are processed:
  while processed_points_num < op.max_points and elapsed_time < op.max_wall_time:
    print('*** iter : ' + str(iter))
    elapsed_time = round(time.time() - start_time, 2)
    print('Elapsed ' + str(elapsed_time) + ' sec')
    # Ask for a new point:
    point_to_process = ask_point(params, op, log_threshold)
    # Check the point's status:
    tuple_point = tuple(point_to_process)
    #print(tuple_point)
    calc_obj_collect_result(point_to_process)
    iter += 1
    elapsed_time = round(time.time() - start_time, 2)
    processed_points_num = processed(generated_points)
    assert(processed_points_num == iter)
    finished_points_num = finished(generated_points)
    interrupted_points_num = interrupted(generated_points)
    assert(processed_points_num == finished_points_num + interrupted_points_num)
    s = str(finished_points_num) + ' finished points, ' + str(interrupted_points_num) + ' interrupted points'
    print(s)
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
  write_points(generated_points, op.opt_alg, op.seed)
  # Write final pcs file:
  write_final_pcs(best_point, params, op.opt_alg, op.seed)
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
  print('Final best sum time : ' + str(best_sum_time) + ' , so ' + \
    str(round(default_sum_time, 2)) + ' -> ' + str(best_sum_time))
  print('Final best max time : ' + str(max_instance_time_best_point))
  if updates_num > 0:
    if best_point == def_point:
        print('The best point is the default one')
    else:
      diff_str = points_diff(def_point, best_point, params)
      assert(diff_str != '')
      print('Difference from the default point:')
      print(diff_str)
  print('Final best command : \n' + best_command)
  # Print Optuna statistics:
  if optuna_study != None:
    running_trials_num = 0
    waiting_trials_num = 0
    pruned_trials_num = 0
    complete_trials_num = 0
    fail_trials_num = 0
    for t in optuna_study.trials:
      if t.state == optuna.trial.TrialState.RUNNING:
         running_trials_num += 1
      if t.state == optuna.trial.TrialState.WAITING:
         waiting_trials_num += 1
      if t.state == optuna.trial.TrialState.PRUNED:
         pruned_trials_num += 1
      if t.state == optuna.trial.TrialState.COMPLETE:
         complete_trials_num += 1
      if t.state == optuna.trial.TrialState.FAIL:
         fail_trials_num += 1
    print('')
    print('Optuna statistics :')
    print(str(running_trials_num) + ' running trials')
    print(str(waiting_trials_num) + ' waiting trials')
    print(str(pruned_trials_num) + ' pruned trials')
    print(str(complete_trials_num) + ' complete trials')
    print(str(fail_trials_num) + ' fail trials')
    print_optuna_trials()
  elif nevergrad_optimizer != None:
    print_nevergrad_trials()
