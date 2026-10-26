timelim=3600
pointslim=1000
for alg in SKOPT-ET SKOPT-RF SKOPT-GBRT 1+1 Optuna-TPE Optuna-HillClimbing
do
    echo $alg
    python3 ./bbo_param_solver.py ./kissat4.0.1_quiet ./kissat4.0.1_reduced.pcs ./cnfs_easy/ -optalg=${alg} -seed=0 -maxpoints=${pointslim} -maxtime=$timelim &> out_${alg} &
    sleep 1
done 
