# Copyright 2022 Thijs Raymakers
#
# Licensed under the EUPL, Version 1.2 or – as soon they
# will be approved by the European Commission - subsequent
# versions of the EUPL (the "Licence");
# You may not use this work except in compliance with the
# Licence.
# You may obtain a copy of the Licence at:
#
# https://joinup.ec.europa.eu/software/page/eupl
#
# Unless required by applicable law or agreed to in
# writing, software distributed under the Licence is
# distributed on an "AS IS" basis,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied.
# See the Licence for the specific language governing
# permissions and limitations under the Licence.

import asyncio
import logging
import re
import sys
import traceback
from hashlib import sha256
from io import BytesIO
from ipaddress import ip_address
from mimetypes import guess_type
from os import getenv
from pathlib import Path
from urllib.parse import quote, urlsplit
from weakref import WeakValueDictionary

import cloudscraper
from aiohttp import ClientSession, ClientTimeout, CookieJar, TCPConnector
from aiohttp.abc import AbstractResolver
from aiohttp.resolver import DefaultResolver
from feedgen.ext.base import BaseEntryExtension, BaseExtension
from feedgen.feed import FeedGenerator
from hypercorn.asyncio import serve
from hypercorn.config import Config
from lxml import etree
from PIL import Image
from quart import Quart, Response, render_template, request, send_from_directory

import podimo.cache as cache
from podimo.client import PodimoClient
from podimo.config import *
from podimo.utils import generateHeaders, randomHexId

PODCAST_NAMESPACE = "https://podcastindex.org/namespace/1.0"
ITUNES_NAMESPACE = "http://www.itunes.com/dtds/podcast-1.0.dtd"
HLS_FALLBACK_MP3 = "audio/dummy.mp3"
AUDIO_DIR = Path(__file__).resolve().parent / "audio"
HLS_FALLBACK_MP3_PATH = Path(__file__).resolve().parent / HLS_FALLBACK_MP3
MAX_ARTWORK_SIZE = 10 * 1024 * 1024
MAX_ARTWORK_DIMENSION = 3000
MAX_ARTWORK_PIXELS = 20_000_000
artwork_downloads = asyncio.Semaphore(2)
artwork_locks = WeakValueDictionary()


async def runInThread(function, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, function, *args)


def ensurePublicAddresses(addresses):
    if any(not ip_address(address["host"]).is_global for address in addresses):
        raise OSError("Artwork host resolves to a non-public address")
    return addresses


class PublicResolver(AbstractResolver):
    def __init__(self):
        self.resolver = DefaultResolver()

    async def resolve(self, host, port=0, family=0):
        addresses = await self.resolver.resolve(host, port, family)
        return ensurePublicAddresses(addresses)

    async def close(self):
        await self.resolver.close()


class PublicConnector(TCPConnector):
    async def _resolve_host(self, host, port, traces=None):
        addresses = await super()._resolve_host(host, port, traces)
        return ensurePublicAddresses(addresses)


class PodcastHlsExtension(BaseExtension):
    def __init__(self):
        self._itunes_explicit = None
        self._itunes_type = None
        self._podcast_block = None

    def itunes_explicit(self, value=None):
        if value is not None:
            self._itunes_explicit = value
        return self._itunes_explicit

    def itunes_type(self, value=None):
        if value is not None:
            self._itunes_type = value
        return self._itunes_type

    def podcast_block(self, value=None):
        if value is not None:
            self._podcast_block = value
        return self._podcast_block

    def extend_ns(self):
        return {"podcast": PODCAST_NAMESPACE}

    def extend_rss(self, feed):
        if self._itunes_explicit is not None:
            explicit = etree.SubElement(
                feed[0], etree.QName(ITUNES_NAMESPACE, "explicit")
            )
            explicit.text = self._itunes_explicit
        if self._itunes_type is not None:
            podcast_type = etree.SubElement(
                feed[0], etree.QName(ITUNES_NAMESPACE, "type")
            )
            podcast_type.text = self._itunes_type
        if self._podcast_block is not None:
            podcast_block = etree.SubElement(
                feed[0], etree.QName(PODCAST_NAMESPACE, "block")
            )
            podcast_block.text = self._podcast_block
        return feed


