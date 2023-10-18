import puppeteer from 'npm:puppeteer-extra'
import StealthPlugin from 'npm:puppeteer-extra-plugin-stealth'
import repl from 'npm:puppeteer-extra-plugin-repl'
import resourceBlock from 'npm:puppeteer-extra-plugin-block-resources';
import { Page, Browser, BrowserContext, executablePath, Puppeteer } from "npm:puppeteer";
import { EventEmitter } from 'node:events';

async function newBrowser() : Promise<Browser> {
  return puppeteer
    .use(repl())
    .use(resourceBlock({
      blockedTypes: new Set(['image', 'stylesheet', 'media', 'font', 'texttrack', 'websocket', 'manifest', 'eventsource', 'other'] as const)
    }))
    .use(StealthPlugin())
    .launch({
      headless: "new",
      // headless: "false",
      executablePath: executablePath(),
    });
}

async function newSession(browser: Browser) : Promise<BrowserContext> {
  return browser.createIncognitoBrowserContext();
}

async function newPage(session: BrowserContext) : Promise<Page> {
 return session.newPage();
}

const ANIMATION_TIMEOUT = 2500;

const query = `query PodcastEpisodesResultsQuery($podcastId: String!, $limit: Int!, $offset: Int!, $sorting: PodcastEpisodeSorting) {
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
`
// The request that will be hijacked, and the new payload
const baseUrl = "https://open.podimo.com/graphql?queryName="
const authUrl = baseUrl + "LoginResultsQuery";
const interceptUrl = baseUrl + "ProfileResultsQuery";
const operationName = "PodcastEpisodesResultsQuery";
const targetUrl = baseUrl + operationName;

class InterceptEmitter extends EventEmitter {}

async function interceptAndModify(page: Page, podcastId: string, emitter: InterceptEmitter) {
  // Setup post data
  const episodesLimit = 500;
  const payload = JSON.stringify({
    "operationName": operationName,
    "query": query,
    "variables": {
      "limit": episodesLimit,
      "offset": 0,
      "podcastId": podcastId,
      "sorting": "PUBLISHED_DESCENDING",
    }
  });

  // Setup emitters to transfer Request back
  let callback = null;
  emitter.on("response", (cb) => {
    callback = cb;
  })

  // Capture the request, and send a new request
  const client = await page.target().createCDPSession();
  client.on('Fetch.requestPaused', (event) => {
    const { requestId, request } = event;

    if (request.url == interceptUrl) {
      client.send('Fetch.fulfillRequest', {
        requestId,
        responseCode: 200,
        body: btoa("{}")
      }).then(() => {
          fetch(targetUrl, {
            method: request.method,
            headers: request.headers,
            body: payload
          }).then((response) => response.json())
            .then((data) => {
              if ("errors" in data) {
                callback(new Response(`{"errors": ${data[errors]}}`, {status: 500}));
              } else {
                callback(new Response(`{"ok": ${data}}`, {status: 200}));
              }
            })
      });
    } else if (request.url == authUrl) {
      client.send('Fetch.getResponseBody', { requestId }).then(({body, base64Encoded}) => {
        if (base64Encoded) {
          body = atob(body);
        }
        try {
          const body_json = JSON.parse(body);
          if ("errors" in body_json) {
            if (callback != null) {
              callback(new Response(body, {status: 500}));
            }
          }
        } catch (e) {
          callback(new Response(`{"errors: "Expected JSON response from Podimo: ${e}"}`, {status: 500}));
        }
      });
    }
  });

  // Issue requestPaused events when these requests happen
  await client.send('Fetch.enable', {
    patterns: [
      {
        urlPattern: interceptUrl,
        requestStage: "Request"
      },
      {
        urlPattern: authUrl,
        requestStage: "Response"
      }
    ]
  });
}

async function getPodcastInfo(page: Page, username: string, password: string, podcastId: string) : Promise<Response> {
  try {
    await page.setViewport({width: 390, height: 844})
    await page.goto('https://open.podimo.com');

    // Setup the interceptor
    const emitter = new InterceptEmitter();
    interceptAndModify(page, podcastId, emitter);
    const response = new Promise((resolve) => {
      emitter.emit('response', (value) => {
        resolve(value);
      })
    });

    // Login to the web player
    const emailInput = "input[name=email]";
    await page.waitForSelector(emailInput, {"visible": true, "timeout": ANIMATION_TIMEOUT});
    await page.type(emailInput, username);

    const passwordInput = "input[type=password]";
    await page.waitForSelector(passwordInput, {"visible": true, "timeout": ANIMATION_TIMEOUT});
    await page.type(passwordInput, password);

    const submitButton = "button[type=submit]";
    await page.waitForSelector(submitButton, {"visible": true, "timeout": ANIMATION_TIMEOUT});

    await page.click(submitButton);
    return await response;

    return new Response(`{"ok"}`, {status: 200});
  } catch (e) {
    return new Response(`{"error": ${e}}`, {status: 500});
  }

  // Submit and wait
  // await Promise.all([
  //   page.waitForNavigation({timeout: ANIMATION_TIMEOUT}),
    // Can fail if invalid credentials
    //   {
    //   "errors": [
    //     {
    //       "message": "Auth with credentials failed!",
    //       "locations": [
    //         {
    //           "line": 2,
    //           "column": 3
    //         }
    //       ],
    //       "path": [
    //         "tokenWithCredentials"
    //       ],
    //       "code": "auth_failed",
    //       "extensions": {
    //         "exception": {
    //           "code": "auth_failed",
    //           "message": "Auth with credentials failed!"
    //         }
    //       }
    //     }
    //   ],
    //   "data": null
    //  }

  // ]);
}

async function endSession(session: BrowserContext) {
  await session.close();
}

let browser = null;
async function getBrowser() : Promise<Browser> {
  if (browser == null) {
    browser = await newBrowser();
  }
  return browser;
}

type SessionAndResponse = {
  session: BrowserContext;
  response: Promise<Response>
}

async function spawnSessionAndGetInfo(browser: Browser, username: str, password: str, podcastId: str) : Promise<SessionAndResponse> {
  return newSession(browser).then(session => {
    const response = newPage(session).then(page => {
      return getPodcastInfo(page, username, password, podcastId).then(podcastInfo => {
        return podcastInfo
      })
    });
    return { session, response }
  });
}

async function requestHandler(req: Request) : Response {
  if (req.method != "POST") {
    return new Response("{\"error\": \"Must be a POST request\"}", {status: 405});
  }

  try {
    const data = await req.json();
    if ("username" in data && "password" in data && "podcastId" in data) {
      const _browser = await getBrowser();
      try {
        const { session, response } = await spawnSessionAndGetInfo(_browser, data["username"], data["password"], data["podcastId"])
        const resolvedResponse = await response;
        endSession(session);
        return resolvedResponse
      } catch (e) {
        // Something failed, let's try to restart the browser
        // and do it again
        try {
          await browser.close();
        } catch (e) {}
        browser = null;
        const _browser = await getBrowser();

        const { session, response } = await spawnSessionAndGetInfo(_browser, data["username"], data["password"], data["podcastId"])
        const resolvedResponse = await response;
        endSession(session);
        return resolvedResponse
      }
      return new Response(`{"error": "Spawning failed twice"}`, {status: 500})
    } else {
      return new Response(`{"error": "Missing a field"}`, {status: 400});
    }
  } catch (e) {
    return new Response(`{"error": ${e}}`, {status: 400});
  }
}

function main() {
  Deno.serve({port: 12105, hostname: "localhost"}, requestHandler);
}

if (import.meta.main) {
  main();
}
