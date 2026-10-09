"""Reproduce M6 source/signature/pin checks; no model weights or inference."""
import ast
import hashlib
from importlib.metadata import distribution, version
import inspect
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
source=ROOT/'.deps/prime-rl'
installed=Path(distribution('prime-rl').locate_file('prime_rl'))
print('prime HEAD',subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip())
files={
    'trainer/model.py':['get_model','forward'],
    'trainer/runs.py':['MultiRunManager','setup_multi_run_manager'],
    'trainer/lora.py':['apply_lora_to_model','freeze_all_except_lora_and_specified'],
    'trainer/models/layers/lora/base.py':['set_lora_num_tokens','set_multilora_scaling'],
    'trainer/models/layers/lora/multi_linear.py':['MultiLoRALinear','_run_lora_for_loop'],
    'trainer/models/layers/lm_head.py':['VanillaOutputLinear','inject_prime_lm_head','_patch_model_forward'],
    'trainer/rl/loss.py':['LossInputs','LossOutputs','default_loss_fn'],
    'transport/types.py':['TrainingSample','MicroBatch'],
}
for relative,symbols in files.items():
    path=source/'src/prime_rl'/relative
    data=path.read_bytes()
    assert data==(installed/relative).read_bytes(),relative
    print('SOURCE',str(path.relative_to(ROOT)),'SHA256',hashlib.sha256(data).hexdigest(),'INSTALLED_BYTES_IDENTICAL')
    tree=ast.parse(data)
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in symbols:
            signature=ast.unparse(node.args) if isinstance(node,ast.FunctionDef) else ', '.join(
                ast.unparse(n) for n in node.body if isinstance(n,ast.AnnAssign))
            print('SYMBOL',node.name,'LINE',node.lineno,signature)
    if relative=='transport/types.py':
        for node in tree.body:
            if isinstance(node,ast.ClassDef) and node.name in symbols:
                assert not any('teacher_prefix' in ast.unparse(n) for n in node.body)

from prime_rl.configs.trainer import DefaultLossConfig,ModelConfig,LoRAConfig
cfg=ModelConfig(name='pinned-cache-snapshot',impl='hf',attn='eager',seq_len=4096,
    lora=LoRAConfig(rank=16,alpha=32,dropout=0,target_modules=['q_proj','k_proj','v_proj','o_proj'],modules_to_save=[]),
    compile=None,ac=None,cp=1,ep=1,fused_lm_head_token_chunk_size='disabled')
print('VALIDATED_MODEL_KEYS',json.dumps({k:cfg.model_dump(mode='json')[k] for k in (
    'name','impl','attn','seq_len','lora','compile','ac','cp','ep','fused_lm_head_token_chunk_size')},sort_keys=True))
print('NATIVE_LOSS_CONFIG',DefaultLossConfig(adv_tau=0,teacher_tau=1,kl_tau=0,dppo_mask_low=1,dppo_mask_high=1).model_dump())
from huggingface_hub import snapshot_download
import torch
print('snapshot_download',inspect.signature(snapshot_download))
for package in ('torch','transformers','huggingface-hub','beartype','jaxtyping','loguru','networkx','setuptools','wadler-lindig'):
    print('LOCAL_VERSION',package,version(package))
print('RUNTIME',sys.platform,'CUDA',torch.cuda.is_available(),'not a pretrained smoke')

from rlm_opsd.prompts import PromptConfig,PromptBuilder,ChatRenderer
from rlm_opsd.harness import HarnessConfig
from rlm_opsd.training.config import OpsdConfig
for suffix in ('_small',''):
    opsd=OpsdConfig.from_toml(ROOT/f'configs/opsd_mode_a{suffix}.toml')
    prompt=PromptConfig.from_yaml(opsd.prompt_config)
    pair=PromptBuilder.load().build(query='Return the context length.',context='CPU configuration fixture',config=HarnessConfig.from_yaml(ROOT/'configs/harness.yaml'))
    prefixes=ChatRenderer(prompt).prefixes(pair)
    print('PINNED_PREFIX_FIXTURE',opsd.stage,opsd.base_model,opsd.revision,
          len(prefixes.student_ids),len(prefixes.teacher_ids),prompt.template_sha256)

urls={
    'qwen27_generation_config':'https://huggingface.co/Qwen/Qwen3.5-27B/resolve/fc05daec18b0a78c049392ed2e771dde82bdf654/generation_config.json',
    'vllm_sampling_params':'https://raw.githubusercontent.com/vllm-project/vllm/v0.21.0/vllm/sampling_params.py',
    'vllm_model_config':'https://raw.githubusercontent.com/vllm-project/vllm/v0.21.0/vllm/config/model.py',
}
for name,url in urls.items():
    data=urllib.request.urlopen(url,timeout=45).read()
    print('PRIMARY_SOURCE',name,url,'SHA256',hashlib.sha256(data).hexdigest())
    if name=='qwen27_generation_config':print(data.decode())
    else:
        needles=('presence_penalty:','frequency_penalty:','repetition_penalty:',
                 'top_p:','top_k:','min_p:','logprobs_mode:','processed_logprobs')
        for number,line in enumerate(data.decode().splitlines(),1):
            if any(needle in line for needle in needles):print(number,line.strip())
print('Source/config checks passed; real small/27B pretrained smokes NOT RUN.')
