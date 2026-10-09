"""Execute server installer's manifest export without needing Linux/CUDA."""
from pathlib import Path
import subprocess
import sys


def test_server_source_export_supports_source_and_version_pins(tmp_path):
    script = Path("scripts/setup_m0_server.sh").read_text()
    source = script.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    result = subprocess.run([sys.executable, "-", str(tmp_path)], input=source,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    sources = (tmp_path / "sources.txt").read_text().splitlines()
    assert len(sources) == 3
    assert {line.split()[0] for line in sources} == {"rlm", "verifiers", "prime-rl"}
    assert all(len(line.split()[2]) == 40 for line in sources)
    assert "psutil==7.2.2" in (tmp_path / "primary.txt").read_text()
