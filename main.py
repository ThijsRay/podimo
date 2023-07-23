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
import os
import sys
from gql import Client, gql
from email.utils import parseaddr
from feedgen.feed import FeedGenerator
from gql.transport.aiohttp import AIOHTTPTransport
from random import choice, randint
from mimetypes import guess_type
from aiohttp import ClientSession
from quart import Quart, Response, render_template, request
from time import time
from hashlib import sha256
from hypercorn.config import Config
from hypercorn.asyncio import serve
from urllib.parse import quote

GRAPHQL_URL = "https://graphql.pdm-gateway.com/graphql"

HOST = os.environ.get("HOST", "podimo.thijs.sh")

BIND_HOST = os.environ.get("BIND_HOST", "127.0.0.1:12104")

# Setup Quart
app = Quart(__name__)

tokens = dict()
head_cache = dict()
url_cache = dict()
podcast_cache = dict()
podcast_cache_time = 15*60 # 15 minutes
token_timeout = 3600 * 24 * 5  # seconds = 5 days
head_cache_time = 60 * 60 * 24  # seconds = 1 day

locales = ['nl-NL', 'de-DE']
regions = ['nl', 'de']


def example():
    return f"""Example
------------
Username: example@example.com
Password: this-is-my-password
Podcast ID: 12345-abcdef

The URL will be
https://example%40example.com:this-is-my-password@{HOST}/feed/12345-abcdef.xml

Note that the username and password should be URL encoded. This can be done with
a tool like https://devpal.co/url-encode/
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

# Verify if it is actually an email address
def is_correct_email_address(username):
    return "@" in parseaddr(username)[1]


def token_key(username, password):
    key = sha256(
        b"~".join([username.encode("utf-8"), password.encode("utf-8")])
    ).hexdigest()
    return key


async def check_auth(username, password, region, locale):
    try:
        if len(username) == 0 or len(password) == 0:
            return False
        if len(username) > 256 or len(password) > 256:
            return False

        # Check if there is an authentication token already in memory. If so, use that one.
        # If it is expired, request a new token.
        key = token_key(username, password)
        if key in tokens:
            _, timestamp = tokens[key]
            if timestamp < time():
                del tokens[key]
            else:
                return True

        if is_correct_email_address(username):
            preauth_token = await getPreregisterToken(region, locale)
            prereg_id = await getOnboardingId(preauth_token, locale)
            token = await podimoLogin(username, password, preauth_token, prereg_id, locale)
            tokens[key] = (token, time() + token_timeout)
            return True

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
    return False

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
        elif region not in regions:
            error += "Region is not valid"
        if locale is None or locale == "":
            error += "Locale is required"
        elif locale not in locales:
            error += "Locale is not valid"

        if error == "":
            email = quote(email, safe="")
            region = quote(region, safe="")
            locale = quote(locale, safe="")

            comma = quote(',', safe="")
            username = f"{email}{comma}{region}{comma}{locale}"

            password = quote(password, safe="")
            podcast_id = quote(podcast_id, safe="")

            return await render_template("feed_location.html", 
                                         username=username,
                                         password=password,
                                         HOST=HOST,
                                         podcast_id=podcast_id
            )

    return await render_template("index.html", error=error, locales=locales, regions=regions)

@app.errorhandler(404)
async def not_found(error):
    return Response(
        f"404 Not found.\n\n{example()}", 401, {"Content-Type": "text/plain"}
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
        return (s[0], regions[0], locales[0])

@app.route("/feed/<string:username>/<string:password>/<string:podcast_id>.xml")
async def serve_feed(username, password, podcast_id):
    # Check if it is a valid podcast id string
    if podcast_id_pattern.fullmatch(podcast_id) is None:
        return Response("Invalid podcast id format", 400, {})

    username, region, locale = split_username_region_locale(username)
    if region not in regions:
        return Response("Invalid region", 400, {})
    if locale not in locales:
        return Response("Invalid locale", 400, {})

    # Authenticate
    if not await check_auth(username, password, region, locale):
        return authenticate()

    # Get a list of valid podcasts
    token, _ = tokens[token_key(username, password)]
    try:
        podcasts = await podcastsToRss(
            podcast_id, await getPodcasts(token, podcast_id, locale), locale
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


def randomHexId(length):
    string = []
    hex_chars = list("1234567890abcdef")
    for i in range(length):
        string.append(choice(hex_chars))
    return "".join(string)


def randomFlyerId():
    a = randint(1000000000000, 9999999999999)
    b = randint(1000000000000, 9999999999999)
    return str(f"{a}-{b}")


def generateHeaders(authorization, locale):
    headers = {
        'user-os': 'android',
        'user-agent': 'Podimo/2.45.1 build 566/Android 33',
        'user-version': '2.45.1',
        'user-locale': locale,
        "user-unique-id": randomHexId(16)
    }
    if authorization:
        headers["authorization"] = authorization
    return headers


# This gets the authentication token that is required for subsequent requests
# as an anonymous user
async def getPreregisterToken(region, locale):
    t = AIOHTTPTransport(url=GRAPHQL_URL, headers=generateHeaders(None, locale))
    async with Client(transport=t) as client:
        query = gql(
            """
                query AuthorizationPreregisterUser($locale: String!, $referenceUser: String, $countryCode: String, $appsFlyerId: String) {
                    tokenWithPreregisterUser(
                        locale: $locale
                        referenceUser: $referenceUser
                        countryCode: $countryCode
                        source: MOBILE
                        appsFlyerId: $appsFlyerId
                    ) {
                        token
                    }
                }
                """
        )
        variables = {"locale": locale, "countryCode": region, "appsFlyerId": randomFlyerId()}
        result = await client.execute(query, variable_values=variables)
        return result["tokenWithPreregisterUser"]["token"]


# Gets an "onboarding ID" that is used during login
async def getOnboardingId(preauth_token, locale):
    t = AIOHTTPTransport(url=GRAPHQL_URL, headers=generateHeaders(preauth_token, locale))
    async with Client(transport=t) as client:
        query = gql(
            """
                query OnboardingQuery {
                    userOnboardingFlow {
                        id
                    }
                }
                """
        )
        result = await client.execute(query)
        return result["userOnboardingFlow"]["id"]


async def podimoLogin(username, password, preauth_token, prereg_id, locale):
    t = AIOHTTPTransport(url=GRAPHQL_URL, headers=generateHeaders(preauth_token, locale))
    async with Client(transport=t, serialize_variables=True) as client:
        query = gql(
            """
                query AuthorizationAuthorize($email: String!, $password: String!, $locale: String!, $preregisterId: String) {
                    tokenWithCredentials(
                    email: $email
                    password: $password
                    locale: $locale
                    preregisterId: $preregisterId
                ) {
                    token
                  }
                }
                """
        )
        variables = {
            "email": username,
            "password": password,
            "locale": locale,
            "preregisterId": prereg_id,
        }

        result = await client.execute(query, variable_values=variables)
        return result["tokenWithCredentials"]["token"]


async def getPodcasts(token, podcast_id, locale):
    if podcast_id in podcast_cache:
        result, timestamp = podcast_cache[podcast_id]
        if timestamp >= time():
            print(f"Got podcast {podcast_id} from cache ({int(timestamp-time())} seconds left)", file=sys.stderr)
            return result

    t = AIOHTTPTransport(url=GRAPHQL_URL, headers=generateHeaders(token, locale))
    async with Client(transport=t, serialize_variables=True) as client:
        query = gql(
            """
        query ChannelEpisodesQuery($podcastId: String!, $limit: Int!, $offset: Int!, $sorting: PodcastEpisodeSorting) {
          episodes: podcastEpisodes(
            podcastId: $podcastId
            converted: true
            published: true
            limit: $limit
            offset: $offset
            sorting: $sorting
          ) {
            ...EpisodeBase
          }
          podcast: podcastById(podcastId: $podcastId) {
            title
            description
            webAddress
            authorName
            language
            images {
                coverImageUrl
            }
          }
        }

        fragment EpisodeBase on PodcastEpisode {
          id
          artist
          podcastName
          imageUrl
          description
          datetime
          title
          audio {
            url
            duration
          }
          streamMedia {
            duration
            url
          }
        }
        """
        )
        variables = {
            "podcastId": podcast_id,
            "limit": 500,
            "offset": 0,
            "sorting": "PUBLISHED_DESCENDING",
        }

        result = await client.execute(query, variable_values=variables)
        print(f"Fetched podcast {podcast_id} directly", file=sys.stderr)
        podcast_cache[podcast_id] = (result, time() + podcast_cache_time)
        return result


async def urlHeadInfo(session, id, url, locale):
    if id in head_cache:
        cl, ct, timestamp = head_cache[id]
        if timestamp >= time():
            return (cl, ct)

    async with session.head(
        url, allow_redirects=True, headers=generateHeaders(None, locale)
    ) as response:
        content_length = 0
        content_type, _ = guess_type(url)
        if "content-length" in response.headers:
            content_length = response.headers["content-length"]
        if content_type == None and "content-type" in response.headers:
            content_type = response.headers["content-type"]
        else:
            content_type = "audio/mpeg"
        head_cache[id] = (content_length, content_type, time() + head_cache_time)
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
        await asyncio.gather(
            *[addFeedEntry(fg, episode, session, locale) for episode in episodes]
        )

    feed = fg.rss_str(pretty=True)
    return feed


async def main():
    config = Config()
    config.bind = [BIND_HOST]
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    await serve(app, config)


if __name__ == "__main__":
    asyncio.run(main())
