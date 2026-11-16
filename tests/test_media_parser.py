import unittest
from unittest.mock import Mock

from douyin_phaser import _parse_video_detail, extract_images_from_dom, extract_videos_from_dom, extract_video_from_api


class MediaParserTests(unittest.TestCase):
    def test_default_play_address_works_without_bitrate_list(self):
        url = "https://v3-web.douyinvod.com/video/example.mp4"
        for bitrates in ({}, {"bit_rate": None}):
            with self.subTest(bitrates=bitrates):
                detail = {"video": {"play_addr": {"url_list": [url]}, "cover": None, **bitrates}}
                result = _parse_video_detail(detail)
                self.assertEqual(result["items"][0]["video_url"], url)

    def test_image_post_is_not_mistaken_for_video(self):
        detail = {"images": [{"url_list": ["https://example.com/image"]}], "video": {"play_addr": {"url_list": ["https://example.com/preview.mp4"]}}}
        self.assertIsNone(_parse_video_detail(detail))

    def test_intercepted_response_also_accepts_default_play_address(self):
        url = "https://v3-web.douyinvod.com/video/example.mp4"
        response = Mock()
        response.url = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
        response.status = 200
        response.json.return_value = {"aweme_detail": {"video": {"play_addr": {"url_list": [url]}}}}
        found = {}
        extract_video_from_api(Mock(), found)(response)
        self.assertEqual(found["url"], url)

    def test_preferred_video_is_not_lost_after_duplicate_is_seen(self):
        urls = [
            "https://v9.douyinvod.com/video/tos/cn/bucket/abc/?a=1",
            "https://v3-web.douyinvod.com/video/tos/cn/bucket/abc/?a=2",
        ]
        videos = []
        for url in urls:
            video = Mock()
            video.get_attribute.return_value = url
            video.query_selector_all.return_value = []
            videos.append(video)
        page = Mock()
        page.query_selector_all.return_value = videos
        self.assertEqual(extract_videos_from_dom(page), [urls[1]])

    def test_dom_images_keep_original_order_while_removing_duplicates(self):
        urls = [f"https://p3.douyinpic.com/tos-cn-i-0813/{key}~tplv.webp?biz_tag=aweme_images&x-signature=test" for key in ("first", "second", "first")]
        images = []
        for url in urls:
            image = Mock()
            image.get_attribute.return_value = url
            images.append(image)
        page = Mock()
        page.query_selector_all.side_effect = [images, []]
        self.assertEqual(extract_images_from_dom(page), urls[:2])


if __name__ == "__main__":
    unittest.main()
