import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import douyin_user_parser_api as api
from api_common import BrowserPool


class UserAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_requests_and_shutdown_use_the_same_worker(self):
        calls = []

        def extract(url, maximum, cookies):
            calls.append(threading.get_ident())
            return {"user": {}, "works_count": 1, "works": [{"aweme_id": "1"}]}

        with patch.object(api, "get_all_user_works", side_effect=extract), patch.object(
            BrowserPool, "shutdown", side_effect=lambda: calls.append(threading.get_ident())
        ):
            async with api.lifespan(api.app):
                responses = await asyncio.gather(*(
                    api.root(url="https://www.douyin.com/user/user", max=1, cookie="") for _ in range(2)
                ))
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(set(calls)), 1)
        self.assertNotIn(threading.get_ident(), calls)

    async def test_invalid_cookie_file_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "cookie.json"
            cookie_file.write_text("[broken")
            with patch.object(BrowserPool, "shutdown"), patch.object(api, "get_all_user_works") as extract:
                async with api.lifespan(api.app):
                    response = await api.root(url="https://www.douyin.com/user/user", max=1, cookie=str(cookie_file))
            extract.assert_not_called()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.body)["data"], None)

    async def test_non_douyin_url_is_rejected_before_browser_use(self):
        response = await api.root(url="https://example.com/user/user", max=1, cookie="")
        self.assertEqual(response.status_code, 400)


class CookieReloadTests(unittest.TestCase):
    def test_replacing_cookie_file_is_visible_on_next_request(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "cookie.json"
            for value in ("old", "new"):
                cookie_file.write_text(json.dumps([{"name": "sessionid", "value": value}]))
                self.assertEqual(api._get_cookies(str(cookie_file))[0]["value"], value)


if __name__ == "__main__":
    unittest.main()
