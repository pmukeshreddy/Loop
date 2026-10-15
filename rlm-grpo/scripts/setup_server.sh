#!/usr/bin/env bash
# Install GRPO's own environment from the pinned Prime-RL runtime lock.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    echo "GRPO setup requires Linux x86_64 with a CUDA-capable NVIDIA driver." >&2
    exit 2
fi
for command in git uvx nvidia-smi; do
    command -v "$command" >/dev/null || { echo "Required command missing: $command" >&2; exit 2; }
done

GRPO_ROOT="$PWD"
GRPO_ENV="$GRPO_ROOT/.venv-server"
mkdir -p .deps
grpo_uv() { uvx --from 'uv==0.11.1' uv "$@"; }
grpo_uv python install 3.12.12
GRPO_PYTHON="$(grpo_uv python find --managed-python 3.12.12)"

"$GRPO_PYTHON" - <<'PY'
from pathlib import Path
import re
import tomllib

requirements = tomllib.loads(Path('pyproject.toml').read_text())['project']['dependencies']
Path('.deps/grpo-primary.txt').write_text('\n'.join(requirements) + '\n')
source = next(r for r in requirements if r.startswith('prime-rl @ '))
Path('.deps/prime-revision').write_text(re.search(r'[0-9a-f]{40}', source).group() + '\n')
PY
GRPO_REVISION="$(cat .deps/prime-revision)"
if [[ ! -e .deps/prime-rl ]]; then
    git clone --no-checkout https://github.com/PrimeIntellect-ai/prime-rl.git .deps/prime-rl
    git -C .deps/prime-rl checkout --detach "$GRPO_REVISION"
fi
[[ "$(git -C .deps/prime-rl rev-parse HEAD)" == "$GRPO_REVISION" ]]
if [[ -n "$(git -C .deps/prime-rl status --porcelain --untracked-files=normal)" ]]; then
    echo "Use a pristine GRPO Prime-RL checkout; modified checkouts are not supported." >&2
    exit 2
fi
git -C .deps/prime-rl -c 'url.https://github.com/.insteadOf=git@github.com:' \
    submodule update --init -- deps/verifiers deps/renderers deps/research-environments deps/pydantic-config
UV_PROJECT_ENVIRONMENT="$GRPO_ENV" grpo_uv sync --project .deps/prime-rl \
    --python "$GRPO_PYTHON" --frozen --no-dev --extra flash-attn

"$GRPO_ENV/bin/python" - <<'PY'
import importlib.metadata as md
from pathlib import Path

Path('.deps/runtime-constraints.txt').write_text('\n'.join(sorted(
    f"{d.metadata['Name']}=={d.version}" for d in md.distributions())) + '\n')
PY
grpo_uv pip install --python "$GRPO_ENV/bin/python" \
    --constraint .deps/runtime-constraints.txt -r requirements-rlm.lock
grpo_uv pip install --python "$GRPO_ENV/bin/python" 'pip==25.3'
# pip handles the pinned config subdirectory archive without uv's workspace
# member build failure. Dependencies already come from the runtime lock above.
"$GRPO_ENV/bin/python" -m pip install --no-deps -r .deps/grpo-primary.txt
"$GRPO_ENV/bin/python" -m pip install --no-deps -e .
"$GRPO_ENV/bin/python" -m pip check
echo "GRPO environment installed. No rollouts, tests, or training were run."
