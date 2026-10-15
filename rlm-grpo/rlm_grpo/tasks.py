"""Harbor task bundles, explicit splits, and reserved-benchmark exclusion."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tomllib
import unicodedata


def normalized(text):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def grams(text, n):
    words = normalized(text).split()
    width = min(n, len(words))
    return {tuple(words[i:i + width]) for i in range(len(words) - width + 1)} if width else set()


def repository_key(url: str) -> str:
    return url.lower().removeprefix("https://").removeprefix("http://").removeprefix(
        "git@").replace(":", "/").rstrip("/").removesuffix(".git")


@dataclass(frozen=True)
class RepoTask:
    task_id: str
    split: str
    directory: Path
    instruction: str
    repository_url: str
    base_commit: str
    image: str
    repo_path: str
    verifier_timeout: float
    cpus: float
    memory_mb: int
    build_timeout: float
    environment: dict[str, str]
    verifier_environment: dict[str, str]

    @classmethod
    def read(cls, directory: Path, *, task_id: str, split: str, repo_path="/app"):
        directory = directory.resolve(strict=True)
        config = tomllib.loads((directory / "task.toml").read_text())
        metadata, env = config["metadata"], config["environment"]
        verifier = config["verifier"]
        commit = metadata["base_commit_hash"]
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError(f"{task_id}: base_commit_hash must be an exact SHA")
        path = PurePosixPath(repo_path)
        if not path.is_absolute() or ".." in path.parts or repo_path == "/":
            raise ValueError(f"{task_id}: invalid repository path")
        instruction = (directory / "instruction.md").read_text()
        if not instruction.strip():
            raise ValueError(f"{task_id}: empty instruction")
        for required in ("environment/Dockerfile", "tests/test.sh"):
            if not (directory / required).is_file():
                raise ValueError(f"{task_id}: missing {required}")
        if verifier.get("environment_mode", "separate") != "separate":
            raise ValueError(f"{task_id}: GRPO requires a separate verifier environment")
        if verifier.get("docker_image") or verifier.get("environment", {}).get("docker_image"):
            raise ValueError(f"{task_id}: a distinct verifier image is not supported")
        # Reference solutions are never read, copied, or included in dataset rows.
        task = cls(task_id, split, directory, instruction, metadata["repository_url"],
                   commit, env.get("docker_image", ""), repo_path,
                   float(verifier.get("timeout_sec", 1800)), float(env.get("cpus", 2)),
                   int(env.get("memory_mb", 8192)), float(env.get("build_timeout_sec", 1800)),
                   dict(env.get("env", {})), dict(verifier.get("env", {})))
        if min(task.verifier_timeout, task.cpus, task.memory_mb, task.build_timeout) <= 0:
            raise ValueError(f"{task_id}: resource limits must be positive")
        return task

    def row(self, example_id: int) -> dict:
        return dict(example_id=example_id, prompt=[dict(role="user", content=self.instruction)],
                    answer="", info=dict(task_id=self.task_id))


def load_pool(manifest_path, *, heldout_dir) -> list[RepoTask]:
    """Load all splits together so train/dev leakage cannot hide in a split filter."""
    manifest = Path(manifest_path).resolve(strict=True)
    reserved = []
    for path in sorted(Path(heldout_dir).glob("*/task.toml")):
        meta = tomllib.loads(path.read_text())["metadata"]
        query = (path.parent / "instruction.md").read_text()
        reserved.append((meta.get("task_id", path.parent.name),
                         repository_key(meta["repository_url"]), normalized(query), grams(query, 5)))
    if not reserved:
        raise ValueError("Reserved DeepSWE snapshot is missing; cannot decontaminate the pool")
    held_ids = {item[0] for item in reserved}
    held_repos = {item[1] for item in reserved}
    tasks, ids, sources, queries = [], set(), {}, {}
    for number, line in enumerate(manifest.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if set(row) - {"task_id", "split", "task_dir", "repo_path"}:
            raise ValueError(f"manifest line {number}: unsupported fields")
        if row["split"] not in {"train", "dev"}:
            raise ValueError("GRPO manifests may contain only train/dev, never benchmark eval")
        task = RepoTask.read(manifest.parent / row["task_dir"], task_id=row["task_id"],
                            split=row["split"], repo_path=row.get("repo_path", "/app"))
        if task.task_id in ids:
            raise ValueError(f"Duplicate task_id: {task.task_id}")
        repo, query = repository_key(task.repository_url), normalized(task.instruction)
        if task.task_id in held_ids or repo in held_repos:
            raise ValueError(f"{task.task_id}: reserved DeepSWE task/repository overlap")
        candidate_grams = grams(query, 5)
        for held_id, _, held_query, held_grams in reserved:
            overlap = len(candidate_grams & held_grams) / max(1, len(candidate_grams | held_grams))
            if query == held_query or overlap > 0.8:
                raise ValueError(f"{task.task_id}: reserved instruction overlap with {held_id}")
        if repo in sources and sources[repo] != task.split:
            raise ValueError(f"Repository occurs in both train and dev: {repo}")
        if query in queries:
            raise ValueError(f"Duplicate instruction: {task.task_id} and {queries[query]}")
        sources[repo], queries[query] = task.split, task.task_id
        ids.add(task.task_id)
        tasks.append(task)
    if not tasks:
        raise ValueError("GRPO task pool is empty")
    return tasks


def image_tag(task: RepoTask) -> str:
    dockerfile = (task.directory / "environment/Dockerfile").read_bytes()
    digest = hashlib.sha256(dockerfile + str(task.directory).encode()).hexdigest()[:20]
    return f"loop-grpo:{digest}"
