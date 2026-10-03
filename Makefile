.PHONY: setup lint test compose-up seed

setup:
bash scripts/setup.sh

lint:
bash scripts/lint.sh

test:
bash scripts/test.sh

compose-up:
bash scripts/compose-up.sh

seed:
bash scripts/seed.sh