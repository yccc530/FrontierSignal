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


async def test_mixed_dns_answers_never_pass_private_or_reserved_addresses(monkeypatch):
    async def resolve(self, host, port=0, family=0):
        return [{"host": address} for address in ["127.0.0.1", "2001::c760:3b13", "1.1.1.1"]]

    monkeypatch.setattr(ThreadedResolver, "resolve", resolve)
    assert await PublicResolver().resolve("feed.example", 443) == [{"host": "1.1.1.1"}]
