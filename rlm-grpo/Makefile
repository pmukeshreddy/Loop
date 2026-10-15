.PHONY: setup-server grpo-train grpo-check grpo-smoke grpo-prepare-images

PYTHON ?= .venv-server/bin/python
PRIME_SOURCE ?= .deps/prime-rl
GRPO_CONFIG ?= configs/grpo.toml
GRPO_MANIFEST ?= data/grpo/manifest.jsonl
GRPO_HELDOUT ?= ../data/deep-swe/tasks

setup-server:
	bash scripts/setup_server.sh

grpo-train:
	"$(PYTHON)" -m rlm_grpo train --config "$(GRPO_CONFIG)" --source "$(PRIME_SOURCE)"

grpo-check:
	"$(PYTHON)" -m rlm_grpo check --config "$(GRPO_CONFIG)" --source "$(PRIME_SOURCE)"

grpo-smoke:
	"$(PYTHON)" -m rlm_grpo train --config "$(GRPO_CONFIG)" --source "$(PRIME_SOURCE)" --max-steps 1

grpo-prepare-images:
	"$(PYTHON)" -m rlm_grpo prepare-images --manifest "$(GRPO_MANIFEST)" --heldout-dir "$(GRPO_HELDOUT)"
