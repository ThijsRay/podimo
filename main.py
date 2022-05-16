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
import urllib
import os
from gql import Client, gql
from email.utils import parseaddr
from feedgen.feed import FeedGenerator
from gql.transport.aiohttp import AIOHTTPTransport
from random import choice, randint
from json import loads
from mimetypes import guess_type
from aiohttp import ClientSession
from quart import Quart, Response, request, redirect
from functools import wraps
from time import time
from hashlib import sha256
from hypercorn.config import Config
from hypercorn.asyncio import serve

GRAPHQL_URL = "https://graphql.pdm-gateway.com/graphql"

HOST = os.environ.get("HOST", "podimo.thijs.sh")

BIND_HOST = os.environ.get("BIND_HOST", "127.0.0.1:12104")

# Setup Quart
app = Quart(__name__)

tokens = dict()
head_cache = dict()
token_timeout = 3600 * 24 * 5  # seconds = 5 days
head_cache_time = 60 * 60 * 24  # seconds = 1 day


def example():
    return f"""Example
------------
Username: example@example.com
Password: this-is-my-password
Podcast ID: 12345-abcdef

The URL will be
https://{HOST}/feed/example%40example.com/this-is-my-password/12345-abcdef.xml

Note that the username and password should be URL encoded. This can be done with
a tool like https://devpal.co/url-encode/
"""


def authenticate():
    return Response(
        f"""401 Unauthorized.
You need to login with the correct credentials for Podimo.

{example()}""",
        401,
        {"Content-Type": "text/plain"},
    )


# Verify if it is actually an email address
def is_correct_email_address(username):
    return "@" in parseaddr(username)[1]


def token_key(username, password):
    key = sha256(
        b"~".join([username.encode("utf-8"), password.encode("utf-8")])
    ).hexdigest()
    return key


async def check_auth(username, password):
    try:
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
            # Introduce a sleep when the auth token is not yet in memory. This discourages
            # using this server to do brute force attacks.
            await asyncio.sleep(5)
            preauth_token = await getPreregisterToken()
            prereg_id = await getOnboardingId(preauth_token)
            token = await podimoLogin(username, password, preauth_token, prereg_id)
            tokens[key] = (token, time() + token_timeout)
            return True
    except Exception as e:
        print(f"An error occurred: {e}")
    return False


@app.route("/", methods=["POST", "GET"])
async def index():
    error = ""
    if request.method == "POST":
        form = await request.form
        email = form.get("email")
        password = form.get("password")
        podcast_id = form.get("podcast_id")
        if email is None or email == "":
            error += "Email is required<br />"
        if password is None or password == "":
            error += "Password is required<br />"
        if podcast_id is None or podcast_id == "":
            error += "Podcast ID is required<br />"

        if error == "":
            email = urllib.parse.quote(email, safe="")
            password = urllib.parse.quote(password, safe="")
            podcast_id = urllib.parse.quote(podcast_id, safe="")
            return redirect(f"/feed/{email}/{password}/{podcast_id}.xml")

    form = f"""{error}<br />
<form action="/" method="post">
    <label for="email">Your Podimo email address</label><br />
    <input type="email" required placeholder="Podimo email address" name="email"><br />
    <br />
    <label for="password">Your Podimo password</label><br />
    <input type="password" required placeholder="Podimo password" name="password"><br />
    <br />
    <label for="podcast_id">Podcast ID (https://podimo.com/nl/shows/<b>THIS IS THE ID</b>)</label><br />
    <input placeholder="Podcast ID" required name="podcast_id"><br />
    <br />
    <input type="submit" value="Create RSS URL (may take some time)" />
</form>
    """
    return Response(form)


@app.errorhandler(404)
async def not_found(error):
    return Response(
        f"404 Not found.\n\n{example()}", 401, {"Content-Type": "text/plain"}
    )


id_pattern = re.compile(r"[0-9a-fA-F\-]+")


@app.route("/feed/<string:username>/<string:password>/<string:podcast_id>.xml")
async def serve_feed(username, password, podcast_id):
    # Authenticate
    if not await check_auth(username, password):
        return authenticate()

    # Check if it is a valid podcast id string
    if id_pattern.fullmatch(podcast_id) is None:
        return Response("Invalid podcast id format", 404, {})

    # Get a list of valid podcasts
    token, _ = tokens[token_key(username, password)]
    try:
        podcasts = await podcastsToRss(
            username, password, podcast_id, await getPodcasts(token, podcast_id)
        )
    except Exception as e:
        exception = str(e)
        if "Podcast not found" in exception:
            return Response(
                "Podcast not found. Are you sure you have the correct ID?", 404, {}
            )
        print(f"Error while fetching podcasts: {exception}")
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


