from datetime import date
from decimal import Decimal

import httpx

from osip_dashboard.services import fx_rates


def test_export_fx_prefers_dated_nbk_rate(monkeypatch):
    target = date(2026, 7, 20)
    expected = fx_rates.FxRate(
        rate=Decimal("500.12"),
        effective_date=target,
        source="National Bank of Kazakhstan — official daily USD/KZT rate",
        source_url="https://nationalbank.kz/rss/get_rates.cfm?fdate=20.07.2026",
    )
    monkeypatch.setattr(fx_rates, "_fetch_nbk_exact", lambda value: expected if value == target else None)

    resolved = fx_rates.resolve_export_usd_kzt_rate(target, Decimal("469.83"))

    assert resolved == expected
    assert not resolved.fallback


def test_export_fx_uses_transparent_workbook_fallback_when_nbk_unavailable(monkeypatch):
    monkeypatch.setattr(fx_rates, "_fetch_nbk_exact", lambda value: None)

    resolved = fx_rates.resolve_export_usd_kzt_rate(date(2026, 7, 20), Decimal("469.83"))

    assert resolved is not None
    assert resolved.rate == Decimal("469.83")
    assert resolved.effective_date == date(2026, 7, 20)
    assert resolved.fallback is True
    assert "OSIP workbook" in resolved.source


def test_export_fx_does_not_fabricate_without_any_rate(monkeypatch):
    monkeypatch.setattr(fx_rates, "_fetch_nbk_exact", lambda value: None)

    assert fx_rates.resolve_export_usd_kzt_rate(date(2026, 7, 20), None) is None


def test_resolve_export_fx_rate_kzt_is_always_rate_one_with_no_lookup(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("KZT must never hit the NBK feed")

    monkeypatch.setattr(fx_rates, "_fetch_nbk_exact", _fail)

    resolved = fx_rates.resolve_export_fx_rate("KZT", date(2026, 7, 20))

    assert resolved.rate == Decimal("1")
    assert not resolved.fallback


def test_resolve_export_fx_rate_generalizes_to_any_currency(monkeypatch):
    target = date(2026, 7, 20)
    expected = fx_rates.FxRate(
        rate=Decimal("537.53"),
        effective_date=target,
        source="National Bank of Kazakhstan — official daily EUR/KZT rate",
        source_url="https://nationalbank.kz/rss/get_rates.cfm?fdate=20.07.2026",
    )
    monkeypatch.setattr(fx_rates, "_fetch_nbk_exact", lambda value, currency: expected if (value, currency) == (target, "EUR") else None)

    resolved = fx_rates.resolve_export_fx_rate("EUR", target)

    assert resolved == expected


def test_resolve_export_fx_rate_falls_back_and_then_gives_up_like_the_usd_resolver(monkeypatch):
    monkeypatch.setattr(fx_rates, "_fetch_nbk_exact", lambda value, currency: None)

    with_fallback = fx_rates.resolve_export_fx_rate("GBP", date(2026, 7, 20), Decimal("650.0"))
    assert with_fallback.fallback is True
    assert with_fallback.rate == Decimal("650.0")

    without_fallback = fx_rates.resolve_export_fx_rate("GBP", date(2026, 7, 20), None)
    assert without_fallback is None


def test_transient_nbk_failure_is_not_cached_and_a_later_retry_can_still_succeed(monkeypatch):
    """A single network/parse error must not permanently poison this date's cache.

    _fetch_nbk_exact is @lru_cache'd; catching a transient httpx error
    *inside* it and returning None would memoize that None forever, so
    every later call for the same date would silently keep using the
    offline fallback even after the network recovers. This exercises the
    real cached function (not a monkeypatched stand-in) to prove a failed
    attempt is retried, not memoized.
    """
    target = date(2026, 7, 20)
    fx_rates._fetch_nbk_exact.cache_clear()
    calls = {"count": 0}

    def flaky_get(url, timeout=5.0, follow_redirects=True):
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("network unreachable", request=httpx.Request("GET", url))
        return httpx.Response(
            200,
            content=(
                b"<rss><date>20.07.2026</date>"
                b"<item><title>USD</title><description>500,12</description><quant>1</quant></item>"
                b"</rss>"
            ),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(fx_rates.httpx, "get", flaky_get)
    try:
        # First attempt: the feed is unreachable. resolve_export_usd_kzt_rate
        # walks up to 7 preceding days too, so force a same-day-only check.
        first = fx_rates._fetch_nbk_exact_safe(target)
        assert first is None
        assert calls["count"] == 1

        # Second attempt for the SAME date: network is back. A cached
        # failure would return None again without calling httpx.get at all.
        second = fx_rates._fetch_nbk_exact_safe(target)
        assert second is not None
        assert second.rate == Decimal("500.12")
        assert calls["count"] == 2

        # Third attempt: now genuinely cached (a real success), no new call.
        third = fx_rates._fetch_nbk_exact_safe(target)
        assert third == second
        assert calls["count"] == 2
    finally:
        fx_rates._fetch_nbk_exact.cache_clear()
