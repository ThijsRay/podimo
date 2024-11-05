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

from email.utils import parseaddr
from random import choice, randint
from hashlib import sha256
import asyncio
import requests
from functools import wraps, partial

def randomHexId(length: int):
    string = []
    hex_chars = list("1234567890abcdef")
    for _ in range(length):
        string.append(choice(hex_chars))
    return "".join(string)


def randomFlyerId():
    a = randint(1000000000000, 9999999999999)
    b = randint(1000000000000, 9999999999999)
    return str(f"{a}-{b}")


def token_key(username, password):
    key = sha256(
        b"~".join([username.encode("utf-8"), password.encode("utf-8")])
    ).hexdigest()
    return key

# Verify if it is actually an email address
def is_correct_email_address(username):
    return "@" in parseaddr(username)[1]


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

def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)
    return run

def video_exists_at_url(url: str) -> bool:
    res = requests.get(url)
    if res.text.strip().startswith("#EXTM3U"):
        return True
    return False