class PodcastHlsEntryExtension(BaseEntryExtension):
    def __init__(self):
        self._alternate_enclosures = []

    def alternate_enclosure(self, uri, type, length=0, title=None):
        self._alternate_enclosures.append(
            {
                "uri": uri,
                "type": type,
                "length": length,
                "title": title,
            }
        )

    def extend_rss(self, entry):
        for enclosure in self._alternate_enclosures:
            alternate = etree.SubElement(
                entry,
                etree.QName(PODCAST_NAMESPACE, "alternateEnclosure"),
                type=enclosure["type"],
                length=str(enclosure["length"]),
            )
            if enclosure["title"] is not None:
                alternate.set("title", enclosure["title"])
            etree.SubElement(
                alternate,
                etree.QName(PODCAST_NAMESPACE, "source"),
                uri=enclosure["uri"],
            )
        return entry


# Setup Quart, used for serving the web pages
app = Quart(__name__)
proxies = dict()

# Setup logging
logging.basicConfig(
    format="%(levelname)s | %(asctime)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    level=logging.INFO,
)


def example():
    return f"""Example
------------
Username: example@example.com
Password: this-is-my-password
Podcast ID: 12345-abcdef

The URL will be
https://example%40example.com:this-is-my-password@{PODIMO_HOSTNAME}/feed/12345-abcdef.xml

Note that the username and password should be URL encoded. This can be done with
a tool like https://gchq.github.io/CyberChef/#recipe=URL_Encode(true)
"""


@app.after_request
def allow_cors(response):
    response.headers.set("Access-Control-Allow-Origin", "*")
    response.headers.set("Access-Control-Allow-Methods", "GET, POST")
    response.headers.set("Cache-Control", "max-age=900")
    logging.debug(
        f"Incoming {request.method} request for '{request.url}' from User-Agent {request.user_agent} at {request.remote_addr}."
    )
    return response


def authenticate():
    return Response(
        f"""401 Unauthorized.
You need to login with the correct credentials for Podimo.

{example()}""",
        401,
        {
            "Content-Type": "text/plain",
            "WWW-Authenticate": "Basic realm='Podimo credentials'",
        },
    )


def initialize_client(
    username: str, password: str, region: str, locale: str
) -> PodimoClient:
    client = PodimoClient(username, password, region, locale)

    # Check if there is an authentication token already in memory. If so, use that one.
    # If it is expired, request a new token.
    key = client.key
    client.token = cache.getCacheEntry(key, cache.TOKENS)

    # Check if we previously created a cookie jar
    if key not in cache.cookie_jars:
        cache.cookie_jars[key] = CookieJar()
    client.cookie_jar = cache.cookie_jars[key]
    return client


async def check_auth(username, password, region, locale, scraper):
    try:
        client = initialize_client(username, password, region, locale)
        if client.token:
            return client

        await client.podimoLogin(scraper)
        cache.insertIntoTokenCache(client.key, client.token)
        return client

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        if DEBUG:
            traceback.print_exc()
    return None


podcast_id_pattern = re.compile(r"[0-9a-fA-F\-]+")


