"""M5 teacher gate; no training or checkpoint monitoring."""
from .config import GateConfig, GateCriterion
from .decision import evaluate_gate
from .preflight import prepare_gate, check_readiness

__all__=['GateConfig','GateCriterion','evaluate_gate','prepare_gate','check_readiness']
from .gate import run_gate
__all__.append('run_gate')
