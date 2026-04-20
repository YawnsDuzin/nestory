from app.logging_setup import init_sentry


def test_init_sentry_noop_when_dsn_missing(monkeypatch) -> None:
    called = {"inited": False}
    import sentry_sdk

    def fake_init(**kwargs):
        called["inited"] = True

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    init_sentry("", "local")
    assert called["inited"] is False


def test_init_sentry_calls_init_when_dsn_present(monkeypatch) -> None:
    called = {}
    import sentry_sdk

    def fake_init(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    init_sentry("https://key@o0.ingest.sentry.io/0", "production")
    assert called["dsn"].startswith("https://")
    assert called["environment"] == "production"
    assert called["send_default_pii"] is False
