timelim=180
pointslim=50
#Optuna-CatCMA
defobj=9.55
maxsolvertime=5
for alg in 1+1 Optuna-TPE Optuna-HillClimbing Optuna-GP
do
    echo $alg
    python3 ./bbo_param_solver.py ./kissat4.0.1_quiet ./kissat4.0.1_reduced.pcs ./cnfs_easy/ -optalg=${alg} -seed=0 -maxpoints=${pointslim} -maxtime=$timelim &> out_test_${alg} &
    sleep 1
done 
