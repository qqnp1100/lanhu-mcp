import asyncio


def _load_server(monkeypatch):
    monkeypatch.setenv("LANHU_COOKIE", "test-cookie")
    import lanhu_mcp_server

    return lanhu_mcp_server


def test_mcp_middleware_injects_missing_request_content_type(monkeypatch):
    server = _load_server(monkeypatch)
    seen_headers = {}

    async def app(scope, receive, send):
        seen_headers["headers"] = dict(scope["headers"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    async def run():
        middleware = server.MCPContentTypeMiddleware(app)
        messages = []

        async def send(message):
            messages.append(message)

        await middleware(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "headers": [(b"accept", b"application/json, text/event-stream")],
            },
            lambda: {"type": "http.request", "body": b"{}"},
            send,
        )
        return messages

    messages = asyncio.run(run())

    assert seen_headers["headers"][b"content-type"] == b"application/json"
    response_start = messages[0]
    assert dict(response_start["headers"])[b"content-type"] == b"application/json; charset=utf-8"


def test_mcp_middleware_preserves_existing_response_content_type(monkeypatch):
    server = _load_server(monkeypatch)

    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    async def run():
        middleware = server.MCPContentTypeMiddleware(app)
        messages = []

        async def send(message):
            messages.append(message)

        await middleware(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "headers": [(b"content-type", b"application/json")],
            },
            lambda: {"type": "http.request", "body": b"{}"},
            send,
        )
        return messages

    response_start = asyncio.run(run())[0]

    assert dict(response_start["headers"])[b"content-type"] == b"text/event-stream"
