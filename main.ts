import puppeteer from 'npm:puppeteer-extra'
import StealthPlugin from 'npm:puppeteer-extra-plugin-stealth'
import repl from 'npm:puppeteer-extra-plugin-repl'
import resourceBlock from 'npm:puppeteer-extra-plugin-block-resources';
import { Page, Browser, BrowserContext, executablePath } from "npm:puppeteer";
import { RequestInterceptionManager } from 'https://raw.githubusercontent.com/ThijsRay/puppeteer-intercept-and-modify-requests/60706c9e4d81c490ca7d500f2e57a1c2c246f8a9/src/main.ts';

async function newBrowser() : Promise<Browser> {
  return puppeteer
    .use(repl())
    .use(resourceBlock({
      blockedTypes: new Set(['image', 'stylesheet', 'media', 'font', 'texttrack', 'websocket', 'manifest', 'eventsource', 'other'] as const)
    }))
    .use(StealthPlugin())
    .launch({
      // headless: "new",
      headless: false,
      executablePath: executablePath(),
    });
}

async function newSession(browser: Browser) : Promise<BrowserContext> {
  return browser.createIncognitoBrowserContext();
}

async function newPage(session: BrowserContext) : Promise<Page> {
  return session.newPage();
}

class PodimoClient {}

const ANIMATION_TIMEOUT = 1000;

async function login(page: Page, username: string, password: string) : Promise<PodimoClient> {
  const emailInput = "input[name=email]";
  await page.waitForSelector(emailInput, {"visible": true, "timeout": ANIMATION_TIMEOUT});
  await page.type(emailInput, username);

  const passwordInput = "input[type=password]";
  await page.waitForSelector(passwordInput, {"visible": true, "timeout": ANIMATION_TIMEOUT});
  await page.type(passwordInput, password);

  const submitButton = "button[type=submit]";
  await page.waitForSelector(submitButton, {"visible": true, "timeout": ANIMATION_TIMEOUT});

  const client = await page.target().createCDPSession();
  const interceptManager = new RequestInterceptionManager(client);
  const interceptConfig : Interception = {
    urlPattern: "*graphql*",
    modifyResponse: ({ body }) => {
      console.log(body);
      return {
        body: body
      }
    }
  }
  await interceptManager.intercept(interceptConfig);

  await Promise.all([
    page.waitForNavigation({timeout: 5000}),
    page.click(submitButton),
  ]);
  
  await page.repl();

  return new PodimoClient();
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
    // page = await acceptCookies(page);
    const client = await login(page, username, password);
  });
  await endSession(session);

  await browser.close();
}

if (import.meta.main) {
  await main();
}
