import puppeteer from 'npm:puppeteer-extra'
import StealthPlugin from 'npm:puppeteer-extra-plugin-stealth'
import repl from 'npm:puppeteer-extra-plugin-repl'
import { Page, Browser, BrowserContext, executablePath } from "npm:puppeteer";

async function newBrowser() : Promise<Browser> {
  return puppeteer
    .use(repl())
    .use(StealthPlugin())
    .launch({
      // headless: "new",
      headless: false,
      executablePath: executablePath()
    });
}

async function newSession(browser: Browser) : Promise<BrowserContext> {
  return browser.createIncognitoBrowserContext();
}

async function newPage(session: BrowserContext) : Promise<Page> {
  return session.newPage();
}

class PodimoClient {}

async function acceptCookies(page: Page) : Promise<Page> {
  await page.goto('https://podimo.com');
  await page.waitForSelector(".cookie")
  await page.click(".cookie >* button")
  return page
}

async function endSession(session: BrowserContext) {
  await session.close();
}

async function main() {
  const browser = await newBrowser();

  const session = await newSession(browser);
  newPage(session).then(async page => {
    await acceptCookies(page);
  });
  await endSession(session);

  await browser.close();
}

// Learn more at https://deno.land/manual/examples/module_metadata#concepts
if (import.meta.main) {
  await main();
}
