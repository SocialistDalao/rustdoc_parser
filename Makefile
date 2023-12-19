env:
	pip install -r requirements.txt

run:
	python3 parse.py complete > run.log

run_parallel1:
	python3 parse.py complete_selected 1 30 > run1_30.log

run_parallel2:
	python3 parse.py complete_selected 31 50 > run31_50.log

run_parallel2:
	python3 parse.py complete_selected 51 63 > run51_63.logbash for loop

rust_env:
	rustup component add rustc-dev llvm-tools

rust_api_parser:
	rustc parse_api_token.rs
	rustup run nightly ./parse_api_token

LAST := 63
NUMBERS := $(shell seq 1 ${LAST})
results:
	for number in ${NUMBERS}; do \
		cat tmp.txt | grep "1.$$number.0 "; \
	done