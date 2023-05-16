# Created on: 13 May 2023
# Author: Oleg Zaikin
# E-mail: zaikin.icc@gmail.com
#
# Converts a given wcnf-file from the old format to the new one.
# For details see
# https://maxsat-evaluations.github.io/2022/rules.html#input
#
# Example:
#   python3 ./convert_to_new_maxsat.py ./1.wcnf
#
# If 1.wcnf is a wcnf-file in an old format, e.g.
# p wcnf 4 5 15
# 15 1 -2 4 0
# 15 -1 -2 3 0
# 6 -2 -4 0
# 5 -3 2 0
# 3 1 3 0
#
# then the file 1_newformat.wcnf in the new format will be created as follows:
# h 1 -2 4 0
# h -1 -2 3 0
# 6 -2 -4 0
# 5 -3 2 0
# 3 1 3 0
# 
#========================================================================================


import sys

fname = sys.argv[1].replace('./', '')
top = 1
hw = -1
with open(fname, 'r') as f:
  lines = f.read().splitlines()
  for line in lines:
    if len(line) < 2 or line[0] == 'p' or line[0] == 'c':
      continue
    w =  int(line.split()[0])
    if hw < 0:
      hw = w
      print('hw : ' + str(hw))
    if w == hw:
      continue
    top += w
print('top : ' + str(top))

assert(top == hw)
new_lines = []
with open(sys.argv[1]) as f:
  lines = f.read().splitlines()
  for line in lines:
    if len(line) < 2 or line[0] == 'p' or line[0] == 'c':
      continue
    words = line.split()
    w =  int(words[0])
    if w == hw:
      s = 'h'
      for word in words[1:]:
        s += ' ' + word
      new_lines.append(s)
    else:
      new_lines.append(line)

new_fname = fname.split('.')[0] + '_newformat.wcnf'
print('new_fname : ' + new_fname)
with open(new_fname, 'w') as ofile:
  for line in new_lines:
    ofile.write(line + '\n')
