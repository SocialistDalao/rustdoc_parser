env:
	pip install -r requirements.txt

run:
	python3 parse.py complete > run.log

run_parallel1:
	python3 parse.py complete_selected 1 30 > run1_30.log

run_parallel2:
	python3 parse.py complete_selected 31 50 > run31_50.log

run_parallel2:
	python3 parse.py complete_selected 51 63 > run51_63.log