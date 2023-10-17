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

async function acceptCookies(page: Page) : Promise<Page> {
  const cookieButtonSelector = ".cookie button";
  await page.waitForSelector(cookieButtonSelector);
  await page.click(cookieButtonSelector);
  await page.waitForSelector(cookieButtonSelector, {"hidden": true, "timeout": ANIMATION_TIMEOUT});
  return page
}

async function login(page: Page, username: string, password: string) : Promise<PodimoClient> {
  // Click the hamburger
  const hamburger = ".main-header__mobile-trigger";
  await page.waitForSelector(hamburger);
  await page.click(hamburger);

  // Press login
  const loginPopupButtonSelector = ".main-header__log-in-trigger";
  await page.waitForSelector(loginPopupButtonSelector);
  await page.click(loginPopupButtonSelector);

  // Wait for the login box to appear
  await page.waitForSelector(".login");

  // Login
  await page.type('input[type=email]', username);
  await page.type('input[type=password]', password);
  await page.click('.btn--login');

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

    await page.goto('https://podimo.com');
    page = await acceptCookies(page);
    const client = await login(page, username, password);
    await page.repl();
  });
  await endSession(session);

  await browser.close();
}

if (import.meta.main) {
  await main();
}
