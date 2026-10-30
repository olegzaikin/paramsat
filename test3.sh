for i in 0 1 2
do
    python3 ./bbo_param_solver.py ./kissat4.0.1_quiet ./kissat4.0.1_reduced.pcs ./cnfs_easy/ -optalg=Optuna-HillClimbing-TPE -seed=0 -maxpoints=3 -maxtime=600 &> out_$i
done
