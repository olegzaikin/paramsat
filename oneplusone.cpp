// Created on: 9 March 2022
// Author: Oleg Zaikin
// E-mail: zaikin.icc@gmail.com
//
// Implementation of an integer-programming version of the (1+1) evolutionary
// algorithm.
// A point is a set of n integers.
// Given a point p and an integer number k, k points are generated in
// the neighborhood of p.
// 
// Example:
//   XXX
//
//=============================================================================

#include <iostream>
#include <vector>
#include <set>
#include <cassert>
#include <random>
#include <algorithm>

#define point_t std::vector<int>
#define param_t std::vector<int>

template <class X>
constexpr bool eqp(const X& lhs, const X& rhs) noexcept {
  return lhs == rhs;
}

/* 
// Python code for calculating weights:
weights = [0 for x in lst]
max_dist_to_left = indx
max_dist_to_right = len(lst) - indx - 1
max_dist = max(max_dist_to_left, max_dist_to_right)
for i in range(indx):
  weights[indx - i - 1] = pow(2, max_dist-1 - i)
for i in range(indx+1, len(lst)):
  weights[i] = pow(2, max_dist-1 - (i - indx - 1))
*/
std::vector<unsigned> calc_weights(const unsigned indx, const unsigned arraysize) {
  std::vector<unsigned> weights(arraysize, 0); // сначала все веса нулевые
  unsigned max_distance_to_left = indx;
  unsigned max_distance_to_right = arraysize - indx - 1;
  unsigned max_distance = std::max(max_distance_to_left, max_distance_to_right);
  for (unsigned i=0; i < indx; ++i) {
    weights[indx - i - 1] = std::pow(2, max_distance-1 - i);
  }
  for (unsigned i=indx+1; i < arraysize; ++i) {
    weights[i] = std::pow(2, max_distance-1 - (i - indx - 1));
  }
  assert(weights[indx] == 0);
  return weights;
}

unsigned new_param_value(const unsigned current_value, param_t param, 
                         std::mt19937 &rand_gen) {
  // Тестирование calc_weights;
  assert(eqp(calc_weights(0, 2), {0, 1}));
  assert(eqp(calc_weights(1, 2), {1, 0}));
  assert(eqp(calc_weights(0, 3), {0, 2, 1}));
  assert(eqp(calc_weights(1, 3), {1, 0, 1}));
  assert(eqp(calc_weights(2, 3), {1, 2, 0}));
  assert(eqp(calc_weights(0, 4), {0, 4, 2, 1}));
  assert(eqp(calc_weights(1, 4), {2, 0, 2, 1}));
  assert(eqp(calc_weights(2, 4), {1, 2, 0, 2}));
  assert(eqp(calc_weights(3, 4), {1, 2, 4, 0}));
  //
  auto it = std::find(param.begin(), param.end(), current_value);
  assert(it != param.end());
  unsigned indx = it - param.begin();
  unsigned new_index = indx;
  // Вычислить веса:
  std::vector<unsigned> weights = calc_weights(indx, param.size());
  // Дискретное распределение, основанное на весах:
  std::discrete_distribution<> dist(weights.begin(), weights.end());
  /*
  std::cout << "param :" << std::endl;
  for (auto x : param) std::cout << x << " ";
  std::cout << std::endl;
  std::cout << "Weights :" << std::endl;
  for (auto x : weights) std::cout << x << " ";
  std::cout << std::endl;
  */
  new_index = dist(rand_gen);
  assert(new_index != indx);
  unsigned new_val = param[new_index];
  /*
  std::cout << "current_value : " << current_value << std::endl;
  std::cout << "new_val       : " << new_val << std::endl;
  std::cout << std::endl;
  */
  assert(new_val != current_value);
  return new_val;
}

// Whether a random event happens with a given probability:
bool is_random_event_happens(std::mt19937 &rand_gen, const double probability) {
  assert(probability > 0.0 and probability < 1.0);
  // Генератор, который выдает вещественные числа от 0.0 до 1.0 включительно:
	static std::uniform_real_distribution<double> dist{0.0, 1.0};
  double d = dist(rand_gen);
  if (d < probability) return true;
  return false;
}

// Сгенерировать points_to_gen точек в окрестности точки start_point
// в пространстве параметров parameters.
// iteration - итерация поиска, которая используется для инициализации
// генератора псевдослучайных чисел
std::set<point_t> oneplusone(const point_t start_point,
                             const std::vector<param_t> parameters,
                             const unsigned points_to_gen,
                             const unsigned iteration) {
  assert(not parameters.empty());
  assert(not start_point.empty());
  assert(points_to_gen > 0);
  std::set<point_t> points;
  unsigned params_num = parameters.size(); // число параметров
  // Генератор Вихрь Мерсенна, инициализированный номером итерации:
	std::mt19937 rand_gen{ static_cast<unsigned int>(iteration) };

  // Пока не сгенерировано нужное число точек:
  while (points.size() < points_to_gen) {
    point_t new_point = start_point;
    std::vector<unsigned> params_indicies_to_change;
    for (unsigned i=0; i < params_num; ++i) {
      // Вероятность 1/n, где n - число параметров:
      if (is_random_event_happens(rand_gen, (double)1/(double)params_num)) {
        params_indicies_to_change.push_back(i);
      }
    }
    // Если ни один параметр не выбран для изменения, пропустить:
    if (params_indicies_to_change.empty()) continue;
    for (auto indx : params_indicies_to_change) {
      //std::cout << "indx to change : " << indx << std::endl;
      new_point[indx] = new_param_value(start_point[indx], parameters[indx], rand_gen);
    }
    // Если такой точки еще нет в множестве, добавить ее:
    if (points.count(new_point) == 0) {
      points.insert(new_point);
    }
  }

  //assert(not points.empty());
  return points;
}

void print_point(const point_t p) {
  for (auto x : p) std::cout << x << " ";
  std::cout << "\n";
}

int main(int argc, char** argv) {
  unsigned iteration = 1; // номер итерации поиска
  std::vector<param_t> parameters = {{0,1}, {1,2,3}, {5, 10, 25, 50, 100}, {10, 100, 1000, 10000}, {0,1}, 
  {0,1}, {1,2,3}, {5, 10, 25, 50, 100}, {10, 100, 1000, 10000}, {0,1}};
  point_t start_point = {0,2,5,1000,1,0,2,5,1000,1};
  std::cout << "start_point :\n";
  print_point(start_point);
  std::set<point_t> points = oneplusone(start_point, parameters, 10, iteration);
   std::cout << points.size() << " points generated :" << std::endl;
  for (auto p : points) print_point(p);
  return 0;
}
