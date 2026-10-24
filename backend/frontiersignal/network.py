import asyncio
import ipaddress
import json
import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

import aiohttp

from .config import Settings

DEFAULT_HOSTS = {
    "www.anthropic.com",
    "cohere.com",
    "seed.bytedance.com",
    "x.ai",
    "aws.amazon.com",
    "api.openalex.org",
    "huggingface.co",
    "openai.com",
    "deepmind.google",
    "research.google",
    "machinelearning.apple.com",
    "blogs.microsoft.com",
    "blog.google",
    "developer.nvidia.com",
    "blogs.nvidia.com",
    "rss.arxiv.org",
    "export.arxiv.org",
    "hacker-news.firebaseio.com",
    "api.github.com",
}


def validate_feed_url(url: str, hosts: set[str]) -> None:
    p = urlsplit(url)
    if (
        p.scheme != "https"
        or p.hostname not in hosts
        or p.port not in (None, 443)
        or p.username
        or p.password
        or p.fragment
    ):
        raise ValueError("URL must use HTTPS on an explicitly allowed feed host")


class PublicResolver(aiohttp.resolver.ThreadedResolver):
    async def resolve(self, host, port=0, family=0):
        records = await super().resolve(host, port, family)
        # Only these validated addresses reach the connector (or the proxy CONNECT target).
        records = [record for record in records if ipaddress.ip_address(record["host"]).is_global]
        if not records:
            raise ValueError("Feed DNS resolved to a non-public address")
        return records


class FetchError(Exception):
    def __init__(self, message, status=None, delay=0.0):
        super().__init__(message)
        self.status, self.delay = status, delay


def retry_after_seconds(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        delay = float(value)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            delay = (parsed - datetime.now(UTC)).total_seconds()
        except (ValueError, TypeError):
            return 0.0
    return max(0.0, delay) if math.isfinite(delay) else 0.0


class Fetcher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.hosts = DEFAULT_HOSTS | set(settings.extra_feed_hosts)

    async def get(self, url: str, headers: dict | None = None) -> tuple[bytes, dict, int]:
        # The connector connects to addresses returned by this resolver. A second
        # uncontrolled DNS lookup cannot redirect a validated host to loopback.
        validate_feed_url(url, self.hosts)
        for attempt in range(3):
            try:
                return await self._request(url, headers or {})
            except FetchError as exc:
                if attempt == 2 or exc.status not in {429, 500, 502, 503, 504} or exc.delay > 60:
                    raise
                await asyncio.sleep(max(exc.delay, 0.5 * 2**attempt))
            except (aiohttp.ClientError, TimeoutError) as exc:
                if attempt == 2:
                    raise FetchError(f"Network request failed ({type(exc).__name__})") from None
                await asyncio.sleep(0.5 * 2**attempt)
        raise AssertionError("unreachable")

    async def _request(self, url: str, headers: dict) -> tuple[bytes, dict, int]:
        proxy = self.settings.outbound_proxy.get_secret_value() or None
        resolver = PublicResolver()
        connector = aiohttp.TCPConnector(resolver=None if proxy else resolver, ttl_dns_cache=30)
        timeout = aiohttp.ClientTimeout(total=self.settings.fetch_timeout)
        initial_host = urlsplit(url).hostname
        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout, trust_env=False
        ) as client:
            for _ in range(4):
                validate_feed_url(url, self.hosts)
                request_headers = {
                    "User-Agent": "FrontierSignal/0.1 (personal feed reader)",
                    **headers,
                }
                if urlsplit(url).hostname != initial_host:
                    request_headers.pop("Authorization", None)
                target_url, server_hostname = url, None
                if proxy:
                    parsed = urlsplit(url)
                    records = await asyncio.wait_for(resolver.resolve(parsed.hostname, 443), 10)
                    address = records[0]["host"]
                    address = f"[{address}]" if ":" in address else address
                    target_url = urlunsplit(("https", address, parsed.path, parsed.query, ""))
                    server_hostname = parsed.hostname
                    request_headers["Host"] = parsed.hostname
                    # CONNECT to the validated IP, with the original TLS hostname.
                async with client.get(
                    target_url,
                    headers=request_headers,
                    allow_redirects=False,
                    proxy=proxy,
                    server_hostname=server_hostname,
                ) as r:
                    if r.status in {301, 302, 303, 307, 308}:
                        url = urljoin(url, r.headers.get("Location", ""))
                        continue
                    if r.status == 304:
                        return b"", dict(r.headers), 304
                    if r.status != 200:
                        raise FetchError(
                            f"HTTP {r.status}; source refused or unavailable",
                            r.status,
                            retry_after_seconds(r.headers.get("Retry-After")),
                        )
                    chunks, size = [], 0
                    async for chunk in r.content.iter_chunked(65536):
                        size += len(chunk)
                        if size > 5_000_000:
                            raise FetchError("Source response exceeds 5 MB")
                        chunks.append(chunk)
                    return b"".join(chunks), dict(r.headers), r.status
        raise FetchError("Too many redirects")

    async def json(self, url: str, headers: dict | None = None):
        body, _, _ = await self.get(url, headers)
        return json.loads(body)