@app.route("/", methods=["POST", "GET"])
async def index():
    error = ""
    if request.method == "POST":
        form = await request.form
        email = form.get("email")
        password = form.get("password")
        podcast_id = form.get("podcast_id")
        region = form.get("region")
        locale = form.get("locale")

        if not LOCAL_CREDENTIALS:
            if email is None or email == "":
                error += "Email is required"
            if password is None or password == "":
                error += "Password is required"
        if podcast_id is None or podcast_id == "":
            error += "Podcast ID is required"
        elif podcast_id_pattern.fullmatch(podcast_id) is None:
            error += "Podcast ID is not valid"
        if region is None or region == "":
            error += "Region is required"
        elif region not in [region_code for (region_code, _) in REGIONS]:
            error += "Region is not valid"
        if locale is None or locale == "":
            error += "Locale is required"
        elif locale not in LOCALES:
            error += "Locale is not valid"

        if error == "":
            podcast_id = quote(str(podcast_id), safe="")
            region = quote(str(region), safe="")
            locale = quote(str(locale), safe="")

            if LOCAL_CREDENTIALS:
                url = f"{PODIMO_PROTOCOL}://{PODIMO_HOSTNAME}/feed/{podcast_id}.xml?{randomHexId(10)}&region={region}&locale={locale}"
            else:
                email = quote(str(email), safe="")
                comma = quote(",", safe="")
                username = f"{email}{comma}{region}{comma}{locale}"
                password = quote(str(password), safe="")
                url = f"{PODIMO_PROTOCOL}://{username}:{password}@{PODIMO_HOSTNAME}/feed/{podcast_id}.xml?{randomHexId(10)}&region={region}&locale={locale}"

            logging.debug(f"Created an URL: {url}.")
            return await render_template("feed_location.html", url=url)

    return await render_template(
        "index.html",
        error=error,
        locales=LOCALES,
        regions=REGIONS,
        need_credentials=not (LOCAL_CREDENTIALS),
    )


@app.errorhandler(404)
async def not_found(error):
    return Response(
        f"404 Not found.\n\n{example()}", 404, {"Content-Type": "text/plain"}
    )


@app.route("/audio/<string:filename>")
async def serve_audio(filename):
    if filename != "dummy.mp3" and not re.fullmatch(
        r"dummy-[0-9a-f]{64}\.mp3", filename
    ):
        return Response("Audio not found", 404, {})
    return await send_from_directory(AUDIO_DIR, "dummy.mp3")


@app.route("/feed/<string:podcast_id>.xml")
async def serve_basic_auth_feed(podcast_id):
    if LOCAL_CREDENTIALS:
        args = request.args
        region = args.get("region")
        locale = args.get("locale")
        return await serve_feed(
            PODIMO_EMAIL, PODIMO_PASSWORD, podcast_id, region, locale
        )
    else:
        auth = request.authorization
        if not auth:
            return authenticate()
        else:
            username, region, locale = split_username_region_locale(auth.username)
            return await serve_feed(username, auth.password, podcast_id, region, locale)


def artworkUrl(image_url):
    if not image_url:
        return None

    parsed_url = urlsplit(image_url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        logging.warning("Skipping invalid artwork URL")
        return None

    if parsed_url.path.lower().endswith((".jpg", ".jpeg", ".png")):
        return image_url

    key = cache.registerArtworkSource(image_url)
    return f"{PODIMO_PROTOCOL}://{PODIMO_HOSTNAME}/artwork/{key}.jpg"


def artworkToJpeg(data):
    with Image.open(BytesIO(data)) as source:
        if source.width * source.height > MAX_ARTWORK_PIXELS:
            raise ValueError("Artwork exceeds maximum pixel count")
        source.load()
        source.thumbnail(
            (MAX_ARTWORK_DIMENSION, MAX_ARTWORK_DIMENSION), Image.Resampling.LANCZOS
        )

        if source.mode in ("RGBA", "LA") or "transparency" in source.info:
            rgba = source.convert("RGBA")
            image = Image.new("RGB", rgba.size, "white")
            image.paste(rgba, mask=rgba.getchannel("A"))
        else:
            image = source.convert("RGB")

        output = BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True)
        return output.getvalue()


