timelim=300
pointslim=100
for alg in SKOPT-ET SKOPT-RF SKOPT-GBRT SKOPT-GP 1+1
do
    echo $alg
    python3 ./bbo_param_solver.py ./kissat4.0.1_quiet ./kissat4.0.1_reduced.pcs ./cnfs_easy/ -optalg=${alg} -seed=0 -maxpoints=${pointslim} -maxtime=$timelim &> out_${alg} &
    sleep 1
done 
