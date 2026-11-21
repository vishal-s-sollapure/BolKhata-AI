"""Monorepo consistency and safety checks."""

from pathlib import Path


def test_no_env_committed():
    """Ensure that git does not track any actual .env files."""
    import subprocess
    result = subprocess.run(["git", "ls-files", ".env", "backend/.env"], capture_output=True, text=True)
    assert result.stdout.strip() == "", f"Secret .env file is tracked in git: {result.stdout}"


def test_monorepo_structure():
    """Ensure all required core architecture directories exist."""
    root = Path(__file__).resolve().parent.parent
    expected_dirs = [
        root / "backend",
        root / "backend" / "app",
        root / "backend" / "app" / "config",
        root / "backend" / "app" / "api",
        root / "backend" / "app" / "voice",
        root / "backend" / "app" / "agent",
        root / "backend" / "app" / "services",
        root / "backend" / "app" / "ledger",
        root / "backend" / "app" / "database",
        root / "backend" / "app" / "models",
        root / "backend" / "app" / "schemas",
        root / "backend" / "app" / "utils",
        root / "backend" / "tests",
        root / "docs",
        root / "tests",
    ]
    for d in expected_dirs:
        assert d.is_dir(), f"Expected directory missing: {d}"