async def fetchArtwork(image_url):
    timeout = ClientTimeout(total=20)
    connector = PublicConnector(resolver=PublicResolver())
    async with ClientSession(timeout=timeout, connector=connector) as session:
        async with session.get(
            image_url, allow_redirects=True, max_redirects=5
        ) as response:
            response.raise_for_status()
            if response.content_length and response.content_length > MAX_ARTWORK_SIZE:
                raise ValueError("Artwork exceeds maximum download size")

            data = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                data.extend(chunk)
                if len(data) > MAX_ARTWORK_SIZE:
                    raise ValueError("Artwork exceeds maximum download size")
            return bytes(data)


@app.route("/artwork/<string:key>.jpg")
async def serve_artwork(key):
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        return Response("Artwork not found", 404, {})

    artwork = await runInThread(cache.getArtwork, key)
    if artwork is None and await runInThread(cache.getArtworkFailure, key):
        return Response("Something went wrong while fetching artwork", 502, {})

    if artwork is None:
        lock = artwork_locks.setdefault(key, asyncio.Lock())
        async with lock:
            artwork = await runInThread(cache.getArtwork, key)
            if artwork is None:
                if await runInThread(cache.getArtworkFailure, key):
                    return Response(
                        "Something went wrong while fetching artwork", 502, {}
                    )
                source_url = await runInThread(cache.getArtworkSource, key)
                if source_url is None:
                    return Response("Artwork not found", 404, {})

                try:
                    async with artwork_downloads:
                        source = await fetchArtwork(source_url)
                        artwork = await runInThread(artworkToJpeg, source)
                    await runInThread(cache.insertArtwork, key, artwork)
                except Exception as error:
                    await runInThread(cache.insertArtworkFailure, key)
                    logging.error(f"Error while fetching artwork {key}: {error}")
                    return Response(
                        "Something went wrong while fetching artwork", 502, {}
                    )

    return Response(artwork, mimetype="image/jpeg")


def split_username_region_locale(string):
    s = string.split(",")
    if len(s) == 3:
        return tuple(s)
    else:
        return (s[0], "nl", "nl-NL")


def token_key(username, password):
    key = sha256(
        b"~".join([username.encode("utf-8"), password.encode("utf-8")])
    ).hexdigest()
    return key


@app.route("/feed/<string:username>/<string:password>/<string:podcast_id>.xml")
async def serve_feed(username, password, podcast_id, region, locale):

    logging.debug(
        f"Feed request for podcast {podcast_id} from IP {request.remote_addr} with User-Agent:{request.user_agent}."
    )

    # Check if it is a valid podcast id string
    if podcast_id_pattern.fullmatch(podcast_id) is None:
        return Response("Invalid podcast id format", 400, {})

    if region not in [region_code for (region_code, _) in REGIONS]:
        return Response("Invalid region", 400, {})
    if locale not in LOCALES:
        return Response("Invalid locale", 400, {})

    # Return HTTP 410 GONE if the URL contains a blocked ID or podcast ID.
    if any(item in request.url for item in BLOCKED):
        logging.debug(f"Blocked! Podcast {podcast_id} is on local block list")
        return Response("Podcast is gone", 410, {})

    with cloudscraper.create_scraper() as scraper:
        scraper.proxies = proxies
        client = await check_auth(username, password, region, locale, scraper)
        if not client:
            return authenticate()

        # Get a list of valid podcasts
        try:
            podcasts = await podcastsToRss(
                podcast_id, await client.getPodcasts(podcast_id, scraper), locale
            )
        except Exception as e:
            exception = str(e)
            if "Podcast not found" in exception:
                return Response(
                    "Podcast not found. Are you sure you have the correct ID?", 404, {}
                )
            logging.error(f"Error while fetching podcasts: {exception}")
            return Response("Something went wrong while fetching the podcasts", 500, {})
        return Response(podcasts, mimetype="text/xml")


