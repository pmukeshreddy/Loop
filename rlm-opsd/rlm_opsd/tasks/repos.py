"""Pinned source repositories, isolated checkouts, sandboxed test execution."""
import asyncio
from dataclasses import dataclass
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

from .models import slug

PLUGIN = Path(__file__).with_name('pytest_report.py')
SECRET_PATHS = ('.phase1-auth', '.codex', '.ssh', '.aws', '.config/gh', '.netrc', '.docker',
                'Library/Keychains', '.anthropic', '.openai')
TEXT_SUFFIXES = {'.py', '.pyi', '.md', '.rst', '.txt', '.toml', '.cfg', '.ini', '.json', '.yaml',
                 '.yml', '.lark', '.html', '.j2', '.jinja', '.sql', '.csv', '.in'}
CONFIG_NAMES = {'pyproject.toml', 'setup.cfg', 'setup.py', 'tox.ini', 'pytest.ini', 'MANIFEST.in'}


@dataclass(frozen=True)
class RepoSpec:
    name: str
    url: str
    ref: str
    commit: str
    license: str
    pythonpath: tuple = ('.',)
    test_paths: tuple = ('tests',)
    test_deps: tuple = ('pytest',)
    pytest_args: tuple = ()

    @property
    def slug(self):
        return slug(self.name)

    @classmethod
    def from_config(cls, raw):
        values = dict(raw)
        for key in ('pythonpath', 'test_paths', 'test_deps', 'pytest_args'):
            if key in values:
                values[key] = tuple(values[key])
        if not re.fullmatch(r'[0-9a-f]{40}', values.get('commit', '')):
            raise ValueError(f'{raw.get("name")}: pin a full 40-character commit')
        return cls(**values)

    def is_test_path(self, path):
        parts = path.split('/')
        name = parts[-1]
        return (any(path == p or path.startswith(p.rstrip('/') + '/') for p in self.test_paths)
                or name.startswith('test_') or name.endswith('_test.py') or name == 'conftest.py'
                or any(part in ('tests', 'test', 'testing') for part in parts[:-1]))


@dataclass
class TestRun:
    outcomes: dict
    exit_code: int
    log: str
    duration_s: float
    timed_out: bool = False

    def failing(self):
        return {k for k, v in self.outcomes.items() if v in ('failed', 'error')}

    def passing(self):
        return {k for k, v in self.outcomes.items() if v in ('passed', 'xfailed')}


def _run(cmd, **kwargs):
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{" ".join(map(str, cmd[:4]))} failed: {result.stderr.strip()[-800:]}')
    return result.stdout


def tree_digest(root):
    entries = []
    for path in sorted(p for p in Path(root).rglob('*') if p.is_file()):
        entries.append(f'{path.relative_to(root).as_posix()}\0{hashlib.sha256(path.read_bytes()).hexdigest()}')
    return hashlib.sha256('\n'.join(entries).encode()).hexdigest(), len(entries)


class Workspace:
    """Clone, exported tree and virtualenv for one pinned repository."""

    def __init__(self, spec: RepoSpec, sources_dir, python='3.12'):
        self.spec, self.python_version = spec, python
        root = Path(sources_dir).resolve()
        self.clone = root / 'clones' / spec.slug
        self.tree = root / 'trees' / spec.slug
        self.venv = root / 'venvs' / spec.slug
        self.root = root

    @property
    def python(self):
        return self.venv / 'bin' / 'python'

    def ensure_clone(self):
        if not self.clone.exists():
            self.clone.parent.mkdir(parents=True, exist_ok=True)
            _run(['git', '-c', 'advice.detachedHead=false', 'clone', '-q', '--depth', '1', '--branch',
                  self.spec.ref, self.spec.url, str(self.clone)])
        head = _run(['git', '-C', str(self.clone), 'rev-parse', 'HEAD']).strip()
        if head != self.spec.commit:
            raise ValueError(f'{self.spec.name}: {self.spec.ref} resolves to {head}, not pinned {self.spec.commit}')
        return head

    def ensure_tree(self):
        if not self.tree.exists():
            staging = Path(tempfile.mkdtemp(prefix='.tree-', dir=self.tree.parent if self.tree.parent.exists()
                                            else self.root))
            archive = subprocess.run(['git', '-C', str(self.clone), 'archive', '--format=tar', self.spec.commit],
                                     capture_output=True, check=True)
            subprocess.run(['tar', '-x', '-C', str(staging)], input=archive.stdout, check=True)
            self.tree.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(self.tree)
        return tree_digest(self.tree)

    def ensure_venv(self):
        if not self.python.exists():
            _run(['uv', 'venv', '-q', '--python', self.python_version, str(self.venv)])
        marker = self.venv / '.rlm-installed.json'
        wanted = dict(commit=self.spec.commit, deps=list(self.spec.test_deps))
        if not marker.exists() or json.loads(marker.read_text()) != wanted:
            env = {**os.environ, 'SETUPTOOLS_SCM_PRETEND_VERSION': self.spec.ref.lstrip('v')}
            _run(['uv', 'pip', 'install', '-q', '--python', str(self.python), str(self.clone),
                  *self.spec.test_deps], env=env)
            marker.write_text(json.dumps(wanted))
        return _run(['uv', 'pip', 'freeze', '--python', str(self.python)]).splitlines()

    def checkout(self, dest):
        dest = Path(dest)
        shutil.copytree(self.tree, dest, symlinks=True)
        # A private repository root keeps `git apply` paths relative to this checkout.
        subprocess.run(['git', 'init', '-q', str(dest)], check=True, capture_output=True)
        return dest


