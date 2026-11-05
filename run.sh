timelim=3600
pointslim=10000
for alg in Optuna-TPE Optuna-HillClimbing Optuna-HillClimbing-TPE Nevergrad-PortfolioDiscreteOnePlusOne Nevergrad-DiscreteOnePlusOne Nevergrad-NGOpt
do
    echo $alg
    python3 ./bbo_param_solver.py ./kissat4.0.1_quiet ./kissat4.0.1_reduced.pcs ./cnfs_easy/ -optalg=${alg} -seed=0 -maxpoints=${pointslim} -maxtime=$timelim &> out_${alg} &
    sleep 1
done 
