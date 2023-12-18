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

import os
import logging

# You can overwrite the following four values with environmental variables
# - `PODIMO_HOSTNAME`: the hostname that is displayed to the user.
#                      This defaults to "podimo.thijs.sh".
# - `PODIMO_BIND_HOST`: to what IP and port the Python webserver should bind.
#                       Defaults to "127.0.0.1:12104"
# - `PODIMO_PROTOCOL`: what protocol is being used for all links that are
#                      displayed to the user. Defaults to "https".
PODIMO_HOSTNAME = os.environ.get("PODIMO_HOSTNAME", "podimo.thijs.sh")
PODIMO_BIND_HOST = os.environ.get("PODIMO_BIND_HOST", "127.0.0.1:12104")
PODIMO_PROTOCOL = os.environ.get("PODIMO_PROTOCOL", "https")
ZENROWS_API = os.environ.get("ZENROWS_API", None)
SCRAPER_API = os.environ.get("SCRAPER_API", None)
CACHE_DIR = os.environ.get("CACHE_DIR", "./cache/")

# Enable extra logging in debugging mode
DEBUG = os.environ.get("DEBUG", False)

# Podimo's API uses GraphQL. This variable defines the endpoint where
# the API can be found.
GRAPHQL_URL = "https://podimo.com/graphql"

# Whether login tokens should be cached on disk, or only in memory
STORE_TOKENS_ON_DISK = bool(os.environ.get("STORE_TOKENS_ON_DISK", True))

# The time that a token is stored in cache
TOKEN_TIMEOUT = 3600 * 24 * 5  # seconds = 5 days

# The time that a podcast feed is stored in cache
PODCAST_CACHE_TIME = int(os.environ.get("PODCAST_CACHE_TIME", "21600"))  # Default = 3600 * 6 = 6 hours

# The time that the content information is cached
HEAD_CACHE_TIME = 7 * 60 * 60 * 24  # seconds = 7 days

LOCALES = [
        'nl-NL',
        'de-DE',
        'da-DK',
        'es-ES',
        'en-US',
        'es-MX',
        'no-NO',
        'fi-FI',
        'en-GB'
]
REGIONS = [
        ('nl', 'Nederland'),
        ('de', 'Deutschland'),
        ('dk', 'Danmark'),
        ('es', 'España'),
        ('latam', 'America latina'),
        ('en', 'International'),
        ('mx', 'Mexico'),
        ('no', 'Norge'),
        ('fi', 'Suomi'),
        ('uk', 'United Kingdom')
]

# If DEBUG mode is enabled, modify the logging output
log_level = logging.INFO
if DEBUG:
    log_level = logging.DEBUG

logging.basicConfig(
    format="%(levelname)s | %(asctime)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    level=log_level
)