async def urlHeadInfo(session, id, url, locale):
    entry = cache.getHeadEntry(id)
    if entry:
        return entry

    logging.debug(f"HEAD request to {url}")
    async with session.head(
        url, allow_redirects=True, headers=generateHeaders(None, locale), timeout=3.05
    ) as response:
        content_length = 0
        content_type, _ = guess_type(url)
        if "content-length" in response.headers:
            content_length = response.headers["content-length"]
        if content_type is None and "content-type" in response.headers:
            content_type = response.headers["content-type"]
        else:
            content_type = "audio/mpeg"
        cache.insertIntoHeadCache(id, content_length, content_type)
        return (content_length, content_type)


def extract_audio_url(episode):
    duration = 0
    url = None
    if episode["audio"]:
        url = episode["audio"]["url"]
        duration = episode["audio"]["duration"]

    if url is None or url == "":
        if episode["streamMedia"]:
            url = episode["streamMedia"]["url"]
            duration = episode["streamMedia"]["duration"]

    # SJC
    # url = url.replace('&amp;', '&')
    # logging.info(f"Media URL: {url}")
    return url, duration


async def addFeedEntry(fg, episode, session, locale):
    episode_id = episode.get("id", "<unknown>")
    logging.debug(f"Starting feed entry for episode {episode_id}")

    fe = fg.add_entry()
    fe.guid(episode["id"])
    fe.title(episode["title"])
    fe.description(episode["description"])
    fe.pubDate(episode.get("publishDatetime", episode.get("datetime")))
    image = artworkUrl(episode.get("imageUrl"))
    if image:
        fe.podcast.itunes_image(image)

    url, duration = extract_audio_url(episode)
    if url is None:
        logging.warning(f"No audio URL found for episode {episode_id}")
        return

    logging.debug(
        f"Audio URL found for episode {episode_id}, duration={duration}, "
        f"is_hls={url.split('?', 1)[0].lower().endswith('.m3u8')}"
    )

    fe.podcast.itunes_duration(duration)
    content_length, content_type = await urlHeadInfo(
        session, episode["id"], url, locale
    )

    # Podimo returns HLS manifests as .m3u8 URLs.
    is_hls = url.split("?", 1)[0].lower().endswith(".m3u8")

    if is_hls:
        fallback_url = hlsFallbackMp3Url(episode_id)
        logging.debug(
            f"Adding fallback MP3 enclosure {fallback_url} and "
            f"HLS alternate enclosure "
            f"for episode {episode_id}"
        )
        fe.enclosure(
            fallback_url,
            hlsFallbackMp3Size(),
            "audio/mpeg",
        )
        fe.podcast_hls.alternate_enclosure(
            uri=url,
            type="application/x-mpegURL",
            length=content_length,
            title="HLS",
        )
    else:
        fe.enclosure(url, content_length, content_type)

    logging.debug(f"Finished feed entry for episode {episode_id}")


def chunks(x, n):
    for i in range(0, len(x), n):
        yield x[i : i + n]


def hlsFallbackMp3Size():
    if not HLS_FALLBACK_MP3_PATH.is_file():
        raise FileNotFoundError(
            f"HLS fallback MP3 not found: {HLS_FALLBACK_MP3_PATH}"
        )
    return str(HLS_FALLBACK_MP3_PATH.stat().st_size)


def hlsFallbackMp3Url(episode_id):
    episode_hash = sha256(str(episode_id).encode("utf-8")).hexdigest()
    return (
        f"{PODIMO_PROTOCOL}://{PODIMO_HOSTNAME}/audio/"
        f"dummy-{episode_hash}.mp3"
    )


def normalizeLanguageTag(language):
    if language and language.lower() == "nl-nl":
        return "nl-NL"
    return language


