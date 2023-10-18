import puppeteer from 'npm:puppeteer-extra'
import StealthPlugin from 'npm:puppeteer-extra-plugin-stealth'
import repl from 'npm:puppeteer-extra-plugin-repl'
import resourceBlock from 'npm:puppeteer-extra-plugin-block-resources';
import { Page, Browser, BrowserContext, executablePath, Puppeteer } from "npm:puppeteer";

async function newBrowser() : Promise<Browser> {
  return puppeteer
    .use(repl())
    .use(resourceBlock({
      blockedTypes: new Set(['image', 'stylesheet', 'media', 'font', 'texttrack', 'websocket', 'manifest', 'eventsource', 'other'] as const)
    }))
    .use(StealthPlugin())
    .launch({
      // headless: "new",
      headless: "false",
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

async function interceptAndModify(page: Page, podcastId: string) {
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
              console.log(data);
              // Error
              // {
              //   errors: [
              //     {
              //       message: "User does not have enough privilege",
              //       locations: [ { line: 36, column: 3 } ],
              //       path: [ "episodes", 0, "streamMedia" ],
              //       code: "forbidden",
              //       extensions: {
              //         exception: {
              //           code: "forbidden",
              //           message: "User does not have enough privilege"
              //         }
              //       }
              //     }
              //   ],
              //   data: null
              // }

              console.log("get podcasts finished");
            })
      });
    } else if (request.url == authUrl) {
      client.send('Fetch.getResponseBody', { requestId }).then(({body, base64Encoded}) => {
        if (base64Encoded) {
          body = atob(body);
        }
        console.log(body);
        // Error
        // {
        // "errors": [
        //   {
        //     "message": "Invalid password",
        //     "locations": [
        //       {
        //         "line": 2,
        //         "column": 3
        //       }
        //     ],
        //     "path": [
        //       "tokenWithCredentials"
        //     ],
        //     "code": "invalid_password",
        //     "extensions": {
        //       "exception": {
        //         "code": "invalid_password",
        //         "message": "Invalid password"
        //       }
        //     }
        //   }
        // ],
        // "data": null
        // }
        console.log("auth finished");
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
  await page.setViewport({width: 390, height: 844})
  await page.goto('https://open.podimo.com');

  // Setup the interceptor
  interceptAndModify(page, podcastId);

  // Login to the web player
  const emailInput = "input[name=email]";
  await page.waitForSelector(emailInput, {"visible": true, "timeout": ANIMATION_TIMEOUT});
  await page.type(emailInput, username);

  const passwordInput = "input[type=password]";
  await page.waitForSelector(passwordInput, {"visible": true, "timeout": ANIMATION_TIMEOUT});
  await page.type(passwordInput, password);

  const submitButton = "button[type=submit]";
  await page.waitForSelector(submitButton, {"visible": true, "timeout": ANIMATION_TIMEOUT});

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

    page.click(submitButton);
    return new Response();
  // ]);
}

async function endSession(session: BrowserContext) {
  await session.close();
}

let browser = null;
async function getBrowser() {
  if (browser == null) {
    browser = await newBrowser();
  } else {
    browser = await puppeteer.connect().catch(_ => {
      browser.close();
      return newBrowser();
    })
  }
  return browser
}

async function requestHandler(req: Request) : Response {
  if (req.method != "POST") {
    return new Response("{}", {status: 405});
  }

  try {
    const data = await req.json();
    if ("username" in data && "password" in data && "podcastId" in data) {
      const browser = await getBrowser();
      const session = await newSession(browser);
      try {
        const username = data["username"];
        const password = data["password"];
        const podcastId = data["podcastId"];

        const page = await newPage(session);
        const info = await getPodcastInfo(page, username, password, podcastId);
      } finally {
        await endSession(session);
      }
    } else {
      return new Response("{error: \"Missing a field\"}", {status: 400});
    }
  } catch (e) {
    return new Response("{error: \"" + e + "\"}", {status: 400});
  }
}

function main() {
  Deno.serve({port: 12105, hostname: "localhost"}, requestHandler);
}

if (import.meta.main) {
  main();
}
