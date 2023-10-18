import puppeteer from 'npm:puppeteer-extra'
import StealthPlugin from 'npm:puppeteer-extra-plugin-stealth'
import repl from 'npm:puppeteer-extra-plugin-repl'
import resourceBlock from 'npm:puppeteer-extra-plugin-block-resources';
import { Page, Browser, BrowserContext, executablePath } from "npm:puppeteer";

async function newBrowser() : Promise<Browser> {
  return puppeteer
    .use(repl())
    .use(resourceBlock({
      blockedTypes: new Set(['image', 'stylesheet', 'media', 'font', 'texttrack', 'websocket', 'manifest', 'eventsource', 'other'] as const)
    }))
    .use(StealthPlugin())
    .launch({
      headless: "new",
      // headless: false,
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
// const baseUrl = "http://localhost:8080/?queryName=";
const interceptUrl = baseUrl + "ProfileResultsQuery";
const operationName = "PodcastEpisodesResultsQuery";
const targetUrl = baseUrl + operationName;

async function interceptAndModify(page: Page, podcastId: string) {
  // Setup post data
const episodesLimit = 50;
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
  client.once('Fetch.requestPaused', (event) => {
    const { requestId, request } = event;

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

            console.log("Finished!");
          })
    })
  });

  // Issue requestPaused events when these requests happen
  await client.send('Fetch.enable', {
    patterns: [
      {
        urlPattern: interceptUrl,
        requestStage: "Request"
      }
    ]
  });
}

async function getPodcastInfo(page: Page, username: string, password: string, podcastId: string) {
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
  await Promise.all([
    page.waitForNavigation({timeout: ANIMATION_TIMEOUT}),
    page.click(submitButton),
  ]);
}

async function endSession(session: BrowserContext) {
  await session.close();
}

async function main() {
  const browser = await newBrowser();

  const session = await newSession(browser);
  await newPage(session).then(async page => {
    // Press the login button
    //
    await page.setViewport({width: 390, height: 844})

    await page.goto('https://open.podimo.com');
    // await page.goto('http://localhost:8080');
    // page = await acceptCookies(page);
    await getPodcastInfo(page, username, password, podcastId);
  });
  await endSession(session);

  await browser.close();
}

if (import.meta.main) {
  await main();
}
