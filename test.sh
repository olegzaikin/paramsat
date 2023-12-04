!/usr/bin/bash

python3 ./bbo_param_solver.py ./kissat3 ./kissat3-md-given.pcs ./cnfs_easy/ -maxpoints=2 -cpunum=1
python3 ./bbo_param_solver.py ./kissat3 ./kissat3-md-given.pcs ./cnfs_easy/ -maxpoints=5 -cpunum=5
python3 ./bbo_param_solver.py ./kissat3 ./kissat3-md-given.pcs ./cnfs_easy/ -maxpoints=10 -cpunum=3
