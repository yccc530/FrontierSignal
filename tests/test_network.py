import pytest
from aiohttp.resolver import ThreadedResolver
from frontiersignal.config import Settings
from frontiersignal.network import Fetcher, FetchError, PublicResolver, retry_after_seconds


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.2", "169.254.169.254", "::1", "fc00::1"])
async def test_dns_rebinding_is_rejected(monkeypatch, address):
    async def resolve(self, host, port=0, family=0):
        return [{"host": address}]

    monkeypatch.setattr(ThreadedResolver, "resolve", resolve)
    with pytest.raises(ValueError, match="non-public"):
        await PublicResolver().resolve("feed.example", 443)


async def test_transient_http_retry_and_long_rate_limit(monkeypatch):
    fetcher = Fetcher(Settings(_env_file=None))
    calls = []

    async def flaky(url, headers):
        calls.append(url)
        if len(calls) == 1:
            raise FetchError("HTTP 503", 503)
        return b"ok", {}, 200

    monkeypatch.setattr(fetcher, "_request", flaky)
    assert (await fetcher.get("https://huggingface.co/feed"))[2] == 200
    assert len(calls) == 2

    async def rate_limited(url, headers):
        raise FetchError("HTTP 429", 429, 120)

    monkeypatch.setattr(fetcher, "_request", rate_limited)
    with pytest.raises(FetchError):
        await fetcher.get("https://huggingface.co/feed")
    assert retry_after_seconds("120") == 120
    assert retry_after_seconds("nan") == 0


async def test_response_transfer_counts_compression_redirect_retry_and_separate_tasks(monkeypatch):
    import asyncio
    import gzip

    from aiohttp import web
    from frontiersignal.network import TransferMeter, transfer_meter

    body = b"bounded public response fixture " * 200
    compressed = gzip.compress(body)
    attempts = 0

    async def handler(request):
        nonlocal attempts
        if request.path == "/redirect":
            return web.Response(status=302, headers={"Location": "/gzip"})
        if request.path == "/retry":
            attempts += 1
            if attempts == 1:
                return web.Response(status=503)
        if request.path == "/unchanged":
            return web.Response(status=304)
        return web.Response(body=compressed, headers={"Content-Encoding": "gzip"})

    app = web.Application()
    app.router.add_get("/{path}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    # Local fixture only: production URL/DNS restrictions remain covered above.
    monkeypatch.setattr("frontiersignal.network.validate_feed_url", lambda *_: None)
    monkeypatch.setattr("frontiersignal.network.PublicResolver", ThreadedResolver)
    fetcher = Fetcher(Settings(outbound_proxy="", _env_file=None))

    async def capture(path):
        meter = TransferMeter()
        token = transfer_meter.set(meter)
        try:
            result = await fetcher.get(f"http://127.0.0.1:{port}/{path}")
            return result, next(iter(meter.days.values()))
        finally:
            transfer_meter.reset(token)

    try:
        redirect, retry, cached = await asyncio.gather(
            capture("redirect"), capture("retry"), capture("unchanged")
        )
        for response, counters in (redirect, retry):
            assert response[0] == body
            assert counters["requests"] == 2
            assert counters["received_bytes"] == len(compressed)
            assert counters["decoded_bytes"] == len(body)
        assert cached[1]["requests"] == 1 and cached[1]["received_bytes"] == 0
        assert transfer_meter.get() is None
    finally:
        await runner.cleanup()


async def test_daily_traffic_preserves_unknown_history_and_utc_day_boundaries(database):
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from frontiersignal.models import TaskRun
    from frontiersignal.network import TransferMeter
    from frontiersignal.observability import collection_traffic

    db, _ = database
    at = datetime(2026, 10, 23, 0, 1, tzinfo=UTC)
    meter = TransferMeter()
    before = meter.begin_request(at - timedelta(minutes=2))
    meter.received(before, SimpleNamespace(total_raw_bytes=123, total_bytes=999))
    after = meter.begin_request(at)
    meter.received(after, SimpleNamespace(total_raw_bytes=456, total_bytes=1000))
    unknown = meter.begin_request(at)
    meter.received(unknown, SimpleNamespace(total_bytes=50))
    async with db.sessions() as session:
        session.add_all(
            [
                TaskRun(
                    kind="collect",
                    status="failed",
                    created_at=at - timedelta(minutes=2),
                    network_usage=meter.snapshot(),
                ),
                TaskRun(kind="collect", status="success", created_at=at),
                TaskRun(kind="collect", status="running", created_at=at),
                TaskRun(kind="analyze", status="success", created_at=at),
            ]
        )
        await session.commit()
        report = await collection_traffic(session, at)
    today, yesterday = report["days"][:2]
    assert today["date"] == "2026-10-23" and today["received_bytes"] == 456
    assert today["unmeasured_responses"] == 1 and today["requests"] == 2
    assert today["unmeasured_tasks"] == 1 and today["running_tasks"] == 1
    assert yesterday["received_bytes"] == 123 and yesterday["requests"] == 1
    assert len(report["days"]) == 7