def generateHeaders(authorization):
    headers = {
        #'user-os': 'android',
        #'user-agent': 'okhttp/4.9.1',
        #'user-version': '2.15.3',
        #'user-locale': 'nl-NL',
        "user-unique-id": randomHexId(16)
    }
    if authorization:
        headers["authorization"] = authorization
    return headers


async def getPreregisterToken():
    t = AIOHTTPTransport(url=GRAPHQL_URL, headers=generateHeaders(None))
    async with Client(transport=t) as client:
        query = gql(
            """
                query AuthorizationPreregisterUser($locale: String!, $referenceUser: String, $region: String, $appsFlyerId: String) {
                    tokenWithPreregisterUser(
                        locale: $locale
                        referenceUser: $referenceUser
                        region: $region
                        source: WEB
                        appsFlyerId: $appsFlyerId
                    ) {
                        token
                    }
                }
                """
        )
        variables = {"locale": "nl-NL", "region": "nl", "appsFlyerId": randomFlyerId()}
        result = await client.execute(query, variable_values=variables)
        return result["tokenWithPreregisterUser"]["token"]


async def getOnboardingId(preauth_token):
    t = AIOHTTPTransport(url=GRAPHQL_URL, headers=generateHeaders(preauth_token))
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


async def podimoLogin(username, password, preauth_token, prereg_id):
    t = AIOHTTPTransport(url=GRAPHQL_URL, headers=generateHeaders(preauth_token))
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
            "locale": "nl-NL",
            "preregisterId": prereg_id,
        }

        result = await client.execute(query, variable_values=variables)
        return result["tokenWithCredentials"]["token"]


async def getPodcasts(token, podcast_id):
    t = AIOHTTPTransport(url=GRAPHQL_URL, headers=generateHeaders(token))
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
          description
          datetime
          title
          streamMedia {
            duration
            url
          }
        }
        """
        )
        variables = {
            "podcastId": podcast_id,
            "limit": 100,
            "offset": 0,
            "sorting": "PUBLISHED_DESCENDING",
        }

        result = await client.execute(query, variable_values=variables)
        return result


async def urlHeadInfo(session, url):
    if url in head_cache:
        cl, ct, timestamp = head_cache[url]
        if timestamp >= time():
            return (cl, ct)

    async with session.head(
        url, allow_redirects=True, headers=generateHeaders(None)
    ) as response:
        content_length = 0
        content_type, _ = guess_type(url)
        if "content-length" in response.headers:
            content_length = response.headers["content-length"]
        if content_type == None and "content-type" in response.headers:
            content_type = response.headers["content-type"]
        else:
            content_type = "audio/mpeg"
        head_cache[url] = (content_length, content_type, time() + head_cache_time)
        return (content_length, content_type)


async def addFeedEntry(fg, episode, session):
    fe = fg.add_entry()
    fe.title(episode["title"])
    fe.podcast.itunes_duration(episode["streamMedia"]["duration"])
    fe.description(episode["description"])
    fe.pubDate(episode["datetime"])

    url = episode["streamMedia"]["url"]
    content_length, content_type = await urlHeadInfo(session, url)
    fe.enclosure(url, content_length, content_type)


async def podcastsToRss(username, password, podcast_id, data):
    fg = FeedGenerator()
    fg.load_extension("podcast")

    podcast = data["podcast"]
    fg.title(podcast["title"])
    fg.description(podcast["description"])
    fg.link(href=f"https://podimo.com/shows/{podcast_id}", rel="alternate")
    fg.image(podcast["images"]["coverImageUrl"])
    fg.language(podcast["language"])
    fg.author({"name": podcast["authorName"]})
    episodes = data["episodes"]

    async with ClientSession() as session:
        await asyncio.gather(
            *[addFeedEntry(fg, episode, session) for episode in episodes]
        )

    feed = fg.rss_str(pretty=True)
    return feed


async def main():
    config = Config()
    config.bind = [BIND_HOST]
    await serve(app, config)


if __name__ == "__main__":
    asyncio.run(main())
