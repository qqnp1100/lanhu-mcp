"""Tests for matching Lanhu web slice-list behavior."""

import importlib.util
import sys
import types
from pathlib import Path


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


class _AsyncClientStub:
    def __init__(self, *args, **kwargs):
        pass


def _install_import_stubs(monkeypatch):
    fastmcp = types.ModuleType("fastmcp")
    fastmcp.Context = object
    fastmcp.FastMCP = _FastMCPStub
    monkeypatch.setitem(sys.modules, "fastmcp", fastmcp)

    utility_types = types.ModuleType("fastmcp.utilities.types")
    utility_types.Image = object
    monkeypatch.setitem(sys.modules, "fastmcp.utilities", types.ModuleType("fastmcp.utilities"))
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


def _load_server(monkeypatch):
    _install_import_stubs(monkeypatch)
    module_name = "lanhu_mcp_server_slice_list_tests"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / "lanhu_mcp_server.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _image_layer(name, image_url, web_id):
    return {
        "name": name,
        "web_id": web_id,
        "width": 20,
        "height": 20,
        "image": {
            "bitmap": image_url,
            "imageUrl": image_url,
            "isNew": 0,
        },
    }


def test_slice_index_prefers_info_list_when_present(monkeypatch):
    server = _load_server(monkeypatch)
    data = {
        "artboard": {
            "layers": [
                {"layers": [_image_layer("artboard one", "https://example.test/a.png", 1)]},
            ],
        },
        "info": [
            _image_layer("web one", "https://example.test/1.png", 11),
            _image_layer("web two", "https://example.test/2.png", 12),
        ],
    }

    items = server._extract_lanhu_slice_index(data)

    assert [item["name"] for item in items] == ["web one", "web two"]


def test_slice_index_keeps_root_bg_image(monkeypatch):
    server = _load_server(monkeypatch)
    data = {
        "ArtboardID": "root",
        "info": [
            {
                "name": "BG",
                "web_id": 1,
                "parentID": "root",
                "width": 750,
                "height": 1786,
                "image": {
                    "bitmap": "https://example.test/bg.png",
                    "svg": "",
                },
            },
        ],
    }

    items = server._extract_lanhu_slice_index(data)

    assert len(items) == 1
    assert items[0]["name"] == "BG"
    assert items[0]["url"] == "https://example.test/bg.png"


def test_slice_index_matches_frontend_without_deduping(monkeypatch):
    server = _load_server(monkeypatch)
    data = {
        "info": [
            _image_layer("duplicate", "https://example.test/dup.png", 7),
            _image_layer("duplicate", "https://example.test/dup.png", 7),
        ],
    }

    items = server._extract_lanhu_slice_index(data)

    assert [item["name"] for item in items] == ["duplicate", "duplicate"]
