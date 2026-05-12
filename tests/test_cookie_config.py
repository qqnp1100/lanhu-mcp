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
