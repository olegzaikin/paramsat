!/usr/bin/bash

python3 ./bbo_param_solver.py ./kissat3 ./kissat3_md_given.pcs ./cnfs_supereasy/ -maxpoints=2 -cpunum=1
python3 ./bbo_param_solver.py ./kissat3 ./kissat3_md_given.pcs ./cnfs_supereasy/ -maxpoints=5 -cpunum=5
python3 ./bbo_param_solver.py ./kissat3 ./kissat3_md_given.pcs ./cnfs_supereasy/ -maxpoints=10 -cpunum=5
python3 ./bbo_param_solver.py ./kissat3 ./kissat3_md_given.pcs ./cnfs_supereasy/ -maxpoints=5 -cpunum=5 -pointsfile=./points
python3 ./bbo_param_solver.py ./kissat3 ./kissat3_md_given.pcs ./cnfs_supereasy/ -maxpoints=5 -cpunum=5 -pointsfile=./points --solving
