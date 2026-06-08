"""Tests for Docker Compose exposure policy."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def test_lanhu_mcp_is_only_exposed_inside_docker_network():
    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "\n    ports:" not in compose_text
    assert '"8000:8000"' not in compose_text
    assert "\n    expose:\n      - \"8000\"" in compose_text
