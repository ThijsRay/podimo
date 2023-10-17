/* eslint-disable jest/no-conditional-in-test */
import * as http from 'http'
import getPort from 'get-port'
import type { Server } from 'http'
import * as _puppeteer from 'puppeteer'
import type * as puppeteerType from 'puppeteer-core'
import { RequestInterceptionManager } from './main'

const puppeteer = _puppeteer as unknown as typeof puppeteerType

let server: Server
let browser: puppeteerType.Browser
let page: puppeteerType.Page
let client: puppeteerType.CDPSession
let browserClient: puppeteerType.CDPSession
let manager: RequestInterceptionManager

const host = 'localhost'
let port = 3_000

const startServer = async (handler: http.RequestListener): Promise<void> => {
  // eslint-disable-next-line require-atomic-updates
  port = await getPort({ host, port })
  return new Promise((resolve) => {
    server = http.createServer(handler).listen(port, host, resolve)
  })
}

const stopServer = (): Promise<void> =>
  new Promise((resolve, reject) => {
    server.close((err) => {
      if (err) reject(err)
      else resolve()
    })
  })

describe('RequestInterceptionManager', () => {
  jest.setTimeout(5_000)

  beforeAll(async () => {
    browser = await puppeteer.launch()
    browserClient = await browser.target().createCDPSession()
  })

  afterAll(async () => {
    await browser.close()
  })

  beforeEach(async () => {
    page = await browser.newPage()
    client = await page.target().createCDPSession()
  })

  afterEach(async () => {
    await page.close()
    await stopServer()
    await manager.clear()
  })

  describe.each`
    streamResponse
    ${true}
    ${false}
  `(
    'with streamResponse: $streamResponse',
    (options: { streamResponse: boolean }) => {
      it('should intercept and modify response', async () => {
        await startServer((req, res) => {
          res.writeHead(200, { 'Content-Type': 'text/plain' })
          res.end('Hello, world!')
        })

        manager = new RequestInterceptionManager(client)
        await manager.intercept({
          urlPattern: '*',
          modifyResponse: ({ body }) => ({
            body: body?.replace('world', 'Jest'),
          }),
          ...options,
        })

        await page.goto(`http://localhost:${port}`)
        const text = await page.evaluate(() => document.body.textContent)
        expect(text).toBe('Hello, Jest!')

        const response = await page.evaluate(async (url) => {
          const response = await fetch(url)
          return response.text()
        }, `http://localhost:${port}`)

        expect(response).toBe('Hello, Jest!')
      })

      it('should intercept and modify request', async () => {
        await startServer((req, res) => {
          if (req.url === '/') {
            res.writeHead(200, { 'Content-Type': 'text/plain' })
            res.end('Original request')
          } else if (req.url === '/modified') {
            res.writeHead(200, { 'Content-Type': 'text/plain' })
            res.end('Modified request')
          } else {
            res.writeHead(404, { 'Content-Type': 'text/plain' })
            res.end('Not found')
          }
        })

        manager = new RequestInterceptionManager(client)
        await manager.intercept({
          urlPattern: '*/original',
          modifyRequest: ({ event }) => ({
            url: event.request.url.replace('original', 'modified'),
          }),
          ...options,
        })

        await page.goto(`http://localhost:${port}`)
        const text = await page.evaluate(() => document.body.textContent)
        expect(text).toBe('Original request')

        const response = await page.evaluate(async (url) => {
          const response = await fetch(url)
          return response.text()
        }, `http://localhost:${port}/original`)

        expect(response).toBe('Modified request')
      })

      it('should not intercept requests not matching urlPattern', async () => {
        await startServer((req, res) => {
          res.writeHead(200, { 'Content-Type': 'text/plain' })
          res.end('Hello, world!')
        })

        manager = new RequestInterceptionManager(client)
        await manager.intercept({
          urlPattern: 'non-existent-url/*',
          modifyResponse: ({ body }) => ({
            body: body?.replace('world', 'Jest'),
          }),
          ...options,
        })

        await page.goto(`http://localhost:${port}`)
        const text = await page.evaluate(() => document.body.textContent)
        expect(text).toBe('Hello, world!')

        const response = await page.evaluate(async (url) => {
          const response = await fetch(url)
          return response.text()
        }, `http://localhost:${port}`)

        expect(response).toBe('Hello, world!')
      })

      it('should handle intercepting a 304 response', async () => {
        await startServer((req, res) => {
          res.writeHead(304, { 'Content-Type': 'text/plain' })
          res.end()
        })

        manager = new RequestInterceptionManager(client)
        await manager.intercept({
          urlPattern: '*',
          modifyResponse: () => ({
            responseCode: 200,
            body: 'Intercepted',
          }),
          ...options,
        })

        await page.goto(`http://localhost:${port}`)
        const text = await page.evaluate(() => document.body.textContent)
        expect(text).toBe('Intercepted')

        const response = await page.evaluate(async (url) => {
          const response = await fetch(url)
          return response.text()
        }, `http://localhost:${port}`)

        expect(response).toBe('Intercepted')
      })

      it('should handle intercepting a redirect response', async () => {
        await startServer((req, res) => {
          if (req.url === '/redirected') {
            res.writeHead(200, { 'Content-Type': 'text/plain' })
            res.end('Works')
          } else {
            res.writeHead(301, {
              Location: `http://localhost:${port}/redirected`,
            })
            res.end()
          }
        })

        manager = new RequestInterceptionManager(client)
        await manager.intercept({
          urlPattern: '*/redirected',
          modifyResponse: ({ body, event: { responseStatusCode } }) => ({
            responseCode: 200,
            body: `Modified: ${body} ${responseStatusCode}`,
          }),
          ...options,
        })

        await page.goto(`http://localhost:${port}/somePath`)
        const text = await page.evaluate(() => document.body.textContent)
        expect(text).toBe('Modified: Works 200')

        const response = await page.evaluate(async (url) => {
          const response = await fetch(url, { redirect: 'follow' })
          return response.text()
        }, `http://localhost:${port}/somePath`)

        expect(response).toBe('Modified: Works 200')

        await manager.intercept({
          urlPattern: '*/somePath',
          modifyResponse: ({ body, event: { responseStatusCode } }) => ({
            responseCode: 200,
            body: `Modified: ${responseStatusCode}, body: ${body ?? 'n/a'}`,
          }),
          ...options,
        })

        await page.goto(`http://localhost:${port}/somePath`)
        const text2 = await page.evaluate(() => document.body.textContent)
        expect(text2).toBe('Modified: 301, body: n/a')

        const response2 = await page.evaluate(async (url) => {
          const response2 = await fetch(url, { redirect: 'follow' })
          return response2.text()
        }, `http://localhost:${port}/somePath`)

        expect(response2).toBe('Modified: 301, body: n/a')
      })

      it('should handle different status codes', async () => {
        await startServer((req, res) => {
          res.writeHead(403, { 'Content-Type': 'text/plain' })
          res.end('It is forbidden')
        })

        manager = new RequestInterceptionManager(client)
        await manager.intercept({
          urlPattern: '*',
          modifyResponse: ({ body }) => ({
            responseCode: 401,
            body: body?.replace('It is forbidden', 'Modified Unauthorized'),
          }),
          ...options,
        })

        await page.goto(`http://localhost:${port}`)
        const text = await page.evaluate(() => document.body.textContent)
        expect(text).toBe('Modified Unauthorized')

        const response = await page.evaluate(async (url) => {
          const response = await fetch(url)
          return {
            status: response.status,
            text: await response.text(),
          }
        }, `http://localhost:${port}`)

        expect(response.status).toBe(401)
        expect(response.text).toBe('Modified Unauthorized')
      })

      it('should handle multiple interception rules', async () => {
        await startServer((req, res) => {
          if (req.url === '/first') {
            res.writeHead(200, { 'Content-Type': 'text/plain' })
            res.end('First')
          } else if (req.url === '/second') {
            res.writeHead(200, { 'Content-Type': 'text/plain' })
            res.end('Second')
          } else {
            res.writeHead(404, { 'Content-Type': 'text/plain' })
            res.end('Not found')
          }
        })

        manager = new RequestInterceptionManager(client)
        await manager.intercept(
          {
            urlPattern: '*/first',
            modifyResponse: ({ body }) => ({
              body: body?.replace('First', 'First intercepted'),
            }),
            ...options,
          },
          {
            urlPattern: '*/second',
            modifyResponse: ({ body }) => ({
              body: body?.replace('Second', 'Second intercepted'),
            }),
            ...options,
          },
        )

        await page.goto(`http://localhost:${port}`)
        const text = await page.evaluate(() => document.body.textContent)
        expect(text).toBe('Not found')

        const firstResponse = await page.evaluate(async (url) => {
          const response = await fetch(url)
          return response.text()
        }, `http://localhost:${port}/first`)

        const secondResponse = await page.evaluate(async (url) => {
          const response = await fetch(url)
          return response.text()
        }, `http://localhost:${port}/second`)

        expect(firstResponse).toBe('First intercepted')
        expect(secondResponse).toBe('Second intercepted')
      })

      it('should intercept and modify requests on new tabs', async () => {
        await startServer((req, res) => {
          if (req.url === '/') {
            res.writeHead(200, { 'Content-Type': 'text/html' })
            res.end('<a href="/new-tab" target="_blank">Open new tab</a>')
          } else if (req.url === '/new-tab') {
            res.writeHead(200, { 'Content-Type': 'text/plain' })
            res.end('Hello, new tab!')
          } else {
            res.writeHead(404, { 'Content-Type': 'text/plain' })
            res.end('Not found')
          }
        })

        // Set up request interception for the initial page
        manager = new RequestInterceptionManager(browserClient)
        await manager.intercept({
          urlPattern: '*',
          modifyResponse: ({ body }) =>
            body
              ? {
                  body: body.replace('new tab', 'new tab intercepted'),
                }
              : undefined,
          ...options,
        })

        await page.goto(`http://localhost:${port}`)

        // Listen for a new page to be opened
        const newPagePromise = browser
          .waitForTarget(
            (target) =>
              target.type() === 'page' &&
              target.url() === `http://localhost:${port}/new-tab`,
          )
          .then((target) => target.page())
          .then((newPage) => newPage!)

        // Click the link to open a new tab
        await page.click('a')

        // Wait for the new page to be opened
        const newPage = await newPagePromise

        // Check if the request on the new tab was intercepted and modified
        const newText = await newPage.evaluate(() => document.body.textContent)
        expect(newText).toBe('Hello, new tab intercepted!')

        const newResponse = await newPage.evaluate(async (url) => {
          const response = await fetch(url)
          return response.text()
        }, `http://localhost:${port}/new-tab`)

        expect(newResponse).toBe('Hello, new tab intercepted!')
      })
    },
  )

  it('should intercept and modify response chunks from an EventStream', async () => {
    const messages = ['Hello', 'world', '!']
    let messageId = 0

    // Set up an EventStream server that sends a series of messages
    await startServer((req, res) => {
      if (req.url === '/') {
        res.writeHead(200, { 'Content-Type': 'text/plain' })
        res.end('Hello!')
        return
      }

      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      })

      const sendNextMessage = () => {
        res.write(`id: ${messageId}\n`)
        res.write(`data: ${messages[messageId]}\n\n`)
        messageId += 1

        if (messageId >= messages.length) {
          res.end()
        }
      }

      sendNextMessage()
      sendNextMessage()
      sendNextMessage()
    })

    manager = new RequestInterceptionManager(client)
    await manager.intercept({
      urlPattern: '*/stream',
      // Replace "world" with "Jest" in the response chunk
      modifyResponseChunk: ({ data, ...rest }) => ({
        data: data.replace('world', 'Jest'),
        ...rest,
      }),
      streamResponse: { chunkSize: 10 },
    })

    await page.goto(`http://localhost:${port}`)

    const receivedMessages = await page.evaluate(async (url) => {
      const eventSource = new EventSource(url)
      const receivedMessages: string[] = []

      return new Promise<string[]>((resolve, reject) => {
        eventSource.addEventListener('message', (event) => {
          receivedMessages.push(event.data)

          if (receivedMessages.length === 3) {
            eventSource.close()
            resolve(receivedMessages)
          }
        })

        eventSource.addEventListener('error', (error) => {
          eventSource.close()
          reject(error)
        })
      })
    }, `http://localhost:${port}/stream`)

    expect(receivedMessages).toEqual(['Hello', 'Jest', '!'])
  })
})
