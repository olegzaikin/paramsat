timelim=3600
pointslim=1000
defobj=9.55
for alg in 1+1 Optuna-TPE Optuna-HillClimbing
do
    echo $alg
    python3 ./bbo_param_solver.py ./kissat4.0.1_quiet ./kissat4.0.1_reduced.pcs ./cnfs_easy/ -optalg=${alg} -seed=0 -maxpoints=${pointslim} -maxtime=$timelim &> out_${alg} &
    sleep 1
    python3 ./bbo_param_solver.py ./kissat4.0.1_quiet ./kissat4.0.1_reduced.pcs ./cnfs_easy/ -optalg=${alg} -seed=0 -maxpoints=${pointslim} -maxtime=$timelim -defobj=$defobj &> out_${alg}_defobj &
    sleep 1
done 
