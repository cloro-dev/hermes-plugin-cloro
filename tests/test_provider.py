"""Unit tests for the cloro web search provider. The network is mocked."""

import io
import json
import urllib.error

import hermes_plugin_cloro
import pytest
from hermes_plugin_cloro import provider as cloro

GOOGLE_RESPONSE = {
    "success": True,
    "result": {
        "organicResults": [
            {
                "position": 1,
                "title": "Hermes Agent",
                "link": "https://hermes-agent.nousresearch.com",
                "snippet": "An agent.",
            },
            {"position": 2, "title": "Unresolved", "link": "", "snippet": "No link yet."},
            {"position": 3, "title": "GitHub", "link": "https://github.com/NousResearch/hermes-agent", "snippet": None},
            {"position": 4, "title": "Docs", "link": "https://hermes-agent.nousresearch.com/docs", "snippet": "Docs."},
        ]
    },
}


class FakeContext:
    def __init__(self, settings=None):
        self.settings = settings or {}
        self.providers = []

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_web_search_provider(self, provider):
        self.providers.append(provider)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setattr(
        cloro, "get_secret", lambda name, default=None: "test-key" if name == "CLORO_API_KEY" else default
    )


class Calls(list):
    """Records each request and answers it with the payload given to respond()."""

    def __init__(self, monkeypatch):
        super().__init__()
        self.monkeypatch = monkeypatch

    def respond(self, payload):
        def urlopen(request, timeout):
            self.append({"request": request, "timeout": timeout})
            return FakeResponse(json.dumps(payload).encode())

        self.monkeypatch.setattr(cloro.urllib.request, "urlopen", urlopen)


@pytest.fixture
def calls(monkeypatch):
    return Calls(monkeypatch)


def provider(settings=None):
    return cloro.CloroWebSearchProvider(FakeContext(settings))


def test_register_adds_the_provider():
    ctx = FakeContext()
    hermes_plugin_cloro.register(ctx)
    assert [p.name for p in ctx.providers] == ["cloro"]
    assert ctx.providers[0].display_name == "cloro (Google Search)"


def test_not_available_without_key(monkeypatch):
    monkeypatch.setattr(cloro, "get_secret", lambda name, default=None: default)
    assert provider().is_available() is False
    result = provider().search("hermes")
    assert result["success"] is False
    assert "CLORO_API_KEY" in result["error"]


def test_available_with_key(api_key):
    assert provider().is_available() is True


def test_search_sends_query_and_country(api_key, calls):
    calls.respond(GOOGLE_RESPONSE)
    provider({"country": "de"}).search("hermes agent")
    request = calls[0]["request"]
    assert request.full_url == "https://api.cloro.dev/v1/monitor/google"
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"query": "hermes agent", "country": "DE"}
    assert request.get_header("Authorization") == "Bearer test-key"
    assert calls[0]["timeout"] == 120


def test_search_maps_results_and_skips_entries_without_a_link(api_key, calls):
    calls.respond(GOOGLE_RESPONSE)
    result = provider().search("hermes agent", limit=5)
    assert result == {
        "success": True,
        "data": {
            "web": [
                {
                    "title": "Hermes Agent",
                    "url": "https://hermes-agent.nousresearch.com",
                    "description": "An agent.",
                    "position": 1,
                },
                {
                    "title": "GitHub",
                    "url": "https://github.com/NousResearch/hermes-agent",
                    "description": "",
                    "position": 2,
                },
                {
                    "title": "Docs",
                    "url": "https://hermes-agent.nousresearch.com/docs",
                    "description": "Docs.",
                    "position": 3,
                },
            ]
        },
    }


def test_search_respects_limit(api_key, calls):
    calls.respond(GOOGLE_RESPONSE)
    result = provider().search("hermes agent", limit=1)
    assert [row["url"] for row in result["data"]["web"]] == ["https://hermes-agent.nousresearch.com"]


def test_invalid_country_fails_without_a_request(api_key, calls):
    calls.respond(GOOGLE_RESPONSE)
    result = provider({"country": "Germany"}).search("hermes")
    assert result["success"] is False
    assert "country" in result["error"]
    assert calls == []


def test_empty_query_fails(api_key):
    assert provider().search("  ")["success"] is False


def test_error_envelope_message_is_returned(api_key, monkeypatch):
    body = json.dumps({"success": False, "error": {"code": "INSUFFICIENT_CREDITS", "message": "Not enough credits"}})

    def urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 402, "Payment Required", {}, io.BytesIO(body.encode()))

    monkeypatch.setattr(cloro.urllib.request, "urlopen", urlopen)
    assert provider().search("hermes") == {"success": False, "error": "cloro: Not enough credits"}


def test_http_error_without_envelope(api_key, monkeypatch):
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 502, "Bad Gateway", {}, io.BytesIO(b"<html>"))

    monkeypatch.setattr(cloro.urllib.request, "urlopen", urlopen)
    assert provider().search("hermes") == {"success": False, "error": "cloro: request returned HTTP 502"}


def test_network_error(api_key, monkeypatch):
    def urlopen(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(cloro.urllib.request, "urlopen", urlopen)
    assert provider().search("hermes") == {"success": False, "error": "cloro: could not reach the API"}


def test_unexpected_response_shape(api_key, calls):
    calls.respond({"success": True, "result": {}})
    result = provider().search("hermes")
    assert result["success"] is False
    assert "organicResults" in result["error"]
