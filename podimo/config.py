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
from dotenv import dotenv_values

# Load variables from the `.env` file first,
# and overwrite them with environment variables
config = {
    **dotenv_values(".env"),
    **os.environ
}

# You can overwrite the following four values with environmental variables
# - `PODIMO_HOSTNAME`: the hostname that is displayed to the user.
#                      This defaults to "podimo.thijs.sh".
# - `PODIMO_BIND_HOST`: to what IP and port the Python webserver should bind.
#                       Defaults to "127.0.0.1:12104"
# - `PODIMO_PROTOCOL`: what protocol is being used for all links that are
#                      displayed to the user. Defaults to "https".
PODIMO_HOSTNAME = str(config.get("PODIMO_HOSTNAME", "localhost:12104"))
PODIMO_BIND_HOST = str(config.get("PODIMO_BIND_HOST", "127.0.0.1:12104"))
PODIMO_PROTOCOL = str(config.get("PODIMO_PROTOCOL", "http"))
HTTP_PROXY = config.get("HTTP_PROXY", None)
ZENROWS_API = config.get("ZENROWS_API", None)
SCRAPER_API = config.get("SCRAPER_API", None)
CACHE_DIR = os.path.abspath(str(config.get("CACHE_DIR", "./cache")))
BLOCK_LIST_FILE = str(config.get("BLOCK_LIST_FILE", "./.block-list"))

# Enable extra logging in debugging mode
DEBUG = bool(str(config.get("DEBUG", None)).lower() in ['true', '1', 't', 'y', 'yes'])

# Enable local credentials
LOCAL_CREDENTIALS = bool(str(config.get("LOCAL_CREDENTIALS", None)).lower() in ['true', '1', 't', 'y', 'yes'])
PODIMO_EMAIL = config.get("PODIMO_EMAIL", None)
PODIMO_PASSWORD = config.get("PODIMO_PASSWORD", None)

# Podimo's API uses GraphQL. This variable defines the endpoint where
# the API can be found.
GRAPHQL_URL = "https://podimo.com/graphql"

# Whether login tokens should be cached on disk, or only in memory
STORE_TOKENS_ON_DISK = bool(str(config.get("STORE_TOKENS_ON_DISK", True)).lower() in ['true', '1', 't', 'y', 'yes'])

# The time that a token is stored in cache
TOKEN_CACHE_TIME = int(config.get("TOKEN_CACHE_TIME", 3600 * 24 * 5))  # seconds = 5 days by default

# The time that a podcast feed is stored in cache
PODCAST_CACHE_TIME = int(config.get("PODCAST_CACHE_TIME", "21600"))  # Default = 3600 * 6 = 6 hours

# The time that the content information is cached
HEAD_CACHE_TIME = int(config.get("HEAD_CACHE_TIME", 7 * 60 * 60 * 24))  # seconds = 7 days by default

# Whether the feeds generated with this tool should show up in public podcast catalogues
PUBLIC_FEEDS = bool(str(config.get("PUBLIC_FEEDS", None)).lower() in ['true', '1', 't', 'y', 'yes'])

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

# Load block list from file '.block-list' if it exists
BLOCKED = set()
if os.path.exists(BLOCK_LIST_FILE):
    with open (BLOCK_LIST_FILE, 'r') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith('#'): 
                line = line.split(' ', 1)[0]
                BLOCKED.add(line)


# load experimental video support env vars
VIDEO_ENABLED = bool(
    str(config.get("ENABLE_VIDEO", None)).lower() in ["true", "1", "t", "y", "yes"]
)
VIDEO_CHECK_ENABLED = bool(
    str(config.get("ENABLE_VIDEO_CHECK", None)).lower() in ["true", "1", "t", "y", "yes"]
)
VIDEO_TITLE_SUFFIX = str(config.get("VIDEO_TITLE_SUFFIX", ""))
