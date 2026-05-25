"""Tests for the interactive slice download selector app."""

from urllib.parse import quote

from tests.test_lanhu_slice_list_logic import _load_server


def test_slice_selector_payload_marks_each_slice_downloadable(monkeypatch):
    server = _load_server(monkeypatch)
    slices = [
        {
            "id": 101,
            "name": "icon close",
            "download_url": "https://assets.example.test/close.png",
            "slice_list_src": "https://assets.example.test/close-thumb.png",
            "size": "24x24",
            "format": "png",
        },
        {
            "id": 102,
            "name": "empty state",
            "download_url": "https://assets.example.test/empty.png",
            "size": "320x240",
            "format": "png",
        },
    ]

    payload = server._build_slice_selector_payload(
        {
            "status": "success",
            "design_id": "img-1",
            "design_name": "Home",
            "total_slices": len(slices),
            "slices": slices,
        }
    )

    assert payload["design_name"] == "Home"
    assert [item["selected"] for item in payload["slices"]] == [True, True]
    assert payload["slices"][0]["thumb_url"] == "https://assets.example.test/close-thumb.png"
    assert payload["slices"][1]["thumb_url"] == "https://assets.example.test/empty.png"
    assert payload["slices"][0]["filename"] == "icon_close.png"
    assert payload["slices"][1]["filename"] == "empty_state.png"
    assert len({item["key"] for item in payload["slices"]}) == 2


def test_slice_selector_prefab_app_has_checkboxes_images_and_submit_tool(monkeypatch):
    server = _load_server(monkeypatch)
    payload = {
        "design_name": "Home",
        "slices": [
            {
                "key": "1::0",
                "name": "icon close",
                "thumb_url": "https://assets.example.test/close.png",
                "download_url": "https://assets.example.test/close.png",
                "filename": "icon_close.png",
                "selected": True,
            }
        ],
    }
    selector_id, _ = server._register_slice_selector_payload(
        payload,
        cookies={"lanhu_cookie": "lh-cookie", "dds_cookie": "dds-cookie"},
    )

    app = server._build_slice_selector_prefab_app(selector_id, server._slice_selector_payloads[selector_id])
    app_json = app.to_json()

    serialized = str(app_json)
    assert "$prefab" in app_json
    assert "Checkbox" in serialized
    assert "Image" in serialized
    assert "lanhu_confirm_slice_selection" in serialized
    assert selector_id in serialized


def test_slice_selector_public_url_uses_configured_base(monkeypatch):
    server = _load_server(monkeypatch)
    monkeypatch.setenv("SLICE_SELECTOR_BASE_URL", "http://example.test/tools")

    url = server._slice_selector_public_url("abc123")

    assert url == "http://example.test/tools/slice-selector/abc123"


def test_submit_slice_selector_selection_filters_payload(monkeypatch):
    server = _load_server(monkeypatch)
    payload = {
        "design_name": "Home",
        "slices": [
            {"key": "1::0", "name": "one", "download_url": "https://assets.example.test/1.png"},
            {"key": "2::1", "name": "two", "download_url": "https://assets.example.test/2.png"},
        ],
    }
    selector_id, _ = server._register_slice_selector_payload(payload)

    selection = server._submit_slice_selector_selection(selector_id, ["2::1"])

    assert selection["status"] == "selected"
    assert selection["selected_count"] == 1
    assert [item["name"] for item in selection["selected_slices"]] == ["two"]
    assert server._slice_selector_payloads[selector_id]["selected_keys"] == ["2::1"]


def test_confirm_slice_selection_filters_truthy_prefab_state(monkeypatch):
    server = _load_server(monkeypatch)
    payload = {
        "design_name": "Home",
        "slices": [
            {"key": "1::0", "name": "one", "download_url": "https://assets.example.test/1.png"},
            {"key": "2::1", "name": "two", "download_url": "https://assets.example.test/2.png"},
        ],
    }
    selector_id, _ = server._register_slice_selector_payload(payload)

    selection = server._confirm_slice_selector_selection(
        selector_id,
        {"1::0": False, "2::1": True},
    )

    assert selection["status"] == "selected"
    assert selection["selected_count"] == 1
    assert [item["name"] for item in selection["selected_slices"]] == ["two"]


def test_register_slice_selector_rewrites_asset_urls_to_proxy(monkeypatch):
    server = _load_server(monkeypatch)
    payload = {
        "design_name": "Home",
        "slices": [
            {
                "key": "1::0",
                "name": "icon close",
                "thumb_url": "https://lanhuapp.com/thumb.png",
                "download_url": "https://dds.lanhuapp.com/file.png",
            }
        ],
    }

    selector_id, _ = server._register_slice_selector_payload(
        payload,
        cookies={"lanhu_cookie": "lh-cookie", "dds_cookie": "dds-cookie"},
    )
    item = server._slice_selector_payloads[selector_id]["slices"][0]
    encoded_key = quote("1::0", safe="")

    assert item["source_thumb_url"] == "https://lanhuapp.com/thumb.png"
    assert item["source_download_url"] == "https://dds.lanhuapp.com/file.png"
    assert item["thumb_url"] == f"http://127.0.0.1:8000/slice-selector/{selector_id}/asset/{encoded_key}?kind=thumb"
    assert item["download_url"] == f"http://127.0.0.1:8000/slice-selector/{selector_id}/asset/{encoded_key}?kind=download"


def test_slice_selector_asset_request_uses_dds_cookie_and_referer(monkeypatch):
    server = _load_server(monkeypatch)
    payload = {
        "design_name": "Home",
        "slices": [
            {
                "key": "1::0",
                "name": "icon close",
                "thumb_url": "https://lanhuapp.com/thumb.png",
                "download_url": "https://dds.lanhuapp.com/file.png",
            }
        ],
    }
    selector_id, _ = server._register_slice_selector_payload(
        payload,
        cookies={"lanhu_cookie": "lh-cookie", "dds_cookie": "dds-cookie"},
    )

    request = server._slice_selector_asset_request(selector_id, "1::0", "download")

    assert request["url"] == "https://dds.lanhuapp.com/file.png"
    assert request["headers"]["Cookie"] == "dds-cookie"
    assert request["headers"]["Referer"] == "https://dds.lanhuapp.com/"


def test_public_slice_selector_payload_does_not_expose_cookies(monkeypatch):
    server = _load_server(monkeypatch)
    payload = {
        "design_name": "Home",
        "slices": [{"key": "1::0", "name": "one", "download_url": "https://lanhuapp.com/1.png"}],
    }
    selector_id, _ = server._register_slice_selector_payload(
        payload,
        cookies={"lanhu_cookie": "lh-cookie", "dds_cookie": "dds-cookie"},
    )

    public_payload = server._public_slice_selector_payload(server._slice_selector_payloads[selector_id])

    assert "_cookies" not in public_payload
    assert "lh-cookie" not in str(public_payload)
    assert "dds-cookie" not in str(public_payload)
