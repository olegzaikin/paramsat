timelim=180
pointslim=50
#Optuna-CatCMA
defobj=9.55
maxsolvertime=5
for alg in 1+1 Optuna-TPE Optuna-HillClimbing 
do
    echo $alg
    python3 ./bbo_param_solver.py ./kissat4.0.1_quiet ./kissat4.0.1_reduced.pcs ./cnfs_easy/ -optalg=${alg} -seed=0 -maxpoints=${pointslim} -maxtime=$timelim -defobj=${defobj} -maxsolvertime=${maxsolvertime} &> out_test_${alg}_defobj &
    sleep 1
done
