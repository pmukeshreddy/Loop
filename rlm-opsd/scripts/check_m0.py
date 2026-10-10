"""Offline installation/source smoke checks; NOT a prime-rl runtime readiness test."""

import asyncio
import importlib.metadata as metadata
import inspect
import json
from pathlib import Path
import re
import subprocess
import tomllib
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
SOURCES = {
    "rlms": ("rlm", ".", "rlm"),
    "rlm-train": ("rlm", "training/src", "rlm_train"),
    "verifiers": ("verifiers", ".", "verifiers"),
    "prime-rl": ("prime-rl", "src", "prime_rl"),
    "prime-rl-configs": ("prime-rl", "packages/prime-rl-configs/src", "prime_rl"),
}


class M0LocalChecks(unittest.TestCase):
    def test_installed_provenance_and_source_bytes(self):
        for requirement in PROJECT["project"]["dependencies"]:
            if " @ " not in requirement:
                name, version = requirement.split("==", 1)
                self.assertEqual(metadata.version(name), version)
                print(f"{name}=={version}: installed version matches explicit pin")
                continue
            name, url = requirement.split(" @ ", 1)
            commit = re.search(r"[0-9a-f]{40}", url).group()
            repo, source_dir, package = SOURCES[name]
            checkout = ROOT / ".deps" / repo
            head = subprocess.check_output(
                ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
            ).strip()
            self.assertEqual(head, commit)
            patched_files = {}
            if repo == 'prime-rl':
                from rlm_opsd.training.prime_patch import apply_patch, patch_manifest
                patch_state = apply_patch(checkout, check_only=True)
                patched_files = patch_manifest()['files'] if patch_state == 'already_applied' else {}
            else:
                subprocess.run(["git", "-C", str(checkout), "diff", "--exit-code", "HEAD"], check=True)
            dist = metadata.distribution(name)
            direct = json.loads(dist.read_text("direct_url.json"))
            if url.startswith("git+"):
                self.assertEqual(direct["vcs_info"]["commit_id"], commit)
                self.assertEqual(direct["url"], url.removeprefix("git+").split("@", 1)[0])
            else:
                self.assertEqual(direct["url"], url.split("#", 1)[0])
                self.assertIn("sha256", direct["archive_info"]["hashes"])
            subdir = url.partition("#subdirectory=")[2]
            self.assertEqual(direct.get("subdirectory", ""), subdir)
            files = [p for p in dist.files if str(p).startswith(package + "/") and str(p).endswith(".py")]
            self.assertTrue(files)
            for file in files:
                source = checkout / source_dir / str(file)
                relative = source.relative_to(checkout).as_posix()
                # Installed wheels retain the immutable upstream baseline. The
                # reviewed source overlay is verified independently above.
                expected = (subprocess.check_output(['git', '-C', str(checkout), 'show', commit + ':' + relative])
                            if relative in patched_files else source.read_bytes())
                self.assertEqual(dist.locate_file(file).read_bytes(), expected, str(file))
            print(f"\n{name}=={dist.version}: {commit}; {len(files)} installed Python files match the pinned baseline")
            print(json.dumps(direct, sort_keys=True))

    def test_imports_and_config_contracts(self):
        import rlm
        import rlm_train
        import verifiers as vf
        from prime_rl.configs.orchestrator import OrchestratorConfig, TrainEnvConfig, TrainSamplingConfig
        from prime_rl.configs.rl import RLConfig, SingleNodeDeploymentConfig
        from prime_rl.configs.trainer import DefaultLossConfig, LoRAConfig, TrainerConfig

        self.assertTrue(issubclass(rlm_train.RLMTrainEnv, vf.MultiTurnEnv))
        for obj in (rlm.RLM, rlm.RLM.completion, rlm_train.RLMTrainEnv,
                    rlm_train.SubprocessReplBackend, vf.Environment, vf.MultiTurnEnv,
                    vf.load_environment):
            print(f"\n{obj.__module__}.{obj.__qualname__}{inspect.signature(obj)}")
            print(inspect.getsourcefile(obj), inspect.getsourcelines(obj)[1])
        self.assertIn("num_teacher_gpus", SingleNodeDeploymentConfig.model_fields)
        self.assertIn("teacher_inference", RLConfig.model_fields)
        self.assertIn("teacher_model", OrchestratorConfig.model_fields)
        self.assertNotIn("verification", OrchestratorConfig.model_fields)
        self.assertEqual(TrainEnvConfig(args={"score_rollouts": False}).args, {"score_rollouts": False})
        self.assertEqual(TrainSamplingConfig(max_completion_tokens=16).to_sampling_args()["max_completion_tokens"], 16)
        self.assertIn("score_rollouts", inspect.signature(vf.Environment).parameters)
        self.assertIn("rank", LoRAConfig.model_fields)
        for cls in (SingleNodeDeploymentConfig, DefaultLossConfig, LoRAConfig,
                    TrainSamplingConfig, TrainEnvConfig, TrainerConfig, OrchestratorConfig):
            print(f"\n{cls.__module__}.{cls.__name__}: {list(cls.model_fields)}")

    def test_upstream_subprocess_repl_offline(self):
        from rlm_train import SubprocessReplBackend

        async def run():
            backend = SubprocessReplBackend(startup_timeout=30, request_timeout=30)
            try:
                await backend.start(proxy_url="http://127.0.0.1:1", rollout_id="m0-offline")
                self.assertEqual(await backend.load_context("abcd"), 0)
                result = await backend.execute("n = len(context)\nprint(n)")
                self.assertEqual(result.stdout.strip(), "4")
                self.assertEqual(result.stderr, "")
                result = await backend.execute("answer['content'] = str(n)\nanswer['ready'] = True")
                self.assertEqual(result.final_answer, "4")
                self.assertEqual(result.stderr, "")
            finally:
                await backend.stop()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main(verbosity=2)
