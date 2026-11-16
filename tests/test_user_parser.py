import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from playwright.sync_api import Page

import douyin_user_phaser as parser


class CookieTests(unittest.TestCase):
    def test_cookie_values_preserve_equals_signs(self):
        cookies = parser.parse_cookie_string("sessionid=abc==; =bad; token=xyz")
        self.assertEqual([(c["name"], c["value"]) for c in cookies], [("sessionid", "abc=="), ("token", "xyz")])

    def test_invalid_json_and_missing_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cookies.json"
            for content in ("[broken", "{}", "[null]", '[{"name":"test"}]'):
                with self.subTest(content=content):
                    path.write_text(content)
                    with self.assertRaises(ValueError):
                        parser.load_cookies(str(path))

    def test_missing_file_is_not_silently_used_as_an_empty_login(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                parser.load_cookies(str(Path(directory) / "missing.json"))

    def test_nameless_exported_cookie_does_not_discard_valid_login(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cookies.json"
            path.write_text(json.dumps([{"name": "", "value": "ignored"}, {"name": "sessionid", "value": "test"}]))
            cookies = parser.load_cookies(str(path))
        self.assertEqual([c["name"] for c in cookies], ["sessionid"])


class PaginationTests(unittest.TestCase):
    @patch.object(parser.time, "sleep")
    def test_overlapping_pages_are_deduplicated_and_stuck_cursor_stops(self, _sleep):
        pages = [
            {"aweme_list": [{"aweme_id": "1"}, {"aweme_id": "2"}], "has_more": 1, "max_cursor": 100},
            {"aweme_list": [{"aweme_id": "2"}, {"aweme_id": "3"}], "has_more": 1, "max_cursor": 100},
        ]
        with patch.object(parser, "_fetch_posts_api", side_effect=pages) as fetch:
            result = parser._try_api_approach(Mock(), "user")
        self.assertEqual([item["aweme_id"] for item in result["works"]], ["1", "2", "3"])
        self.assertEqual(fetch.call_count, 2)

    @patch.object(parser.time, "sleep")
    def test_maximum_applies_after_deduplication(self, _sleep):
        pages = [
            {"aweme_list": [{"aweme_id": "1"}, {"aweme_id": "1"}], "has_more": 1, "max_cursor": 100},
            {"aweme_list": [{"aweme_id": "2"}, {"aweme_id": "3"}], "has_more": 0},
        ]
        with patch.object(parser, "_fetch_posts_api", side_effect=pages):
            result = parser._try_api_approach(Mock(), "user", max_works=2)
        self.assertEqual([item["aweme_id"] for item in result["works"]], ["1", "2"])

    @patch.object(parser.time, "sleep")
    def test_xhr_wait_is_registered_before_navigation_and_errors_are_retried(self, _sleep):
        page = Mock(spec=Page)
        page.evaluate.side_effect = [
            {"status_code": 8, "status_msg": "try again"},
            {"aweme_list": [{"aweme_id": "1"}], "has_more": 1, "max_cursor": 100},
            {"aweme_list": [{"aweme_id": "2"}], "has_more": 1, "max_cursor": 100},
        ]
        response_wait = Mock()
        response_wait.__enter__ = Mock()
        response_wait.__exit__ = Mock(return_value=False)
        page.expect_response.return_value = response_wait
        page.goto.side_effect = lambda *args, **kwargs: response_wait.__enter__.assert_called_once()
        context = Mock()
        with patch.object(parser, "_create_user_page_context", return_value=(context, page)):
            result = parser._try_xhr_pagination("user", "https://www.douyin.com/user/user")
        self.assertEqual(result["works_count"], 2)
        self.assertEqual(page.evaluate.call_count, 3)
        context.close.assert_called_once()


class UserParserTests(unittest.TestCase):
    def test_nullable_cover_fields(self):
        item = {"aweme_id": "1", "video": {"cover": None, "raw_cover": {"url_list": ["https://example.com/obj/cover"]}}}
        self.assertEqual(parser._parse_aweme_item(item)["cover"], "https://example.com/obj/cover")

    def test_maximum_must_be_positive(self):
        for maximum in (0, -1):
            with self.assertRaises(ValueError):
                parser.get_all_user_works("https://www.douyin.com/user/user", maximum)

    def test_profile_and_fallback_receive_supplied_cookies(self):
        cookies = [{"name": "sessionid", "value": "test", "domain": ".douyin.com", "path": "/"}]
        context, page = Mock(), Mock()
        expected = {"user": {}, "works_count": 1, "works": [{"aweme_id": "1"}]}
        with patch.object(parser, "_create_user_page_context", return_value=(context, page)) as create, patch.object(
            parser, "_fetch_user_profile", return_value={}
        ) as profile, patch.object(parser, "_try_xhr_pagination", return_value=None), patch.object(
            parser, "_try_api_approach", return_value=expected
        ) as fallback:
            result = parser.get_all_user_works("https://www.douyin.com/user/user", cookies=cookies)
        self.assertEqual(result, expected)
        create.assert_called_once_with(cookies=cookies)
        profile.assert_called_once_with(page, "user")
        fallback.assert_called_once_with(page, "user", None)
        context.close.assert_called_once()

    def test_json_cli_stdout_contains_only_json(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        expected = {"user": {}, "works_count": 1, "works": [{"aweme_id": "1"}]}

        def extract(*args, **kwargs):
            print("progress log")
            return expected

        with patch("sys.argv", ["douyin_user_phaser.py", "https://www.douyin.com/user/user", "--json"]), patch.object(
            parser, "get_all_user_works", side_effect=extract
        ), patch.object(parser.BrowserPool, "shutdown", side_effect=lambda: print("shutdown log")), redirect_stdout(stdout), redirect_stderr(stderr):
            parser.main()
        self.assertEqual(json.loads(stdout.getvalue())["data"], expected)
        self.assertIn("progress log", stderr.getvalue())
        self.assertIn("shutdown log", stderr.getvalue())

    def test_interactive_browser_is_closed_if_login_is_interrupted(self):
        pw = Mock()
        with patch.object(parser, "_capture_login_cookies", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                parser._login_with_browser(pw, "cookies.json")
        pw.chromium.launch.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
