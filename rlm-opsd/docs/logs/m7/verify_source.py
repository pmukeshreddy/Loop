"""M7 API/pin and numerical-fixture evidence; no model weights or network."""
import hashlib
import inspect
from importlib.metadata import distribution,version
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import torch
from torch.autograd.function import once_differentiable
from rlm_opsd.training.config import OpsdConfig
from rlm_opsd.training.jsd import masked_jsd_loss,chunked_jsd_loss
from rlm_opsd.training.mode_b import backbone_hidden,ModeBTrainer

source=ROOT/'.deps/prime-rl'
head=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
assert head=='09e11c7527a242b9f150c7c4c71b1b96da66cb75'
print('PRIME_PIN',head)
installed=Path(distribution('prime-rl').locate_file('prime_rl'))
for relative in ('trainer/model.py','trainer/models/layers/lm_head.py','trainer/models/layers/lora/base.py',
                 'trainer/models/layers/lora/multi_linear.py','trainer/lora.py'):
    path=source/'src/prime_rl'/relative;data=path.read_bytes()
    assert data==(installed/relative).read_bytes()
    print('PINNED_SOURCE',path.relative_to(ROOT),hashlib.sha256(data).hexdigest(),'installed bytes identical')
for obj in (torch.autograd.Function,torch.autograd.grad,once_differentiable,
            torch.autograd.graph.saved_tensors_hooks,torch.nn.functional.log_softmax,
            masked_jsd_loss,chunked_jsd_loss,backbone_hidden,ModeBTrainer):
    path=Path(inspect.getfile(obj))
    print('API',obj.__qualname__,inspect.signature(obj),path,hashlib.sha256(path.read_bytes()).hexdigest())
print('FUNCTIONAL_LINEAR',torch.nn.functional.linear.__doc__.splitlines()[1])
for name in ('torch','transformers','prime-rl','verifiers'):print('LOCAL_VERSION',name,version(name))
print('RUNTIME',sys.platform,'CUDA',torch.cuda.is_available())
for suffix in ('_small',''):
    cfg=OpsdConfig.from_toml(ROOT/f'configs/opsd_mode_b{suffix}.toml')
    print('VALIDATED_CONFIG',json.dumps(cfg.model_dump(mode='json'),sort_keys=True))

student=torch.tensor([[.25,.75]],dtype=torch.float64).log().requires_grad_()
teacher=torch.tensor([[.75,.25]],dtype=torch.float64).log().requires_grad_()
value=chunked_jsd_loss(student,teacher,torch.eye(2,dtype=torch.float64),torch.tensor([True]),chunk_size=1)
value.backward()
print('ANALYTICAL_CPU_FIXTURE',json.dumps(dict(jsd=value.item(),student_gradient=student.grad.tolist(),
    teacher_gradient_is_none=teacher.grad is None,source='Hand-derived binary distribution; NOT MODEL RESULTS')))
print('GPU/pretrained small and 27B Mode B smokes NOT RUN. Backbone memory/peak GPU allocation NOT MEASURED.')
