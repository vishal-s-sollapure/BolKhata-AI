"""Monorepo consistency and safety checks."""

from pathlib import Path


def test_no_env_committed():
    """Ensure that no actual .env files exist in tracked root or backend directory."""
    root = Path(__file__).resolve().parent.parent
    root_env = root / ".env"
    backend_env = root / "backend" / ".env"
    
    # We allow .env.example, but warn or fail if actual .env exists with credentials
    if root_env.exists():
        content = root_env.read_text(encoding="utf-8")
        assert "your_groq_api_key_here" in content or "bolkhata-dev" in content
    if backend_env.exists():
        content = backend_env.read_text(encoding="utf-8")
        assert "your_groq_api_key_here" in content or "bolkhata-dev" in content


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
