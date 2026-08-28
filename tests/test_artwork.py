import asyncio
import unittest
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, patch

from lxml import etree
from PIL import Image, features

import main


class ArtworkUrlTests(unittest.TestCase):
    def test_supported_image_url_is_used_directly(self):
        url = "https://cdn.example.com/episode.jpg"

        self.assertEqual(main.artworkUrl(url), url)

    @patch("main.cache.registerArtworkSource")
    def test_supported_image_url_with_query_is_used_directly(self, register_artwork):
        url = "https://cdn.example.com/episode.JPEG?token=abc"

        self.assertEqual(main.artworkUrl(url), url)
        register_artwork.assert_not_called()

    @patch("main.cache.registerArtworkSource", return_value="a" * 64)
    def test_webp_image_uses_local_jpeg_url(self, register_artwork):
        url = "https://cdn.example.com/episode.webp"

        result = main.artworkUrl(url)

        register_artwork.assert_called_once_with(url)
        self.assertEqual(
            result,
            f"{main.PODIMO_PROTOCOL}://{main.PODIMO_HOSTNAME}/artwork/{'a' * 64}.jpg",
        )

    @patch("main.cache.registerArtworkSource", return_value="b" * 64)
    def test_extensionless_image_uses_local_jpeg_url(self, register_artwork):
        result = main.artworkUrl("https://cdn.example.com/image/123")

        self.assertTrue(result.endswith(f"/{'b' * 64}.jpg"))
        register_artwork.assert_called_once()

    def test_invalid_image_url_is_omitted(self):
        self.assertIsNone(main.artworkUrl("file:///etc/passwd"))
        self.assertIsNone(main.artworkUrl(None))


class ArtworkConversionTests(unittest.TestCase):
    @unittest.skipUnless(features.check("webp"), "Pillow has no WebP support")
    def test_webp_is_converted_to_rgb_jpeg(self):
        source = BytesIO()
        Image.new("RGBA", (32, 24), (255, 0, 0, 128)).save(source, format="WEBP")

        result = main.artworkToJpeg(source.getvalue())

        with Image.open(BytesIO(result)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (32, 24))


class ArtworkRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_artwork_returns_404(self):
        client = main.app.test_client()

        response = await client.get(f"/artwork/{'c' * 64}.jpg")

        self.assertEqual(response.status_code, 404)

    @patch("main.cache.getArtwork", return_value=b"jpeg-data")
    async def test_cached_artwork_is_served_as_jpeg(self, get_artwork):
        client = main.app.test_client()

        response = await client.get(f"/artwork/{'d' * 64}.jpg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "image/jpeg")
        self.assertEqual(await response.get_data(), b"jpeg-data")

    @patch("main.cache.insertArtwork")
    @patch("main.cache.getArtworkFailure", return_value=None)
    @patch(
        "main.cache.getArtworkSource", return_value="https://cdn.example.com/image.webp"
    )
    @patch("main.cache.getArtwork", return_value=None)
    @patch("main.fetchArtwork", new_callable=AsyncMock)
    async def test_uncached_artwork_is_converted_and_cached(
        self, fetch_artwork, get_artwork, get_source, get_failure, insert_artwork
    ):
        source = BytesIO()
        Image.new("RGB", (16, 16), "blue").save(source, format="PNG")
        fetch_artwork.return_value = source.getvalue()
        client = main.app.test_client()

        response = await client.get(f"/artwork/{'e' * 64}.jpg")

        self.assertEqual(response.status_code, 200)
        result = await response.get_data()
        self.assertTrue(result.startswith(b"\xff\xd8"))
        insert_artwork.assert_called_once_with("e" * 64, result)


class AudioRouteTests(unittest.IsolatedAsyncioTestCase):
    @patch("main.send_from_directory", new_callable=AsyncMock)
    async def test_audio_file_is_served_from_audio_directory(self, send_file):
        send_file.return_value = main.Response(b"mp3-data", mimetype="audio/mpeg")
        client = main.app.test_client()

        response = await client.get("/audio/dummy.mp3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "audio/mpeg")
        self.assertEqual(await response.get_data(), b"mp3-data")
        send_file.assert_awaited_once_with(main.AUDIO_DIR, "dummy.mp3")

    @patch("main.send_from_directory", new_callable=AsyncMock)
    async def test_unique_audio_url_serves_shared_dummy_file(self, send_file):
        send_file.return_value = main.Response(b"mp3-data", mimetype="audio/mpeg")
        client = main.app.test_client()
        filename = main.hlsFallbackMp3Url("episode-1").rsplit("/", 1)[-1]

        response = await client.get(f"/audio/{filename}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(await response.get_data(), b"mp3-data")
        send_file.assert_awaited_once_with(main.AUDIO_DIR, "dummy.mp3")

    @patch("main.send_from_directory", new_callable=AsyncMock)
    async def test_unknown_audio_filename_returns_404(self, send_file):
        client = main.app.test_client()

        response = await client.get("/audio/not-an-enclosure.mp3")

        self.assertEqual(response.status_code, 404)
        send_file.assert_not_awaited()


class HlsFallbackTests(unittest.TestCase):
    def test_url_is_stable_and_unique_per_episode(self):
        first = main.hlsFallbackMp3Url("episode-1")

        self.assertEqual(first, main.hlsFallbackMp3Url("episode-1"))
        self.assertNotEqual(first, main.hlsFallbackMp3Url("episode-2"))
        self.assertRegex(first, r"/audio/dummy-[0-9a-f]{64}\.mp3$")

    @patch("main.HLS_FALLBACK_MP3_PATH")
    def test_size_is_read_from_file(self, fallback_path):
        fallback_path.is_file.return_value = True
        fallback_path.stat.return_value.st_size = 187288

        self.assertEqual(main.hlsFallbackMp3Size(), "187288")

    @patch("main.HLS_FALLBACK_MP3_PATH")
    def test_missing_file_raises_clear_error(self, fallback_path):
        fallback_path.is_file.return_value = False

        with self.assertRaisesRegex(FileNotFoundError, "fallback MP3 not found"):
            main.hlsFallbackMp3Size()


class PublicResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_connector_rejects_literal_private_address(self):
        connector = main.PublicConnector(resolver=main.PublicResolver())
        self.addAsyncCleanup(connector.close)

        with self.assertRaisesRegex(OSError, "non-public"):
            await connector._resolve_host("127.0.0.1", 80)

    async def test_private_address_is_rejected(self):
        resolver = main.PublicResolver()
        resolver.resolver.resolve = AsyncMock(return_value=[{"host": "127.0.0.1"}])

        with self.assertRaisesRegex(OSError, "non-public"):
            await resolver.resolve("example.com", 443)

    async def test_public_address_is_returned(self):
        resolver = main.PublicResolver()
        addresses = [{"host": "93.184.216.34"}]
        resolver.resolver.resolve = AsyncMock(return_value=addresses)

        self.assertEqual(await resolver.resolve("example.com", 443), addresses)


class FeedArtworkTests(unittest.IsolatedAsyncioTestCase):
    @patch("main.PUBLIC_FEEDS", False)
    @patch(
        "main.urlHeadInfo", new_callable=AsyncMock, return_value=("123", "audio/mpeg")
    )
    @patch("main.cache.registerArtworkSource", return_value="f" * 64)
    async def test_webp_artwork_does_not_prevent_feed_generation(
        self, register_artwork, url_head_info
    ):
        data = {
            "podcast": {
                "title": "Test podcast",
                "description": "Description",
                "images": {"coverImageUrl": "https://cdn.example.com/show.webp"},
                "language": "nl-NL",
                "authorName": "Author",
            },
            "episodes": [
                {
                    "id": "episode-1",
                    "title": "Episode one",
                    "description": "Episode description",
                    "publishDatetime": datetime(2026, 7, 22, tzinfo=timezone.utc),
                    "imageUrl": "https://cdn.example.com/episode.webp",
                    "audio": {
                        "url": "https://cdn.example.com/episode.mp3",
                        "duration": 60,
                    },
                    "streamMedia": None,
                    "podcastName": "Test podcast",
                    "artist": "Author",
                }
            ],
        }

        feed = await main.podcastsToRss("podcast-id", data, "nl-NL")
        feed_text = feed.decode("utf-8")

        self.assertIn("Episode one", feed_text)
        self.assertIn(f"/artwork/{'f' * 64}.jpg", feed_text)
        self.assertNotIn(".webp", feed_text)
        self.assertIn('<itunes:category text="News"', feed_text)
        self.assertIn(
            f'<itunes:image href="{main.PODIMO_PROTOCOL}://{main.PODIMO_HOSTNAME}'
            f'/artwork/{"f" * 64}.jpg"',
            feed_text,
        )
        self.assertIn("<itunes:explicit>false</itunes:explicit>", feed_text)
        self.assertIn("<itunes:name>Example</itunes:name>", feed_text)
        self.assertIn("<itunes:email>you@example.com</itunes:email>", feed_text)
        self.assertIn("<itunes:type>episodic</itunes:type>", feed_text)
        self.assertIn("<itunes:block>yes</itunes:block>", feed_text)
        self.assertIn("<podcast:block>yes</podcast:block>", feed_text)
        url_head_info.assert_awaited_once()

    @patch("main.PUBLIC_FEEDS", True)
    @patch(
        "main.urlHeadInfo", new_callable=AsyncMock, return_value=("123", "audio/mpeg")
    )
    async def test_public_feed_omits_block_tags(self, url_head_info):
        data = {
            "podcast": {
                "title": "Test podcast",
                "description": "Description",
                "images": {"coverImageUrl": "https://cdn.example.com/show.jpg"},
                "language": "nl-nl",
                "authorName": "Author",
            },
            "episodes": [
                {
                    "id": "episode-1",
                    "title": "Episode one",
                    "description": "Episode description",
                    "publishDatetime": datetime(2026, 7, 22, tzinfo=timezone.utc),
                    "imageUrl": "https://cdn.example.com/episode.jpg",
                    "audio": {
                        "url": "https://cdn.example.com/episode.mp3",
                        "duration": 60,
                    },
                    "streamMedia": None,
                    "podcastName": "Test podcast",
                    "artist": "Author",
                }
            ],
        }

        feed = await main.podcastsToRss("podcast-id", data, "nl-NL")
        feed_text = feed.decode("utf-8")

        self.assertIn("<language>nl-NL</language>", feed_text)
        self.assertNotIn("<itunes:block>", feed_text)
        self.assertNotIn("<podcast:block>", feed_text)
        url_head_info.assert_awaited_once()

    @patch(
        "main.urlHeadInfo",
        new_callable=AsyncMock,
        return_value=("123", "application/octet-stream"),
    )
    @patch("main.hlsFallbackMp3Size", return_value="187288")
    async def test_hls_uses_standard_and_alternate_enclosures(
        self, fallback_size, url_head_info
    ):
        data = {
            "podcast": {
                "title": "Test podcast",
                "description": "Description",
                "images": {"coverImageUrl": "https://cdn.example.com/show.jpg"},
                "language": "nl-NL",
                "authorName": "Author",
            },
            "episodes": [
                {
                    "id": "episode-hls",
                    "title": "HLS episode",
                    "description": "Episode description",
                    "publishDatetime": datetime(2026, 7, 22, tzinfo=timezone.utc),
                    "imageUrl": "https://cdn.example.com/episode.jpg",
                    "audio": None,
                    "streamMedia": {
                        "url": "https://cdn.example.com/main.m3u8?token=abc",
                        "duration": 60,
                    },
                    "podcastName": "Test podcast",
                    "artist": "Author",
                }
            ],
        }

        feed = await main.podcastsToRss("podcast-id", data, "nl-NL")
        feed_xml = etree.fromstring(feed)
        item = feed_xml.find("./channel/item")

        enclosure = item.find("enclosure")
        self.assertIsNotNone(enclosure)
        self.assertEqual(
            enclosure.get("url"),
            main.hlsFallbackMp3Url("episode-hls"),
        )
        self.assertEqual(enclosure.get("length"), "187288")
        self.assertEqual(enclosure.get("type"), "audio/mpeg")
        alternate = item.find(f"{{{main.PODCAST_NAMESPACE}}}alternateEnclosure")
        self.assertIsNotNone(alternate)
        self.assertEqual(alternate.get("type"), "application/x-mpegURL")
        source = alternate.find(f"{{{main.PODCAST_NAMESPACE}}}source")
        self.assertEqual(
            source.get("uri"), "https://cdn.example.com/main.m3u8?token=abc"
        )
        fallback_size.assert_called_once_with()
        url_head_info.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
