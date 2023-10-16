import puppeteer from 'npm:puppeteer-extra'
import StealthPlugin from 'npm:puppeteer-extra-plugin-stealth'
import { executablePath } from "npm:puppeteer";

export function puppet() {
  // puppeteer usage as normal
  puppeteer
    .use(StealthPlugin())
    .launch({
      headless: "new",
      executablePath: executablePath()
    }).then(async browser => {
    console.log('Running tests..')
    const page = await browser.newPage()
    await page.goto('https://bot.sannysoft.com')
    await page.waitForTimeout(5000)
    await page.screenshot({ path: 'testresult.png', fullPage: true })
    await browser.close()
    console.log(`All done, check the screenshot. ✨`)
  })
}

// Learn more at https://deno.land/manual/examples/module_metadata#concepts
if (import.meta.main) {
  puppet()
}
