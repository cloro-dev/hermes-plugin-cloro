"""Adapt the cloro Google Search response to the Hermes web_search contract."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from agent.secret_scope import get_secret
from agent.web_search_provider import WebSearchProvider

_ENDPOINT = "https://api.cloro.dev/v1/monitor/google"
_KEY_ENV = "CLORO_API_KEY"
_KEY_URL = "https://dashboard.cloro.dev/api-keys?utm_source=hermes-agent&utm_medium=byok"
# cloro opens the live results page during the request, so allow more time than a search index needs.
_TIMEOUT_SECONDS = 120


def _failure(message):
    return {"success": False, "error": f"cloro: {message}"}


def _error_message(body, status):
    # Failures arrive as {"success": false, "error": {"code": "...", "message": "..."}}.
    try:
        error = json.loads(body).get("error") or {}
    except (ValueError, AttributeError):
        error = {}
    message = error.get("message") if isinstance(error, dict) else None
    return message or f"request returned HTTP {status}"


def _results(data, limit):
    result = data.get("result") if isinstance(data, dict) else None
    items = result.get("organicResults") if isinstance(result, dict) else None
    if not isinstance(items, list):
        raise ValueError("response must contain result.organicResults")
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("link")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        title = item.get("title")
        snippet = item.get("snippet")
        rows.append(
            {
                "title": title if isinstance(title, str) else "",
                "url": url,
                "description": snippet if isinstance(snippet, str) else "",
                "position": len(rows) + 1,
            }
        )
        if len(rows) >= limit:
            break
    return {"success": True, "data": {"web": rows}}


class CloroWebSearchProvider(WebSearchProvider):
    """Search only: live Google organic results. Pair it with an extract backend for web_extract."""

    def __init__(self, ctx):
        # Read settings on every call: one process can serve several profiles.
        self._get_config = ctx.get_config

    @property
    def name(self):
        return "cloro"

    @property
    def display_name(self):
        return "cloro (Google Search)"

    def _country(self):
        value = self._get_config("country", "US")
        country = value.strip().upper() if isinstance(value, str) else ""
        if not re.fullmatch(r"[A-Z]{2}", country):
            raise ValueError("country must be a 2-letter ISO 3166-1 code, for example US")
        return country

    def is_available(self):
        return bool((get_secret(_KEY_ENV) or "").strip())

    def get_setup_schema(self):
        return {
            "name": self.display_name,
            "badge": "paid",
            "tag": "Live Google results. Search only.",
            "env_vars": [{"key": _KEY_ENV, "prompt": "cloro API key", "url": _KEY_URL}],
        }

    def search(self, query, limit=5):
        api_key = (get_secret(_KEY_ENV) or "").strip()
        if not api_key:
            return _failure(f"set {_KEY_ENV} through hermes tools or the plugin settings")
        if not isinstance(query, str) or not query.strip():
            return _failure("query must not be empty")
        try:
            country = self._country()
        except ValueError as exc:
            return _failure(str(exc))
        request = urllib.request.Request(
            _ENDPOINT,
            data=json.dumps({"query": query, "country": country}).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "hermes-plugin-cloro",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            return _failure(_error_message(exc.read(), exc.code))
        except (urllib.error.URLError, TimeoutError):
            return _failure("could not reach the API")
        try:
            return _results(json.loads(body), max(1, int(limit)))
        except ValueError as exc:
            return _failure(f"invalid API response: {exc}")
