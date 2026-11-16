"""
Douyin User Works Extractor API Server
Provides HTTP API for extracting all work share-links from a Douyin user profile.

Usage:
    python douyin_user_parser_api.py
    # Server runs on http://localhost:8001

API:
    GET /?url=<douyin_user_url>
    GET /?url=<douyin_user_url>&max=50
    GET /?url=<douyin_user_url>&cookie=douyin_cookies.json
"""

import asyncio
import logging
import os
from functools import partial
from urllib.parse import urlparse
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from api_common import is_douyin_url, lifespan
from douyin_user_parser import extract_sec_user_id, get_all_user_works, load_cookies

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Douyin User Works Extractor API",
    description="Extract all work share-links (video / note) from a Douyin user profile",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Cookie loading happens on the browser worker so file I/O does not block HTTP.
# ---------------------------------------------------------------------------
def _get_cookies(cookie_arg: str | None) -> list[dict]:
    """Reload cookies on each request so a new login takes effect immediately."""
    if cookie_arg is None and os.path.isfile("douyin_cookies.json"):
        cookie_arg = "douyin_cookies.json"
    return load_cookies(cookie_arg)


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------

def _extract_user_works(url, max_works, cookie_arg):
    try:
        cookies = _get_cookies(cookie_arg)
    except (OSError, ValueError) as exc:
        raise ValueError("Invalid or unreadable cookie input") from exc
    return get_all_user_works(url, max_works, cookies=cookies)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(code: int, message: str):
    return JSONResponse(
        status_code=code,
        content={"code": code, "message": message, "data": None},
    )


def _success_response(data: dict):
    return JSONResponse(
        status_code=200,
        content={"code": 0, "message": "success", "data": data},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root(
    url: str = Query(None, description="Douyin user profile URL"),
    max: int = Query(None, gt=0, description="Maximum number of works to fetch"),
    cookie: str = Query(None, description="Cookie string, cookie file path, or JSON cookie file (from --login)"),
):
    """
    Root endpoint.
    - ``url`` provided → extract all works from the user profile.
    - No ``url`` → return API info.
    """
    if url:
        if not is_douyin_url(url):
            return _error_response(400, "URL must be an http/https Douyin URL")

        if not extract_sec_user_id(urlparse(url).path):
            return _error_response(400, "URL must be a Douyin user profile URL containing /user/")

        try:
            result = await asyncio.get_running_loop().run_in_executor(
                app.state.browser_executor, partial(_extract_user_works, url, max, cookie)
            )
        except ValueError as e:
            return _error_response(400, str(e))
        except Exception as e:
            logger.exception("User works extraction failed")
            return _error_response(500, f"Extraction failed: {str(e)}")

        if not result:
            return _error_response(500, "Extraction failed: no works found")

        return _success_response(result)

    return {
        "name": "Douyin User Works Extractor API",
        "version": "1.0.0",
        "usage": "GET /?url=<douyin_user_url>",
        "params": {
            "url": "Douyin user profile URL (required)",
            "max": "Maximum number of works to fetch (optional)",
            "cookie": "Cookie string or path to cookie file (optional, defaults to douyin_cookies.json)",
        },
        "docs": "/docs",
        "tip": "Run `python douyin_user_parser.py --login` first to export cookies with HttpOnly auth tokens.",
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
