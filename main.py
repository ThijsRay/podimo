from gql import Client, gql
from feedgen.feed import FeedGenerator
from gql.transport.requests import RequestsHTTPTransport
from random import choice, randint
from json import loads
from mimetypes import guess_type
from requests import head

GRAPHQL_URL = "https://graphql.pdm-gateway.com/graphql"
EMAIL = None
PASSWORD = None
PODCAST_ID = "99aa420b-14d0-4ffc-8e79-a55ed8f793e4"

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
        'user-os': 'android',
        'user-agent': 'okhttp/4.9.1',
        'user-version': '2.15.3',
        'user-locale': 'nl-NL',
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

def login(preauth_token, prereg_id):
    t = RequestsHTTPTransport(
        url=GRAPHQL_URL,
        verify=True,
        retries=3,
        headers=generateHeaders(preauth_token)
    )
    client = Client(transport=t)
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
    variables = {"email": EMAIL, "password": PASSWORD, "locale": "nl-NL", "preregisterId": prereg_id}

    result = client.execute(query, variable_values=variables)
    return result['tokenWithCredentials']['token']

def getPodcasts(token):
    t = RequestsHTTPTransport(
        url=GRAPHQL_URL,
        verify=True,
        retries=3,
        headers=generateHeaders(token)
    )
    client = Client(transport=t)
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
        "podcastId": PODCAST_ID,
        "limit": 1000,
        "offset": 0,
        "sorting": "PUBLISHED_DESCENDING"
    }

    result = client.execute(query, variable_values=variables)
    return result

def contentLengthOfUrl(url):
    return head(url).headers['content-length']



def podcastsToRss(data):
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
        fe.enclosure(url, contentLengthOfUrl(url), mt)
        fe.podcast.itunes_duration(episode['streamMedia']['duration'])
        fe.description(episode['description'])
        fe.pubDate(episode['datetime'])

    fg.rss_file(f'{PODCAST_ID}.xml')


if __name__ == "__main__":
    if EMAIL is None or PASSWORD is None or PODCAST_ID is None:
        raise ValueError("Email, password and podcast id should be defined")

    preauth_token = getPreregisterToken()
    prereg_id = getOnboardingId(preauth_token)
    token = login(preauth_token, prereg_id)
    podcasts = getPodcasts(token)

    podcastsToRss(podcasts)
