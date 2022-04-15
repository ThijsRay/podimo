from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from random import choice, randint
from json import loads

GRAPHQL_URL = "https://graphql.pdm-gateway.com/graphql"
EMAIL = None
PASSWORD = None

def randomHexId(length):
    string = []
    hex_chars = list('1234567890abcdef')
    for i in range(length):
        string.append(choice(hex_chars))
    return "".join(string)

def randomFlyerId():
    a = randint(1000000000000, 9999999999999)
    b = randint(1000000000000, 9999999999999)
    return f"{a}-{b}"

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



if __name__ == "__main__":
    if EMAIL is None or PASSWORD is None:
        raise ValueError("Email and password should be defined")

    preauth_token = getPreregisterToken()
    prereg_id = getOnboardingId(preauth_token)
    token = login(preauth_token, prereg_id)
