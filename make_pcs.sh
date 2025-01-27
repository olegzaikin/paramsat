kissat3.0.0 --range > range3 && kissat4.0.1 --range > range4
python3 ./intersect_params.py ./range3 ./range4
python3 ./convert_to_pcs.py ./range_intersection
mv range_intersection.pcs kissat4.0.1_reduced.pcs
