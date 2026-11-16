import asyncio
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import douyin_phaser_api as api
from api_common import BrowserPool, is_douyin_url
from douyin_phaser import _block_unnecessary


class ResourcePolicyTests(unittest.TestCase):
    def test_security_scripts_are_allowed(self):
        for url in (
            "https://lf-cdn.example.com/obj/rc-web-sdk/secsdk.js",
            "https://verify.example.com/captcha/sdk.js",
        ):
            with self.subTest(url=url):
                route = Mock()
                _block_unnecessary(route, SimpleNamespace(resource_type="script", url=url))
                route.continue_.assert_called_once()
                route.abort.assert_not_called()

    def test_images_are_still_blocked(self):
        route = Mock()
        _block_unnecessary(route, SimpleNamespace(resource_type="image", url="https://example.com/image.jpg"))
        route.abort.assert_called_once()


class BrowserLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_requests_and_shutdown_share_one_worker(self):
        calls = []
        event_loop_thread = threading.get_ident()

        def extract(url):
            calls.append((url, threading.get_ident()))
            return {"type": "video", "items": [{"type": "video", "video_url": url}]}

        def shutdown():
            calls.append(("shutdown", threading.get_ident()))

        with patch.object(api, "get_douyin_media", side_effect=extract), patch.object(
            BrowserPool, "shutdown", side_effect=shutdown
        ):
            async with api.lifespan(api.app):
                responses = await asyncio.gather(
                    api.root(url="https://www.douyin.com/video/1"),
                    api.root(url="https://www.douyin.com/video/2"),
                )

        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1][0], "shutdown")
        worker_ids = {thread_id for _, thread_id in calls}
        self.assertEqual(len(worker_ids), 1)
        self.assertNotIn(event_loop_thread, worker_ids)

    async def test_extraction_exception_is_logged_and_returned(self):
        with patch.object(api, "get_douyin_media", side_effect=RuntimeError("browser failed")), patch.object(
            BrowserPool, "shutdown"
        ), self.assertLogs(api.logger, level="ERROR"):
            async with api.lifespan(api.app):
                response = await api.root(url="https://www.douyin.com/video/1")

        self.assertEqual(response.status_code, 500)
        self.assertIn("browser failed", json.loads(response.body)["message"])


class URLValidationTests(unittest.TestCase):
    def test_only_douyin_http_urls_are_accepted(self):
        for url in ("https://v.douyin.com/abc/", "https://www.douyin.com/video/123", "http://www.iesdouyin.com/share/video/123/"):
            with self.subTest(url=url):
                self.assertTrue(is_douyin_url(url))
        for url in ("httpwhatever", "file:///etc/hosts", "http://localhost", "https://douyin.com.evil.example/user/a", "https://evil.example/?url=douyin.com", "https://douyin.com@evil.example/", "https://www.douyin.com:bad/"):
            with self.subTest(url=url):
                self.assertFalse(is_douyin_url(url))


if __name__ == "__main__":
    unittest.main()
