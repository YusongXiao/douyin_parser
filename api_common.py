"""Shared browser lifecycle and URL validation for the HTTP services."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI

from douyin_parser import BrowserPool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Synchronous Playwright objects belong to the thread that created them.
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="douyin-browser")
    app.state.browser_executor = executor
    try:
        yield
    finally:
        try:
            await asyncio.get_running_loop().run_in_executor(executor, BrowserPool.shutdown)
        finally:
            executor.shutdown(wait=True)


def is_douyin_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return (
            parsed.scheme in {"http", "https"}
            and parsed.username is None
            and parsed.password is None
            and parsed.port in {None, 80, 443}
            and any(host == domain or host.endswith("." + domain)
                    for domain in ("douyin.com", "iesdouyin.com"))
        )
    except ValueError:
        return False
