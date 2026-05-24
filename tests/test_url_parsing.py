"""Tests for Lanhu URL parsing behavior."""

from tests.test_lanhu_slice_list_logic import _load_server


def test_parse_url_uses_team_id_when_tid_is_missing(monkeypatch):
    server = _load_server(monkeypatch)
    url = "https://lanhuapp.com/web/#/item/project/product?teamId=team-1&pid=project-1&docId=doc-1"

    params = server.LanhuExtractor.parse_url(url)

    assert params["team_id"] == "team-1"
    assert params["project_id"] == "project-1"
    assert params["doc_id"] == "doc-1"


def test_parse_url_accepts_team_id_in_parameter_string(monkeypatch):
    server = _load_server(monkeypatch)

    params = server.LanhuExtractor.parse_url("teamId=team-2&pid=project-2&versionId=version-2")

    assert params["team_id"] == "team-2"
    assert params["project_id"] == "project-2"
    assert params["version_id"] == "version-2"


def test_parse_url_prefers_tid_over_team_id(monkeypatch):
    server = _load_server(monkeypatch)

    params = server.LanhuExtractor.parse_url("tid=team-primary&teamId=team-fallback&pid=project-3")

    assert params["team_id"] == "team-primary"


async def test_resolve_url_params_fetches_team_id_when_url_does_not_include_it(monkeypatch):
    server = _load_server(monkeypatch)

    class Response:
        status_code = 200

        def json(self):
            return {
                "code": "00000",
                "msg": "success",
                "result": "{\"teamStatus\":{\"team_id\":\"team-from-settings\",\"role\":\"member\"}}",
            }

        def raise_for_status(self):
            pass

    class Client:
        def __init__(self):
            self.requested = []

        async def get(self, url, **kwargs):
            self.requested.append((url, kwargs))
            return Response()

    extractor = server.LanhuExtractor("cookie=value")
    extractor.client = Client()

    params = await extractor.resolve_url_params(
        "https://lanhuapp.com/web/#/item/project/stage?pid=project-4"
    )

    assert params["team_id"] == "team-from-settings"
    assert params["project_id"] == "project-4"
    assert extractor.client.requested == [
        (
            "https://lanhuapp.com/api/account/user_settings",
            {"params": {"settings_type": "web_main"}},
        )
    ]
