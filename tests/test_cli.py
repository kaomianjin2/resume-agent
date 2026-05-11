from pathlib import Path

import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = PROJECT_ROOT / "config" / "interview-agent.toml.example"


def run_module_help() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "interview_agent.cli", "--help"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )


def test_module_help_exits_successfully() -> None:
    result = run_module_help()

    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "interview-agent" in result.stdout


def test_example_config_exists_with_placeholders_only() -> None:
    content = EXAMPLE_CONFIG.read_text(encoding="utf-8")

    assert 'base_url = "https://your-openai-compatible-endpoint/v1"' in content
    assert 'api_key = "your-key"' in content
    assert 'provider = "your-embedding-provider"' in content
    assert 'database_path = "./path/to/your-database.sqlite"' in content
    assert 'source = "/path/to/your-knowledge-base-source"' in content
