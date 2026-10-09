.PHONY: test test-m1 test-m2 test-m3 test-m4 test-m5 teacher-gate teacher-gate-check prompts-prepare prompts-check tasks tasks-prepare tasks-verify check-deps setup-server

PYTHON ?= .venv/bin/python

# Offline dependency checks and all implemented milestone tests.
test:
	$(PYTHON) scripts/check_m0.py
	$(PYTHON) -m pytest tests -q

test-m1:
	$(PYTHON) -m pytest tests/test_harness.py tests/test_verifiers_env.py tests/test_setup_manifest.py -q

test-m2:
	$(PYTHON) -m pytest tests/test_tasks.py tests/test_task_pipeline.py tests/test_heldout_tasks.py tests/test_task_cli.py -q

test-m3:
	$(PYTHON) -m pytest tests/test_prompts.py tests/test_verifiers_env.py -q

test-m4:
	$(PYTHON) -m pytest tests/test_detectors.py tests/test_detector_categories.py tests/test_detector_reports.py tests/test_detector_trace_metadata.py tests/test_detector_cli.py -q

test-m5:
	$(PYTHON) -m pytest tests/test_teacher_gate.py tests/test_teacher_gate_cli.py -q

.PHONY: test-m6 opsd-a opsd-a-check
test-m6:
	$(PYTHON) -m pytest tests/test_training_samples.py tests/test_training_teacher.py tests/test_training_runner.py -q

OPSD_CONFIG ?= configs/opsd_mode_a.toml
OPSD_OUTPUT ?= reports/opsd-a-27b

opsd-a:
	$(PYTHON) -m rlm_opsd.training smoke --config "$(OPSD_CONFIG)" --output "$(OPSD_OUTPUT)"

opsd-a-check:
	$(PYTHON) -m rlm_opsd.training smoke --config "$(OPSD_CONFIG)" --check

.PHONY: test-m7 opsd-b opsd-b-check
test-m7:
	$(PYTHON) -m pytest tests/test_training_jsd.py tests/test_training_mode_b.py tests/test_training_mode_b_runner.py -q

OPSD_B_CONFIG ?= configs/opsd_mode_b.toml
OPSD_B_OUTPUT ?= reports/opsd-b-27b

opsd-b:
	$(PYTHON) -m rlm_opsd.training smoke --config "$(OPSD_B_CONFIG)" --output "$(OPSD_B_OUTPUT)"

opsd-b-check:
	$(PYTHON) -m rlm_opsd.training smoke --config "$(OPSD_B_CONFIG)" --check

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

tasks-prepare:
	$(PYTHON) -m rlm_opsd.tasks prepare --config $(TASK_CONFIG)

tasks: tasks-prepare
	$(PYTHON) -m rlm_opsd.tasks build --config $(TASK_CONFIG) --output $(TASK_OUTPUT)

tasks-verify:
	$(PYTHON) -m rlm_opsd.tasks verify --config $(TASK_CONFIG) --manifest $(TASK_OUTPUT)/manifest.jsonl

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
