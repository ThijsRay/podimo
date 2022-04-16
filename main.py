from gql import Client, gql
from email.utils import parseaddr
from feedgen.feed import FeedGenerator
from gql.transport.requests import RequestsHTTPTransport
from random import choice, randint
from json import loads
from mimetypes import guess_type
from requests import head
from flask import Flask, request, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
from time import time
from hashlib import sha256
from waitress import serve
import re

GRAPHQL_URL = "https://graphql.pdm-gateway.com/graphql"

HOST = "podimo.thijs.sh"

# Setup flask
app = Flask(__name__)
# Setup a rate limiter
limiter = Limiter(app, key_func=get_remote_address)

tokens = dict()
feeds = dict()
token_timeout = 3600 * 24 * 5 # seconds = 5 days
feed_cache_time = 60 * 15 # seconds = 15 minutes

def example():
    return f"Example\n------------\nUsername: example@example.com\nPassword: this-is-my-password\nPodcast ID: 12345-abcdef\n\nThe URL will be\nhttps://{HOST}/feed/example%40example.com/this-is-my-password/12345-abcdef.xml\n\nNote that the username and password should be URL encoded. This can be done with\na tool like https://devpal.co/url-encode/\n" 

def authenticate():
    return Response(f"401 Unauthorized.\nYou need to login with the correct credentials for Podimo.\n\n{example()}", 401,
            {'Content-Type': 'text/plain'})

# Verify if it is actually an email address
def is_correct_email_address(username):
    return '@' in parseaddr(username)[1]

def token_key(username, password):
    key = sha256(b'~'.join([username.encode('utf-8'), password.encode('utf-8')])).hexdigest()
    return key


def check_auth(username, password):
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
            preauth_token = getPreregisterToken()
            prereg_id = getOnboardingId(preauth_token)
            token = podimoLogin(username, password, preauth_token, prereg_id)

            tokens[key] = (token, time() + token_timeout)
            return True
    except Exception as e:
        app.logger.debug(f"An error occurred: {e}")
    return False

@app.errorhandler(404)
def not_found(error):
    return Response(f"404 Not found.\n\n{example()}", 401, {'Content-Type': 'text/plain'})

id_pattern = re.compile('[0-9a-fA-F\-]+')
@app.route('/feed/<username>/<password>/<podcast_id>.xml')
@limiter.limit("3/minute")
def serve_feed(username, password, podcast_id):
    # Authenticate
    username = str(username)
    password = str(password)
    if not check_auth(username, password):
        return authenticate()
    # Check if it is a valid podcast id string
    podcast_id = str(podcast_id)
    if id_pattern.fullmatch(podcast_id) is None:
        return Response("Invalid podcast id format", 404, {})

    # Get a list of valid podcasts
    token, _ = tokens[token_key(username, password)]
    try:
        podcasts = podcastsToRss(username, password, podcast_id, getPodcasts(token, podcast_id))
    except Exception as e:
        exception = str(e)
        if "Podcast not found" in exception:
            return Response("Podcast not found. Are you sure you have the correct ID?", 404, {})
        print(f"Error while fetching podcasts: {exception}")
        return Response("Something went wrong while fetching the podcasts", 500, {})
    return Response(podcasts, mimetype='text/xml')

def randomHexId(length):
    string = []
    hex_chars = list('1234567890abcdef')
    for i in range(length):
        string.append(choice(hex_chars))
    return "".join(string)

def randomFlyerId():
    a = randint(1000000000000, 9999999999999)
    b = randint(1000000000000, 9999999999999)
    return str(f"{a}-{b}")

def generateHeaders(authorization):
    headers={
        #'user-os': 'android',
        #'user-agent': 'okhttp/4.9.1',
        #'user-version': '2.15.3',
        #'user-locale': 'nl-NL',
        'user-unique-id': randomHexId(16)
    }
    if authorization:
        headers['authorization'] = authorization
    return headers

def getPreregisterToken():
    t = RequestsHTTPTransport(
        url=GRAPHQL_URL,
        verify=True,
        retries=3,
        headers=generateHeaders(None)
    )
    client = Client(transport=t)
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

    result = client.execute(query, variable_values=variables)
    return result['tokenWithPreregisterUser']['token']

def getOnboardingId(preauth_token):
    t = RequestsHTTPTransport(
        url=GRAPHQL_URL,
        verify=True,
        retries=3,
        headers=generateHeaders(preauth_token)
    )
    client = Client(transport=t)
    query = gql(
            """
            query OnboardingQuery {
                userOnboardingFlow {
                    id
                }
            }
            """
    )
    result = client.execute(query)
    return result['userOnboardingFlow']['id']

def podimoLogin(username, password, preauth_token, prereg_id):
    t = RequestsHTTPTransport(
        url=GRAPHQL_URL,
        verify=True,
        retries=3,
        headers=generateHeaders(preauth_token)
    )
    client = Client(transport=t, serialize_variables=True)
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
    variables = {"email": username, "password": password, "locale": "nl-NL", "preregisterId": prereg_id}

    result = client.execute(query, variable_values=variables)
    return result['tokenWithCredentials']['token']

def getPodcasts(token, podcast_id):
    t = RequestsHTTPTransport(
        url=GRAPHQL_URL,
        verify=True,
        retries=3,
        headers=generateHeaders(token)
    )
    client = Client(transport=t, serialize_variables=True)
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
        "sorting": "PUBLISHED_DESCENDING"
    }

    result = client.execute(query, variable_values=variables)
    return result

def contentLengthOfUrl(username, password, url):
    token, _ = tokens[token_key(username, password)]
    return head(url, headers=generateHeaders(token)).headers['content-length']

def podcastsToRss(username, password, podcast_id, data):
    key = (token_key(username, password), podcast_id)
    if key in feeds:
        feed, timestamp = feeds[key]
        if timestamp < time():
            del feeds[key]
        else:
            return feed
    else:
        fg = FeedGenerator()
        fg.load_extension('podcast')

        podcast = data['podcast']
        fg.title(podcast['title'])
        fg.description(podcast['description'])
        fg.link(href=podcast['webAddress'], rel='alternate')
        fg.image(podcast['images']['coverImageUrl'])
        fg.language(podcast['language'])
        fg.author({'name': podcast['authorName']})
        episodes = data['episodes']
        for episode in episodes:
            fe = fg.add_entry()
            fe.title(episode['title'])
            url = episode['streamMedia']['url']
            mt, enc = guess_type(url)
            fe.enclosure(url, contentLengthOfUrl(username, password, url), mt)
            fe.podcast.itunes_duration(episode['streamMedia']['duration'])
            fe.description(episode['description'])
            fe.pubDate(episode['datetime'])

        feed = fg.rss_str(pretty=True)
        expiry = time() + feed_cache_time
        feeds[key] = (feed, expiry)
        return feed

if __name__ == "__main__":
    serve(app, host="127.0.0.1", port=12104)
