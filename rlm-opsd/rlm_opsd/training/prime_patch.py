"""Apply the reviewed patch to the exact source pin; never edit site-packages."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / 'patches/prime-rl-opsd.patch'
MANIFEST = ROOT / 'patches/prime-rl-opsd.json'


def patch_manifest():
    return json.loads(MANIFEST.read_text())


def apply_patch(source, *, verify_commit=True, check_only=False):
    source = Path(source).resolve()
    manifest = patch_manifest()
    if verify_commit:
        result = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                check=True, capture_output=True, text=True)
        if result.stdout.strip() != manifest['commit']:
            raise ValueError('prime-rl checkout is not the required pinned commit')
    states = set()
    for relative, hashes in manifest['files'].items():
        path = source / relative
        if not path.resolve().is_relative_to(source):
            raise ValueError('patch source path escapes checkout')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        matches = [state for state in ('before', 'after') if digest == hashes[state]]
        if len(matches) != 1:
            raise ValueError('modified prime-rl source/hash drift: ' + relative)
        states.add(matches[0])
    if verify_commit:
        changed = set(subprocess.check_output(
            ['git', '-C', str(source), 'diff', '--name-only', 'HEAD'], text=True).splitlines())
        expected = set(manifest['files']) if states == {'after'} else set()
        if changed != expected:
            raise ValueError('prime-rl checkout contains source drift outside the complete reviewed patch')
    if states == {'after'}:
        return 'already_applied'
    if states != {'before'}:
        raise ValueError('partially modified prime-rl checkout; restore the complete pinned source')
    if check_only:
        return 'not_applied'
    subprocess.run(['git', 'apply', '--check', str(PATCH)], cwd=source, check=True, capture_output=True)
    subprocess.run(['git', 'apply', str(PATCH)], cwd=source, check=True, capture_output=True)
    for relative, hashes in manifest['files'].items():
        if hashlib.sha256((source / relative).read_bytes()).hexdigest() != hashes['after']:
            raise ValueError('patched source hash mismatch: ' + relative)
    return 'applied'


def source_paths(source):
    source = Path(source).resolve()
    return [str(source / 'src'), str(source / 'packages/prime-rl-configs/src'), str(ROOT)]


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / '.deps/prime-rl')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(apply_patch(args.source, check_only=args.check))
