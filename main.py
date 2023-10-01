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
import re
import sys
from os import getenv
from podimo.client import PodimoClient
from feedgen.feed import FeedGenerator
from mimetypes import guess_type
from aiohttp import ClientSession, CookieJar
from quart import Quart, Response, render_template, request
from hashlib import sha256
from hypercorn.config import Config
from hypercorn.asyncio import serve
from urllib.parse import quote
from podimo.config import *
from podimo.utils import generateHeaders, randomHexId
import podimo.cache as cache

# Setup Quart, used for serving the web pages
app = Quart(__name__)

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
    response.headers.set('Access-Control-Allow-Origin', '*')
    response.headers.set('Access-Control-Allow-Methods', 'GET, POST')
    response.headers.set('Cache-Control', 'max-age=900')
    return response

def authenticate():
    return Response(
        f"""401 Unauthorized.
You need to login with the correct credentials for Podimo.

{example()}""",
        401,
        {
            "Content-Type": "text/plain",
            "WWW-Authenticate": "Basic realm='Podimo credentials'"
        },
    )

def initialize_client(username: str, password: str, region: str, locale: str) -> PodimoClient:
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

async def check_auth(username, password, region, locale):
    try:
        client = initialize_client(username, password, region, locale)
        if client.token:
            return client

        await client.podimoLogin()
        cache.insertIntoTokenCache(client.key, client.token)
        return client

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
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
            email = quote(str(email), safe="")
            region = quote(str(region), safe="")
            locale = quote(str(locale), safe="")

            comma = quote(',', safe="")
            username = f"{email}{comma}{region}{comma}{locale}"

            password = quote(str(password), safe="")
            podcast_id = quote(str(podcast_id), safe="")

            return await render_template("feed_location.html", 
                                         username=username,
                                         password=password,
                                         HOSTNAME=PODIMO_HOSTNAME,
                                         PROTOCOL=PODIMO_PROTOCOL,
                                         podcast_id=podcast_id,
                                         random_id=randomHexId(10)
            )

    return await render_template("index.html", error=error, locales=LOCALES, regions=REGIONS)


@app.errorhandler(404)
async def not_found(error):
    return Response(
        f"404 Not found.\n\n{example()}", 404, {"Content-Type": "text/plain"}
    )


@app.route("/feed/<string:podcast_id>.xml")
async def serve_basic_auth_feed(podcast_id):
    auth = request.authorization
    if not auth:
        return authenticate()
    else:
        return await serve_feed(auth.username, auth.password, podcast_id)


def split_username_region_locale(string):
    s = string.split(',')
    if len(s) == 3:
        return tuple(s)
    else:
        return (s[0], 'nl', 'nl-NL')


def token_key(username, password):
    key = sha256(
        b"~".join([username.encode("utf-8"), password.encode("utf-8")])
    ).hexdigest()
    return key


@app.route("/feed/<string:username>/<string:password>/<string:podcast_id>.xml")
async def serve_feed(username, password, podcast_id):
    # Check if it is a valid podcast id string
    if podcast_id_pattern.fullmatch(podcast_id) is None:
        return Response("Invalid podcast id format", 400, {})

    username, region, locale = split_username_region_locale(username)
    if region not in [region_code for (region_code, _) in REGIONS]:
        return Response("Invalid region", 400, {})
    if locale not in LOCALES:
        return Response("Invalid locale", 400, {})

    client = await check_auth(username, password, region, locale)
    if not client:
        return authenticate()

    # Get a list of valid podcasts
    try:
        podcasts = await podcastsToRss(
            podcast_id, await client.getPodcasts(podcast_id), locale
        )
    except Exception as e:
        exception = str(e)
        if "Podcast not found" in exception:
            return Response(
                "Podcast not found. Are you sure you have the correct ID?", 404, {}
            )
        print(f"Error while fetching podcasts: {exception}", file=sys.stderr)
        return Response("Something went wrong while fetching the podcasts", 500, {})
    return Response(podcasts, mimetype="text/xml")


async def urlHeadInfo(session, id, url, locale):
    entry = cache.getHeadEntry(id)
    if entry:
        return entry

    print("HEAD request to", url, file=sys.stderr)
    async with session.head(
        url, allow_redirects=True, headers=generateHeaders(None, locale), timeout=3.05
    ) as response:
        content_length = 0
        content_type, _ = guess_type(url)
        if "content-length" in response.headers:
            content_length = response.headers["content-length"]
        if content_type == None and "content-type" in response.headers:
            content_type = response.headers["content-type"]
        else:
            content_type = "audio/mpeg"
        cache.insertIntoHeadCache(id, content_length, content_type)
        return (content_length, content_type)


def extract_audio_url(episode):
    duration = 0
    url = None
    if episode['audio']:
        url = episode['audio']['url']
        duration = episode['audio']['duration']

    if url is None or url == "":
        if episode["streamMedia"]:
            url = episode["streamMedia"]["url"]
            duration = episode["streamMedia"]["duration"]
            if "hls-media" in url and "/main.m3u8" in url:
                url = url.replace("hls-media", "audios")
                url = url.replace("/main.m3u8", ".mp3")

    return url, duration


async def addFeedEntry(fg, episode, session, locale):
    fe = fg.add_entry()
    fe.title(episode["title"])
    fe.description(episode["description"])
    fe.pubDate(episode["datetime"])

    url, duration = extract_audio_url(episode)
    if url is None:
        return 

    fe.podcast.itunes_duration(duration)
    content_length, content_type = await urlHeadInfo(session, episode['id'], url, locale)
    fe.enclosure(url, content_length, content_type)

def chunks(x, n):
    for i in range(0, len(x), n):
        yield x[i:i + n]

async def podcastsToRss(podcast_id, data, locale):
    fg = FeedGenerator()
    fg.load_extension("podcast")

    podcast = data["podcast"]
    episodes = data["episodes"]

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
            image = last_episode['imageUrl']
        fg.image(image)

        language = podcast["language"]
        if language is None:
            language = locale
        fg.language(language)

        artist = podcast["authorName"]
        if artist is None:
            artist = last_episode["artist"]
        fg.author({"name": artist})

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
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    await serve(app, config)

async def main():
    tasks = [spawn_web_server()]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    print(f"Spawning server on {PODIMO_BIND_HOST}")
    asyncio.run(main())
