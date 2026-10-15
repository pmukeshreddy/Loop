#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'USAGE'
Usage: bash scripts/push.sh [--dry-run] [--remote REPOSITORY]

Publish the files listed in scripts/push-manifest.json to main.
Default repository: https://github.com/pmukeshreddy/Loop.git
--dry-run clones and stages the changes for inspection.
--remote selects another repository URL or local path.
USAGE
}

dry_run=false
remote='https://github.com/pmukeshreddy/Loop.git'
while (($#)); do
    case "$1" in
        --dry-run) dry_run=true; shift ;;
        --remote)
            if (($# < 2)) || [[ -z "$2" || "$2" == -* ]]; then
                printf '%s\n' '--remote requires a repository URL or path.' >&2
                exit 2
            fi
            remote="$2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

for dependency in git python3; do
    command -v "$dependency" >/dev/null || {
        printf 'Required command missing: %s\n' "$dependency" >&2
        exit 2
    }
done

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="$project_root/scripts/push-manifest.json"
expected_head="$(python3 - "$project_root" "$manifest" <<'PY'
from pathlib import Path
import json
import re
import sys

root = Path(sys.argv[1])
manifest = json.loads(Path(sys.argv[2]).read_text())
head = manifest['expected_head']
if not re.fullmatch(r'[0-9a-f]{40}', head):
    raise SystemExit('The publish manifest requires a full base commit SHA.')
for name in manifest['write'] + manifest['delete']:
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or '.git' in path.parts:
        raise SystemExit(f'Invalid publish path: {name}')
for name in manifest['write']:
    if not (root / name).is_file():
        raise SystemExit(f'Missing source file: {name}')
print(head)
PY
)"

checkout_dir="$(mktemp -d "${TMPDIR:-/tmp}/loop-publish.XXXXXX")"
trap 'printf "Publish checkout retained at: %s\n" "$checkout_dir" >&2' ERR
git clone --quiet --branch main --single-branch -- "$remote" "$checkout_dir"
if [[ "$(git -C "$checkout_dir" rev-parse HEAD)" != "$expected_head" ]]; then
    printf 'main has changed since this publish manifest was prepared. Reconcile the source with main before publishing.\nCheckout: %s\n' "$checkout_dir" >&2
    exit 1
fi

python3 - "$project_root" "$checkout_dir" "$manifest" <<'PY'
from pathlib import Path
import json
import shutil
import sys

root, checkout, manifest_path = map(Path, sys.argv[1:])
manifest = json.loads(manifest_path.read_text())
for name in manifest['write']:
    destination = checkout / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Existing files retain their Git executable bit.
    if destination.exists():
        shutil.copyfile(root / name, destination)
    else:
        shutil.copy2(root / name, destination)
for name in manifest['delete']:
    (checkout / name).unlink(missing_ok=True)
PY

git -C "$checkout_dir" add --all
git -C "$checkout_dir" diff --cached --check
git -C "$checkout_dir" diff --cached --stat
if git -C "$checkout_dir" diff --cached --quiet; then
    printf 'No changes to publish.\n'
    exit 0
fi
if "$dry_run"; then
    printf 'Dry run complete. Inspect with: git -C %q diff --cached\n' "$checkout_dir"
    exit 0
fi

git -C "$checkout_dir" config --local user.name "${GIT_AUTHOR_NAME:-mukesh reddy p}"
git -C "$checkout_dir" config --local user.email "${GIT_AUTHOR_EMAIL:-mukeshreddy662369@gmail.com}"
git -C "$checkout_dir" commit \
    -m 'refactor: separate GRPO and clarify project documentation' \
    -m 'Give GRPO its own package and server environment, remove the former nested integration, and document implementation behavior and verification scope.'
git -C "$checkout_dir" push origin HEAD:refs/heads/main
local_sha="$(git -C "$checkout_dir" rev-parse HEAD)"
remote_sha="$(git -C "$checkout_dir" ls-remote origin refs/heads/main | cut -f1)"
if [[ "$local_sha" != "$remote_sha" ]]; then
    printf 'Push completed, but main changed before verification. Inspect %s\n' "$checkout_dir" >&2
    exit 1
fi
printf 'Verified main at %s\n' "$local_sha"
