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

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from podimo.config import GRAPHQL_URL, LOCAL_PROXY_URL
from podimo.utils import is_correct_email_address, token_key, randomFlyerId, generateHeaders as gHdrs, debug
from podimo.cache import insertIntoPodcastCache, getCacheEntry, podcast_cache
from time import time
from os import getenv
import sys

class PodimoClient:
    def __init__(self, username: str, password: str, region: str, locale: str):
        self.username = username
        self.password = password
        self.region = region
        self.locale = locale
        self.cookie_jar = None

        if len(self.username) == 0 or len(self.password) == 0:
            raise ValueError("Empty username or password")
        if len(self.username) > 256 or len(self.password) > 256:
            raise ValueError("Username or password are too long")
        if not is_correct_email_address(username):
            return ValueError("Email is not in the correct format")

        self.key = token_key(username, password)
        self.token = None

    def generateHeaders(self, authorization):
        return gHdrs(authorization, self.locale) 

    def getTransport(self, headers):
        # Pass all GraphQL requests through a proxy to bypass potential
        # blockades
        endpoint_url = GRAPHQL_URL
        if getenv("HTTP_PROXY"):
            endpoint_url = LOCAL_PROXY_URL
        return AIOHTTPTransport(url=endpoint_url,
                                headers=headers,
                                client_session_args={
                                    'cookie_jar': self.cookie_jar,
                                })

    # This gets the authentication token that is required for subsequent requests
    # as an anonymous user
    async def getPreregisterToken(self):
        t = self.getTransport(self.generateHeaders(None))
        debug("AuthorizationPreregisterUser")
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
                            currentCountry: $countryCode
                        ) {
                            token
                        }
                    }
                    """
            )
            variables = {"locale": self.locale, "countryCode": self.region, "appsFlyerId": randomFlyerId()}
            result = await client.execute(query, variable_values=variables)
            self.preauth_token = result["tokenWithPreregisterUser"]["token"]
            return self.preauth_token


    # Gets an "onboarding ID" that is used during login
    async def getOnboardingId(self):
        t = self.getTransport(self.generateHeaders(self.preauth_token))
        debug("OnboardingQuery")
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
            self.prereg_id = result["userOnboardingFlow"]["id"]
            return self.prereg_id


    async def podimoLogin(self):
        await self.getPreregisterToken()
        await self.getOnboardingId()

        t = self.getTransport(self.generateHeaders(self.preauth_token))
        debug("AuthorizationAuthorize")
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
                "email": self.username,
                "password": self.password,
                "locale": self.locale,
                "preregisterId": self.prereg_id,
            }

            result = await client.execute(query, variable_values=variables)
            self.token = result["tokenWithCredentials"]["token"]
            if self.token:
                return self.token
            else:
                raise ValueError("Invalid Podimo credentials or Podimo is unreachable")

    async def getPodcasts(self, podcast_id):
        podcast = getCacheEntry(podcast_id, podcast_cache)
        if podcast:
            timestamp, _ = podcast_cache[podcast_id]
            print(f"Got podcast {podcast_id} from cache ({int(timestamp-time())} seconds left)", file=sys.stderr)
            return podcast

        t = self.getTransport(self.generateHeaders(self.token))
        debug("ChannelEpisodesQuery")
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
            insertIntoPodcastCache(podcast_id, result)
            return result