async def podcastsToRss(podcast_id, data, locale):
    logging.debug(f"podcastsToRss: START podcast_id={podcast_id}")

    try:
        logging.debug("podcastsToRss: creating FeedGenerator")
        fg = FeedGenerator()
        logging.debug("podcastsToRss: FeedGenerator created")

        logging.debug("podcastsToRss: loading podcast extension")
        fg.load_extension("podcast")
        logging.debug("podcastsToRss: podcast extension loaded")

        logging.debug("podcastsToRss: registering HLS extension")
        fg.register_extension(
            "podcast_hls",
            extension_class_feed=PodcastHlsExtension,
            extension_class_entry=PodcastHlsEntryExtension,
            atom=False,
            rss=True,
        )
        logging.debug("podcastsToRss: HLS extension registered")

        logging.debug("podcastsToRss: reading podcast data")
        podcast = data["podcast"]
        episodes = data["episodes"]

        logging.debug(
            f"podcastsToRss: podcast={podcast.get('title')!r}, "
            f"episodes={len(episodes)}"
        )

    except Exception:
        logging.exception(f"podcastsToRss: FAILED for podcast_id={podcast_id}")
        raise

    if len(episodes) > 0:
        last_episode = episodes[0]
        title = podcast["title"]
        if podcast["title"] is None:
            title = last_episode["podcastName"]
        fg.title(title)

        if podcast["description"]:
            fg.description(podcast["description"])
        else:
            fg.description(title)

        fg.link(href=f"https://podimo.com/shows/{podcast_id}", rel="alternate")

        image = podcast["images"]["coverImageUrl"]
        if image is None:
            image = last_episode["imageUrl"]
        image = artworkUrl(image)
        if image:
            fg.image(image)
            fg.podcast.itunes_image(image)
        fg.podcast.itunes_category("News")
        fg.podcast_hls.itunes_explicit("false")
        fg.podcast.itunes_owner(name="Example", email="you@example.com")
        fg.podcast_hls.itunes_type("episodic")

        language = podcast["language"]
        if language is None:
            language = locale
        fg.language(normalizeLanguageTag(language))

        artist = podcast["authorName"]
        if artist is None:
            artist = last_episode["artist"]
        fg.podcast.itunes_author(artist)

        if not PUBLIC_FEEDS:
            fg.podcast.itunes_block(True)
            fg.podcast_hls.podcast_block("yes")

    async with ClientSession() as session:
        for chunk in chunks(episodes, 5):
            await asyncio.gather(
                *[addFeedEntry(fg, episode, session, locale) for episode in chunk]
            )

    feed = fg.rss_str(pretty=True)
    return feed


async def spawn_web_server():
    config = Config()
    config.bind = [PODIMO_BIND_HOST]
    config.read_timeout = 60
    config.graceful_timeout = 5
    config.backlog = 1000
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    await serve(app, config)


async def main():
    if HTTP_PROXY:
        global proxies
        logging.info(
            f"Running with https proxy defined in environmental variable HTTP_PROXY: {HTTP_PROXY}"
        )
        proxies["https"] = HTTP_PROXY
    tasks = [spawn_web_server()]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    if DEBUG:
        logging.info(
            f"""Spawning server on {PODIMO_BIND_HOST}
Configuration:
- DEBUG: {DEBUG}
- LOCAL CREDENTIALS: {LOCAL_CREDENTIALS} ({PODIMO_EMAIL})
- PODIMO_HOSTNAME: {PODIMO_HOSTNAME}
- PODIMO_BIND_HOST: {PODIMO_BIND_HOST}
- PODIMO_PROTOCOL: {PODIMO_PROTOCOL}
- PUBLIC_FEEDS: {PUBLIC_FEEDS}
- HTTP_PROXY: {HTTP_PROXY}
- ZENROWS_API: {ZENROWS_API}
- SCRAPER_API: {SCRAPER_API}
- CACHE_DIR: {CACHE_DIR}
- STORE_TOKENS_ON_DISK: {STORE_TOKENS_ON_DISK}
- TOKEN_CACHE_TIME: {TOKEN_CACHE_TIME} sec
- PODCAST_CACHE_TIME: {PODCAST_CACHE_TIME} sec
- HEAD_CACHE_TIME: {HEAD_CACHE_TIME} sec
- BLOCKING: {BLOCKED}
"""
        )
    asyncio.run(main())
