# Thin wrapper around run.sh so `make <stage>` and `./run.sh <stage>` do the same thing.
.PHONY: setup load profile build test scorecard docs sources all monitor

setup load profile build test scorecard docs sources all monitor:
	bash ./run.sh $@
