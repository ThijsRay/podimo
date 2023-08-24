# Copyright 2023 Thijs Raymakers
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

from hypercorn.config import Config
from hypercorn.asyncio import serve
from quart import Quart, request
from podimo.config import LOCAL_PROXY_HOST, GRAPHQL_URL
from aiohttp import ClientSession
from gzip import compress

# Setup Quart, used for serving the web pages
app = Quart(__name__)
PROXY_LOCATION = None

@app.route("/", methods=["POST"])
async def index():
    request_headers = request.headers
    request_headers.pop("Remote-Addr")
    request_headers.pop("Host")

    request_data = await request.get_data()
    async with ClientSession() as session:
        async with session.post(GRAPHQL_URL,
                                proxy=PROXY_LOCATION,
                                headers=request_headers,
                                data=request_data) as response:
            response_body = await response.read()
            response_headers = (dict(response.headers.items()))
            return compress(response_body, 1), response.status, response_headers

async def spawn_local_proxy(proxy_location):
    global PROXY_LOCATION
    PROXY_LOCATION = proxy_location

    config = Config()
    config.bind = [LOCAL_PROXY_HOST]
    await serve(app, config)