def sandbox_profile(writable):
    home = Path.home()
    rules = ['(version 1)', '(allow default)',
             '(deny network-outbound (remote ip "*:*"))',
             '(allow network-outbound (remote ip "localhost:*"))',
             '(allow network-outbound (remote unix-socket))',
             f'(deny file-write* (subpath "{home}"))']
    for path in writable:
        rules.append(f'(allow file-write* (subpath "{Path(path).resolve()}"))')
    project = Path(__file__).resolve().parents[3]
    for secret in SECRET_PATHS:
        rules.append(f'(deny file-read* (subpath "{home / secret}"))')
    rules.append(f'(deny file-read* (subpath "{project / ".phase1-auth"}"))')
    return '\n'.join(rules)


async def run_sandboxed(cmd, *, cwd, env, timeout_s, writable=()):
    """Run without network or credential access; kill the whole group on timeout."""
    cwd = Path(cwd)
    argv = ['sandbox-exec', '-p', sandbox_profile([cwd, *writable]), *map(str, cmd)]
    start = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(*argv, cwd=str(cwd), env=env, start_new_session=True,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    timed_out = False
    try:
        output, _ = await asyncio.wait_for(proc.communicate(), timeout_s)
    except TimeoutError:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        output, _ = await proc.communicate()
    return proc.returncode, output.decode('utf-8', 'replace'), timed_out, time.perf_counter() - start


def sanitize(text, workspace, checkout, scratch):
    """Make logs location-independent: no temp, venv, interpreter or home paths."""
    replacements = []
    for path in (Path(checkout), Path(checkout).resolve()):
        replacements += [(str(path) + '/', ''), (str(path), '.')]
    for path in (Path(scratch), Path(scratch).resolve()):
        replacements.append((str(path), '$TMP'))
    replacements.append((str(workspace.venv), '/venv'))
    config = workspace.venv / 'pyvenv.cfg'
    if config.exists():
        home = next((line.split('=', 1)[1].strip() for line in config.read_text().splitlines()
                     if line.startswith('home')), None)
        if home:
            replacements.append((str(Path(home).parent), '/usr'))
    replacements.append((str(Path.home()), '~'))
    for old, new in sorted(set(replacements), key=lambda item: -len(item[0])):
        text = text.replace(old, new)
    return text


def test_env(workspace, checkout, scratch, extra=None):
    paths = [str(Path(checkout) / p) for p in workspace.spec.pythonpath] + [str(scratch)]
    home = Path(scratch) / 'home'
    home.mkdir(parents=True, exist_ok=True)
    env = dict(PATH=f'{workspace.venv / "bin"}:/usr/bin:/bin', HOME=str(home), TMPDIR=str(scratch),
               LANG='en_US.UTF-8', LC_ALL='en_US.UTF-8', PYTHONPATH=os.pathsep.join(paths),
               PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0', TZ='UTC', NO_COLOR='1')
    env.update(extra or {})
    return env


async def run_tests(workspace, checkout, *, selectors=None, timeout_s=900):
    """Run pytest in `checkout` with the repository venv; return per-test outcomes."""
    with tempfile.TemporaryDirectory(prefix='rlm-test-') as scratch:
        scratch = Path(scratch)
        shutil.copy(PLUGIN, scratch / 'rlm_task_report.py')
        report = scratch / 'report.json'
        env = test_env(workspace, checkout, scratch, dict(RLM_TASK_REPORT=str(report)))
        targets = list(selectors) if selectors else list(workspace.spec.test_paths)
        cmd = [workspace.python, '-m', 'pytest', '-p', 'no:cacheprovider', '-p', 'no:randomly',
               '-p', 'rlm_task_report', '-q', '--tb=short', '-rfE', '--color=no',
               *workspace.spec.pytest_args, *targets]
        code, log, timed_out, duration = await run_sandboxed(cmd, cwd=checkout, env=env, timeout_s=timeout_s,
                                                             writable=[scratch])
        outcomes = json.loads(report.read_text())['outcomes'] if report.exists() else {}
        log = sanitize(log, workspace, checkout, scratch)
        return TestRun(outcomes, code if code is not None else -1, log, duration, timed_out)


async def run_python(workspace, checkout, script, *, timeout_s=120):
    """Execute a verifier oracle in the checkout; returns (exit code, output, timed out)."""
    with tempfile.TemporaryDirectory(prefix='rlm-oracle-') as scratch:
        scratch = Path(scratch)
        path = scratch / 'oracle.py'
        path.write_text(script, encoding='utf-8')
        env = test_env(workspace, checkout, scratch)
        code, output, timed_out, _ = await run_sandboxed([workspace.python, str(path)], cwd=checkout, env=env,
                                                         timeout_s=timeout_s, writable=[scratch])
        return code, sanitize(output, workspace, checkout, scratch), timed_out


def patch_files(patch):
    """Paths a unified diff touches, from its headers (a/ b/ prefixes removed)."""
    files = []
    for line in patch.splitlines():
        if line.startswith('+++ ') or line.startswith('--- '):
            path = line[4:].split('\t')[0].strip()
            if path == '/dev/null':
                continue
            if path[:2] in ('a/', 'b/'):
                path = path[2:]
            if path not in files:
                files.append(path)
    return files


async def apply_patch(checkout, patch):
    if not patch or not patch.strip():
        return False, 'empty patch'
    text = patch if patch.endswith('\n') else patch + '\n'
    with tempfile.NamedTemporaryFile('w', suffix='.patch', delete=False, encoding='utf-8') as stream:
        stream.write(text)
        path = stream.name
    try:
        messages = []
        # Exact hunk counts first: --recount ignores them, so in a multi-file patch the
        # next file's `--- a/...` header would be read as a deletion line. Recounting is
        # only a fallback for hand-written hunks with wrong counts.
        for strip, recount in (('-p1', False), ('-p0', False), ('-p1', True), ('-p0', True)):
            proc = await asyncio.create_subprocess_exec(
                'git', 'apply', strip, *(['--recount'] if recount else []), '--whitespace=nowarn', path,
                cwd=str(checkout), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            out, _ = await proc.communicate()
            if proc.returncode == 0:
                return True, strip + (' --recount' if recount else '')
            messages.append(out.decode('utf-8', 'replace').strip()[-400:])
        return False, ' | '.join(messages)
    finally:
        os.unlink(path)


@dataclass
class Document:
    path: str
    kind: str
    text: str


def _excluded(path, patterns):
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch('/' + path, p) for p in patterns)


def inventory(spec, root, *, exclude, max_file_chars):
    """Readable text files with a kind used for context budgeting."""
    root = Path(root)
    documents = []
    for path in sorted(p for p in root.rglob('*') if p.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative.startswith('.git/') or _excluded(relative, exclude):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in CONFIG_NAMES | {'LICENSE', 'CHANGES'}:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        if '\0' in text or len(text) > max_file_chars or not text.strip():
            continue
        if spec.is_test_path(relative):
            kind = 'test'
        elif path.suffix == '.py' and any(relative.startswith(p.rstrip('/') + '/') or p == '.'
                                          for p in spec.pythonpath) and not relative.startswith(
                                              ('examples/', 'docs/', 'doc/', 'bench', 'scripts/', 'tasks/', 'tools/')):
            kind = 'source'
        elif path.name in CONFIG_NAMES:
            kind = 'config'
        elif path.suffix.lower() in ('.md', '.rst', '.txt') or path.name in ('CHANGES', 'LICENSE'):
            kind = 'doc'
        else:
            kind = 'other'
        documents.append(Document(relative, kind, text))
    return documents


PRIORITY = ('source', 'test', 'config', 'doc', 'other')


def select_documents(documents, *, scope, files=(), max_chars, max_documents):
    if scope == 'files':
        by_path = {d.path: d for d in documents}
        missing = [f for f in files if f not in by_path]
        if missing:
            raise ValueError(f'context files not found or not readable text: {missing}')
        chosen = [by_path[f] for f in files]
    else:
        chosen, total = [], 0
        for kind in PRIORITY:
            for document in (d for d in documents if d.kind == kind):
                size = len(document.text) + len(document.path) + 10
                if total + size > max_chars or len(chosen) >= max_documents:
                    continue
                chosen.append(document)
                total += size
        chosen.sort(key=lambda d: d.path)
    return chosen


def render_context(documents, logs=()):
    """Context list: one element per repository file, then execution logs."""
    rendered = [f'# File: {d.path}\n{d.text}' for d in documents]
    rendered += [f'# Log: {title}\n{text}' for title, text in logs]
    return rendered
