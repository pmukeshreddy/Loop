import json
import socket
import threading

import pytest

from step1.run_eval import git, make_fixture


def test_capture_patch_contains_committed_uncommitted_and_new_files(tmp_path):
    from step1.benchmark_worker import capture_patch

    repo = tmp_path / "repo"
    make_fixture(repo)
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "committed.txt").write_text("committed\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "agent change")
    (repo / "total.py").write_text("def total(values):\n    return 42\n")
    (repo / "new.txt").write_text("new\n")
    patch = capture_patch(repo, base)
    grade = tmp_path / "grade"
    make_fixture(grade)
    git(grade, "apply", "-", input=patch)
    assert (grade / "committed.txt").read_text() == "committed\n"
    assert (grade / "new.txt").read_text() == "new\n"
    assert "return 42" in (grade / "total.py").read_text()


def test_repository_context_excludes_untracked_and_binary_files(tmp_path):
    from step1.benchmark_worker import repository_context

    repo = tmp_path / "repo"
    make_fixture(repo)
    (repo / "image.bin").write_bytes(b"\x00\xff")
    git(repo, "add", "image.bin")
    (repo / "outside.txt").write_text("not tracked")
    context = repository_context(repo)
    assert context == {"total.py": "def total(values):\n    return sum(values)\n"}


def test_deadline_capture_works_with_a_stale_git_lock(tmp_path):
    from step1.benchmark_worker import capture_patch

    repo = tmp_path / "repo"
    make_fixture(repo)
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "total.py").write_text("fixed\n")
    (repo / ".git/index.lock").write_text("interrupted git process")
    assert "+fixed" in capture_patch(repo, base)


def test_interrupted_worker_telemetry_is_reported_without_raising(tmp_path):
    from step1.benchmark import worker_result

    path = tmp_path / "worker.json"
    path.write_text('{"status":')
    result = worker_result(path)
    assert result["status"] == "error" and result["usage_complete"] is False


def test_missing_verifier_evidence_is_infrastructure_error(tmp_path):
    from step1.benchmark import read_grade

    with pytest.raises(RuntimeError, match="reward"):
        read_grade(tmp_path)
    (tmp_path / "reward.json").write_text(
        json.dumps({"reward": 0, "f2p_passed": 2, "f2p_total": 4})
    )
    assert read_grade(tmp_path)["reward"] == 0
    (tmp_path / "reward.json").write_text('{"reward": -1}')
    with pytest.raises(RuntimeError, match="reward"):
        read_grade(tmp_path)


def test_usage_log_aggregates_each_completed_request_once(tmp_path):
    from step1.benchmark_worker import read_usage

    path = tmp_path / "usage.jsonl"
    path.write_text(
        '{"input_tokens": 20, "output_tokens": 3}\n{"input_tokens": 40, "output_tokens": 5}\n'
    )
    assert read_usage(path) == {"calls": 2, "input_tokens": 60, "output_tokens": 8}


def test_proxy_rejects_non_openai_connections():
    from step1.api_proxy import Proxy, Server

    server = Server(("127.0.0.1", 0), Proxy)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with socket.create_connection(server.server_address) as client:
            client.sendall(
                b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n"
            )
            assert b"403" in client.recv(1024)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
