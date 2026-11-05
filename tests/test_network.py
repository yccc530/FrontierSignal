import pytest
from aiohttp.resolver import ThreadedResolver
from frontiersignal import network
from frontiersignal.collectors.github_discovery import error_message
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


@pytest.mark.parametrize("resource", ["core", "search"])
async def test_github_primary_quota_pauses_only_matching_resource_and_identity(
    monkeypatch, resource
):
    fetcher = Fetcher(Settings(_env_file=None))
    clock = [100.0]
    monkeypatch.setattr(network.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(network.time, "time", lambda: 1_000.0)
    urls = {
        "core": "https://api.github.com/repos/example/repo/releases",
        "search": "https://api.github.com/search/repositories?q=llm",
    }
    url = urls[resource]
    calls = []

    async def request(url, headers):
        calls.append(url)
        if len(calls) == 1:
            raise fetcher._response_error(
                url,
                headers,
                403,
                {
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": "1120",
                    "X-RateLimit-Resource": resource,
                },
            )
        return b"ok", {}, 200

    monkeypatch.setattr(fetcher, "_request", request)
    for _ in range(2):
        with pytest.raises(FetchError, match="预计.*UTC") as caught:
            await fetcher.get(url)
        assert caught.value.rate_limited
    assert len(calls) == 1
    assert "预计" in error_message(caught.value, "版本跟踪")
    assert (await fetcher.get(urls["search" if resource == "core" else "core"]))[2] == 200
    assert (await fetcher.get("https://huggingface.co/feed.xml"))[2] == 200
    assert (await fetcher.get(url, {"Authorization": "Bearer test-only-token"}))[2] == 200
    assert "test-only-token" not in str(fetcher._github_cooldowns)
    clock[0] += 121
    assert (await fetcher.get(url))[2] == 200


@pytest.mark.parametrize("status", [403, 429])
async def test_github_retry_after_pauses_both_resources_without_immediate_retry(
    monkeypatch, status
):
    fetcher = Fetcher(Settings(_env_file=None))
    calls = []

    async def request(url, headers):
        calls.append(url)
        raise fetcher._response_error(url, headers, status, {"Retry-After": "30"})

    monkeypatch.setattr(fetcher, "_request", request)
    for path in ("repos/example/repo", "search/repositories?q=llm"):
        with pytest.raises(FetchError) as caught:
            await fetcher.get("https://api.github.com/" + path)
        assert caught.value.rate_limited
    assert len(calls) == 1


@pytest.mark.parametrize("reset", [None, "invalid", "nan", "inf", "1e100", "0"])
async def test_github_permission_error_or_invalid_reset_does_not_cache_quota(monkeypatch, reset):
    fetcher = Fetcher(Settings(_env_file=None))
    calls = []

    async def request(url, headers):
        calls.append(url)
        response_headers = (
            {}
            if reset is None
            else {
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": reset,
            }
        )
        raise fetcher._response_error(url, headers, 403, response_headers)

    monkeypatch.setattr(fetcher, "_request", request)
    for _ in range(2):
        with pytest.raises(FetchError, match="HTTP 403") as caught:
            await fetcher.get("https://api.github.com/repos/example/repo")
        assert not caught.value.rate_limited
    assert len(calls) == 2
    assert not fetcher._github_cooldowns
