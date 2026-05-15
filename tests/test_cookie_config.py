"""Tests for request-level Lanhu cookie resolution."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


class _FastMCPStub:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def custom_route(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def run(self, *args, **kwargs):
        pass


class _AsyncClientStub:
    def __init__(self, *args, **kwargs):
        pass

    async def get(self, *args, **kwargs):
        raise AssertionError("HTTP client should not be used in cookie config tests")

    async def aclose(self):
        pass


class _Headers(dict):
    def get(self, key, default=None):
        for current_key, value in self.items():
            if current_key.lower() == key.lower():
                return value
        return default


def _install_import_stubs(monkeypatch):
    fastmcp = types.ModuleType("fastmcp")
    fastmcp.Context = object
    fastmcp.FastMCP = _FastMCPStub
    monkeypatch.setitem(sys.modules, "fastmcp", fastmcp)

    utilities = types.ModuleType("fastmcp.utilities")
    utility_types = types.ModuleType("fastmcp.utilities.types")
    utility_types.Image = object
    monkeypatch.setitem(sys.modules, "fastmcp.utilities", utilities)
    monkeypatch.setitem(sys.modules, "fastmcp.utilities.types", utility_types)

    dependencies = types.ModuleType("fastmcp.server.dependencies")
    dependencies.get_http_request = lambda: (_ for _ in ()).throw(RuntimeError("no http request"))
    monkeypatch.setitem(sys.modules, "fastmcp.server.dependencies", dependencies)

    bs4 = types.ModuleType("bs4")
    bs4.BeautifulSoup = object
    monkeypatch.setitem(sys.modules, "bs4", bs4)

    httpx = types.ModuleType("httpx")
    httpx.AsyncClient = _AsyncClientStub
    monkeypatch.setitem(sys.modules, "httpx", httpx)

    playwright = types.ModuleType("playwright")
    playwright_async = types.ModuleType("playwright.async_api")
    playwright_async.async_playwright = object
    monkeypatch.setitem(sys.modules, "playwright", playwright)
    monkeypatch.setitem(sys.modules, "playwright.async_api", playwright_async)


@pytest.fixture()
def server(monkeypatch):
    _install_import_stubs(monkeypatch)
    monkeypatch.delenv("LANHU_COOKIE", raising=False)
    monkeypatch.delenv("DDS_COOKIE", raising=False)

    module_name = "lanhu_mcp_server_cookie_tests"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / "lanhu_mcp_server.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _set_request_headers(monkeypatch, headers):
    dependencies = sys.modules["fastmcp.server.dependencies"]
    dependencies.get_http_request = lambda: types.SimpleNamespace(headers=_Headers(headers))


def test_env_cookie_fallback_reuses_lanhu_cookie_for_dds(server, monkeypatch):
    monkeypatch.setenv("LANHU_COOKIE", "env-cookie")

    cookies = server.get_current_lanhu_cookies()

    assert cookies == {
        "lanhu_cookie": "env-cookie",
        "dds_cookie": "env-cookie",
    }


def test_headers_override_environment_cookie(server, monkeypatch):
    monkeypatch.setenv("LANHU_COOKIE", "env-cookie")
    monkeypatch.setenv("DDS_COOKIE", "env-dds-cookie")
    _set_request_headers(
        monkeypatch,
        {
            "X-Lanhu-Cookie": "header-cookie",
            "X-Lanhu-DDS-Cookie": "header-dds-cookie",
        },
    )

    cookies = server.get_current_lanhu_cookies()

    assert cookies == {
        "lanhu_cookie": "header-cookie",
        "dds_cookie": "header-dds-cookie",
    }


def test_dds_env_cookie_is_used_when_header_is_missing(server, monkeypatch):
    monkeypatch.setenv("LANHU_COOKIE", "env-cookie")
    monkeypatch.setenv("DDS_COOKIE", "env-dds-cookie")
    _set_request_headers(monkeypatch, {"X-Lanhu-Cookie": "header-cookie"})

    cookies = server.get_current_lanhu_cookies()

    assert cookies == {
        "lanhu_cookie": "header-cookie",
        "dds_cookie": "env-dds-cookie",
    }


def test_placeholder_cookie_raises_configuration_error(server, monkeypatch):
    monkeypatch.setenv("LANHU_COOKIE", "your_lanhu_cookie_here")

    with pytest.raises(server.LanhuCookieNotConfigured):
        server.get_current_lanhu_cookies()


def test_metadata_cache_key_can_be_scoped_per_cookie(server):
    user_a_key = server._get_metadata_cache_key("project-1", "doc-1", cache_scope="user-a")
    user_b_key = server._get_metadata_cache_key("project-1", "doc-1", cache_scope="user-b")

    assert user_a_key != user_b_key
    assert user_a_key.endswith("project-1_doc-1")


def test_axure_cache_dirs_are_scoped_per_cookie(server, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)

    user_a_dirs = server._get_axure_cache_dirs(
        "doc-abcdef123456",
        {"lanhu_cookie": "lanhu-cookie-a", "dds_cookie": "dds-cookie-a"},
    )
    user_b_dirs = server._get_axure_cache_dirs(
        "doc-abcdef123456",
        {"lanhu_cookie": "lanhu-cookie-b", "dds_cookie": "dds-cookie-b"},
    )

    assert user_a_dirs != user_b_dirs
    assert user_a_dirs[0].startswith(str(tmp_path))
    assert "doc-abcdef123456" in user_a_dirs[0]


def test_design_cache_dir_is_scoped_per_cookie(server, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)

    user_a_dir = server._get_design_cache_dir(
        "project-1",
        {"lanhu_cookie": "lanhu-cookie-a", "dds_cookie": "dds-cookie-a"},
    )
    user_b_dir = server._get_design_cache_dir(
        "project-1",
        {"lanhu_cookie": "lanhu-cookie-b", "dds_cookie": "dds-cookie-b"},
    )

    assert user_a_dir != user_b_dir
    assert user_a_dir.parent.name != user_b_dir.parent.name
    assert user_a_dir.name == "project-1"


def test_message_store_does_not_overwrite_interleaved_writes(server, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)

    store_a = server.MessageStore("project-1")
    store_b = server.MessageStore("project-1")

    msg_a = store_a.save_message("a", "content-a", "alice", "dev")
    msg_b = store_b.save_message("b", "content-b", "bob", "qa")

    saved = (tmp_path / "messages" / "project-1.json").read_text(encoding="utf-8")
    data = __import__("json").loads(saved)

    assert msg_a["id"] == 1
    assert msg_b["id"] == 2
    assert [msg["summary"] for msg in data["messages"]] == ["a", "b"]
    assert data["next_id"] == 3
