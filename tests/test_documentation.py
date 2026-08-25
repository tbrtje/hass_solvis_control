"""Tests for generated SolvisLeo 180 documentation."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

REPOSITORY_ROOT = Path(__file__).parents[1]


def test_generated_register_documentation_is_current() -> None:
    """Committed register tables must match the generator output."""
    result = subprocess.run(
        [sys.executable, "-m", "tools.generate_docs", "--check"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_readme_is_a_short_solvisleo_180_fork_description() -> None:
    """The public entry point must describe this single supported Anlage."""
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")

    assert "SolvisLeo 180" in readme
    assert "hard fork" in readme
    assert len(readme.splitlines()) <= 60
    assert "SolvisMax" not in readme
    assert "SolvisTom" not in readme
