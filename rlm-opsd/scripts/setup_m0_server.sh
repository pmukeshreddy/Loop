#!/usr/bin/env bash
# Install the pinned M0 stack and M1 support packages; no model download/training.
# Target: Linux x86_64 with an NVIDIA A100/H100-class GPU and CUDA-capable driver.
set -Eeuo pipefail

cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    echo "M0 server setup requires Linux x86_64; this host is $(uname -sm)." >&2
    exit 2
fi
for command in git uvx nvidia-smi; do
    command -v "$command" >/dev/null || { echo "Required command missing: $command" >&2; exit 2; }
done

M0_ROOT="$PWD"
M0_ENV="$M0_ROOT/.venv-server"
M0_LOG_DIR="$M0_ROOT/docs/logs/m0-server/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$M0_LOG_DIR" .deps
exec > >(tee "$M0_LOG_DIR/setup.log") 2>&1
trap 'echo "M0 server setup failed at line $LINENO; see $M0_LOG_DIR/setup.log" >&2' ERR
set -x
date -u
uname -sm
nvidia-smi

m0_uv() { uvx --from 'uv==0.11.1' uv "$@"; }
m0_uv python install 3.12.12
M0_PYTHON="$(m0_uv python find --managed-python 3.12.12)"

# Derive all project pins from pyproject.toml; no independent moving refs.
"$M0_PYTHON" - "$M0_LOG_DIR" <<'PY'
from pathlib import Path
import re, sys, tomllib
p = tomllib.loads(Path('pyproject.toml').read_text())
requirements = p['project']['dependencies']
log = Path(sys.argv[1])
(log / 'primary.txt').write_text('\n'.join(requirements) + '\n')
(log / 'rlm.in').write_text('\n'.join(r for r in requirements if not r.startswith('prime-rl')) + '\n')
names = {'rlms': 'rlm', 'verifiers': 'verifiers', 'prime-rl': 'prime-rl'}
rows = []
for requirement in requirements:
    name, separator, url = requirement.partition(' @ ')
    if name not in names:
        continue
    assert separator, f'Source pin required for {name}'
    rev = re.search(r'[0-9a-f]{40}', url).group()
    remote = url.removeprefix('git+').split('@', 1)[0] if url.startswith('git+') else url.split('/archive/')[0] + '.git'
    rows.append(f'{names[name]} {remote} {rev}')
(log / 'sources.txt').write_text('\n'.join(rows) + '\n')
PY

while read -r name remote revision; do
    checkout="$M0_ROOT/.deps/$name"
    if [[ ! -e "$checkout" ]]; then
        git clone --no-checkout "$remote" "$checkout"
        git -C "$checkout" checkout --detach "$revision"
    fi
    [[ "$(git -C "$checkout" rev-parse HEAD)" == "$revision" ]]
    if [[ "$name" == prime-rl ]]; then
        "$M0_PYTHON" -m rlm_opsd.training.prime_patch --source "$checkout" --check
    else
        git -C "$checkout" diff --exit-code HEAD
    fi
done < "$M0_LOG_DIR/sources.txt"

# Initialize only the upstream public workspace members. Per-command HTTPS
# rewriting avoids SSH credentials and leaves global Git configuration alone.
git -C .deps/prime-rl -c 'url.https://github.com/.insteadOf=git@github.com:' \
    submodule update --init -- deps/verifiers deps/renderers deps/research-environments deps/pydantic-config

# Use upstream's immutable runtime lock and its prebuilt FlashAttention 2 extra.
# FA2 is the pinned trainer's default and is shared by the A100/H100 setup.
UV_PROJECT_ENVIRONMENT="$M0_ENV" m0_uv sync --project .deps/prime-rl \
    --python "$M0_PYTHON" --frozen --no-dev --extra flash-attn

# Constrain RLM additions to versions actually installed from the upstream lock.
"$M0_ENV/bin/python" - "$M0_LOG_DIR/runtime-constraints.txt" <<'PY'
import importlib.metadata as md
from pathlib import Path
import sys
lines = sorted(f"{d.metadata['Name']}=={d.version}" for d in md.distributions())
Path(sys.argv[1]).write_text('\n'.join(lines) + '\n')
PY
m0_uv pip install --python "$M0_ENV/bin/python" \
    --constraint "$M0_LOG_DIR/runtime-constraints.txt" \
    -r requirements-m0-server-additions.lock
m0_uv pip install --python "$M0_ENV/bin/python" \
    --constraint "$M0_LOG_DIR/runtime-constraints.txt" -r requirements-m1.txt
m0_uv pip install --python "$M0_ENV/bin/python" 'pip==25.3'

# Replace editable project wheels with the exact pinned artifacts used by the
# source checks. Dependencies were installed above and are checked below.
# pip's PEP 517 builder handles the config subdirectory archive without uv's
# missing-workspace-member build error (reproduced in local M0 logs).
"$M0_ENV/bin/python" -m pip install --no-deps -r "$M0_LOG_DIR/primary.txt"
m0_uv pip check --python "$M0_ENV/bin/python"
"$M0_ENV/bin/python" scripts/check_m0.py
"$M0_ENV/bin/rl" --help
"$M0_ENV/bin/python" - <<'PY'
import torch, flash_attn, vllm
assert torch.cuda.is_available(), 'CUDA is unavailable'
assert torch.cuda.get_device_capability()[0] >= 8, 'An Ampere-or-newer GPU is required'
print('torch', torch.__version__, 'CUDA', torch.version.cuda)
print('flash_attn', flash_attn.__version__, 'vllm', vllm.__version__)
print('GPU', torch.cuda.get_device_name(), torch.cuda.get_device_capability())
PY
m0_uv pip freeze --python "$M0_ENV/bin/python" > "$M0_LOG_DIR/installed.txt"
echo "M0 server dependency/import checks passed. No model or training run was started."
