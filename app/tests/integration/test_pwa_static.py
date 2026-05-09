"""Verify PWA static assets are served correctly."""
import json

from fastapi.testclient import TestClient


def test_manifest_served_and_valid_json(client: TestClient) -> None:
    r = client.get("/static/manifest.webmanifest")
    assert r.status_code == 200
    m = json.loads(r.text)
    assert m["name"]
    assert m["short_name"] == "Nestory"
    assert m["start_url"] == "/"
    assert m["display"] == "standalone"
    assert m["icons"]


def test_sw_js_served(client: TestClient) -> None:
    r = client.get("/static/sw.js")
    assert r.status_code == 200
    assert "CACHE_VERSION" in r.text
    assert "fetch" in r.text


def test_pwa_js_served(client: TestClient) -> None:
    r = client.get("/static/js/pwa.js")
    assert r.status_code == 200
    assert "serviceWorker" in r.text


def test_base_html_includes_manifest_link(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'rel="manifest"' in r.text
    assert 'apple-mobile-web-app-capable' in r.text
