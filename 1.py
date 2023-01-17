import random

# Randomly choose an element from a given list except given current index.
# The closer index is to the given one, the higher probability is to be chosen.
def choose_with_weight(lst : list, cur_index : int):
  weights = [0 for x in lst]
  max_dist_to_left = cur_index
  max_dist_to_right = len(lst) - cur_index - 1
  max_dist = max(max_dist_to_left, max_dist_to_right)
  for i in range(cur_index):
    weights[cur_index - i - 1] = pow(2, max_dist-1 - i)
  for i in range(cur_index+1, len(lst)):
    weights[i] = pow(2, max_dist-1 - (i - cur_index - 1))
  r = random.choices(lst, weights, k=1)
  assert(len(r) == 1 and r[0] in lst and r[0] != cur_index)
  return r[0]

lst = [0, 1]
#print(lst)
counter = [0 for x in lst]
for _ in range(100):
  x = choose_with_weight(lst, 1)
  counter[x] += 1
  #print(str(x))
print(counter)
