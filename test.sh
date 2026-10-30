timelim=300
pointslim=60
for alg in 1+1 Optuna-TPE Optuna-HillClimbing Optuna-GP Optuna-HillClimbing-TPE
do
    echo $alg
    python3 ./bbo_param_solver.py ./kissat4.0.1_quiet ./kissat4.0.1_reduced.pcs ./cnfs_easy/ -optalg=${alg} -seed=0 -maxpoints=${pointslim} -maxtime=$timelim &> out_test_${alg} &
    sleep 1
done 
