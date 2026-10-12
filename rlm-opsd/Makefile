.PHONY: test test-m1 test-m2 test-m3 test-m4 test-m5 teacher-gate teacher-gate-check prompts-prepare prompts-check tasks tasks-prepare tasks-generate tasks-verify tasks-status check-deps setup-server

PYTHON ?= .venv/bin/python

# Offline dependency checks and all implemented milestone tests.
test: prime-opsd-patch
	$(PYTHON) scripts/check_m0.py
	PYTHONPATH="$(PRIME_SOURCE)/src:$(PRIME_SOURCE)/packages/prime-rl-configs/src:." "$(PYTHON)" -m pytest tests -q

test-m1:
	$(PYTHON) -m pytest tests/test_harness.py tests/test_verifiers_env.py tests/test_setup_manifest.py -q

test-m2:
	$(PYTHON) -m pytest tests/test_task_generation.py tests/test_task_release.py tests/test_heldout_tasks.py -q

test-m3:
	$(PYTHON) -m pytest tests/test_prompts.py tests/test_verifiers_env.py -q

test-m4:
	$(PYTHON) -m pytest tests/test_detectors.py tests/test_detector_categories.py tests/test_detector_reports.py tests/test_detector_trace_metadata.py tests/test_detector_cli.py -q

test-m5:
	$(PYTHON) -m pytest tests/test_teacher_gate.py tests/test_teacher_gate_cli.py -q

.PHONY: test-m6
test-m6:
	$(PYTHON) -m pytest tests/test_training_samples.py tests/test_training_teacher.py tests/test_training_runner.py -q

.PHONY: test-m7 opsd opsd-check
test-m7:
	$(PYTHON) -m pytest tests/test_training_jsd.py tests/test_training_opsd.py tests/test_training_opsd_runner.py -q

OPSD_CONFIG ?= configs/opsd.toml
OPSD_OUTPUT ?= reports/opsd-27b

opsd:
	$(PYTHON) -m rlm_opsd.training smoke --config "$(OPSD_CONFIG)" --output "$(OPSD_OUTPUT)"

opsd-check:
	$(PYTHON) -m rlm_opsd.training smoke --config "$(OPSD_CONFIG)" --check

.PHONY: opsd-train opsd-train-check test-opsd-train prime-opsd-patch
OPSD_TRAIN_CONFIG ?= configs/opsd_train.toml
PRIME_SOURCE ?= .deps/prime-rl

opsd-train:
	"$(PYTHON)" -m rlm_opsd.training.prime_launch --config "$(OPSD_TRAIN_CONFIG)" --source "$(PRIME_SOURCE)"

opsd-train-check:
	"$(PYTHON)" -m rlm_opsd.training.prime_launch --config "$(OPSD_TRAIN_CONFIG)" --source "$(PRIME_SOURCE)" --check

prime-opsd-patch:
	"$(PYTHON)" -m rlm_opsd.training.prime_patch --source "$(PRIME_SOURCE)"

test-opsd-train: prime-opsd-patch
	PYTHONPATH="$(PRIME_SOURCE)/src:$(PRIME_SOURCE)/packages/prime-rl-configs/src:." "$(PYTHON)" -m pytest tests/test_prime_opsd_*.py -q

GATE_CONFIG ?= configs/gate.yaml
GATE_OUTPUT ?= reports/teacher-gate-manual_v1

teacher-gate:
	$(PYTHON) -m rlm_opsd.eval teacher-gate --config "$(GATE_CONFIG)" --output "$(GATE_OUTPUT)"

teacher-gate-check:
	$(PYTHON) -m rlm_opsd.eval teacher-gate --config "$(GATE_CONFIG)" --check

prompts-prepare:
	$(PYTHON) -m rlm_opsd.prompts prepare

prompts-check:
	$(PYTHON) -m rlm_opsd.prompts check --thinking on
	$(PYTHON) -m rlm_opsd.prompts check --thinking off

TASK_CONFIG ?= configs/tasks.yaml
TASK_OUTPUT ?= data

# Pin sources, record baselines, split repositories and index held-out data.
tasks-prepare:
	$(PYTHON) -m rlm_opsd.tasks prepare --config $(TASK_CONFIG)

# Resumable model-driven generation (OpenAI via step1.auth); safe to rerun.
tasks-generate: tasks-prepare
	$(PYTHON) -m rlm_opsd.tasks generate --config $(TASK_CONFIG)

tasks: tasks-generate
	$(PYTHON) -m rlm_opsd.tasks build --config $(TASK_CONFIG) --output $(TASK_OUTPUT)

# Re-run executable verification of a released pool; no model requests.
tasks-verify:
	$(PYTHON) -m rlm_opsd.tasks verify --config $(TASK_CONFIG) --manifest $(TASK_OUTPUT)/manifest.jsonl

tasks-status:
	$(PYTHON) -m rlm_opsd.tasks status --config $(TASK_CONFIG)

# This must also pass before the full M0 installation can be called complete.
check-deps:
	uv pip check --python $(PYTHON)

setup-server:
	bash scripts/setup_m0_server.sh

.PHONY: test-m8 eval-behavior eval-behavior-check exit-check exit-check-check
test-m8:
	"$(PYTHON)" -m pytest tests/test_monitor_metrics.py tests/test_monitor_scoring.py tests/test_monitor_runner.py tests/test_monitor_cli.py tests/test_exit_check.py tests/test_retention.py -q

EVAL_CONFIG ?= configs/eval.yaml
EVAL_OUTPUT ?= reports/eval-behavior
EXIT_CONFIG ?= configs/exit.yaml
EXIT_OUTPUT ?= reports/exit-check

eval-behavior:
	"$(PYTHON)" -m rlm_opsd.eval eval-behavior --config "$(EVAL_CONFIG)" --output "$(EVAL_OUTPUT)"

eval-behavior-check:
	"$(PYTHON)" -m rlm_opsd.eval eval-behavior --config "$(EVAL_CONFIG)" --check

exit-check:
	"$(PYTHON)" -m rlm_opsd.eval exit-check --config "$(EXIT_CONFIG)" --output "$(EXIT_OUTPUT)"

exit-check-check:
	"$(PYTHON)" -m rlm_opsd.eval exit-check --config "$(EXIT_CONFIG)" --check
