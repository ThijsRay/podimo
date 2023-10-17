# puppeteer-intercept-and-modify-requests

The `puppeteer-intercept-and-modify-requests` TypeScript library allows you to intercept and modify network requests and responses using Puppeteer. It supports modifying all network requests and responses. You can also apply delays, stream responses, modify error responses or apply network errors. It provides a powerful and flexible tool for controlling network behavior in your web automation tasks.

- You may deny the request by returning an object with `errorReason` instead of a `body`.
- You may modify the request itself, before it is sent to the server, by adding a `modifyRequest` function.
- You may passthrough the request without any modification, by returning `undefined`.

### Example Use Cases

1.  **Content modification**: You can modify the content of HTML, CSS, or JavaScript files on the fly, allowing you to test changes without modifying the actual source files or server responses. This can be useful for debugging or experimenting with site layout, design, or functionality.
2.  **Throttling network requests**: You can apply delays to requests or responses to simulate different network conditions or server response times, which can help you understand how your application performs under various scenarios and ensure it remains responsive even under slow or unreliable network conditions.
3.  **Caching and performance testing**: You can intercept and modify cache headers to test the performance and caching behavior of your application, ensuring that your caching strategy is working as expected and providing optimal performance for your users.
4.  **Security testing**: You can intercept and modify requests to test the security of your application, simulating attacks, and verifying the robustness of your application against common web vulnerabilities.

### Superiority over Built-in Puppeteer Features

The `puppeteer-intercept-and-modify-requests` library offers several advantages over using the rudimentary `page.setRequestInterception` and `page.on('request', interceptedRequestCallback)` built-in to Puppeteer:

1.  **Simpler API**: The library provides a more concise and easy-to-understand API for intercepting and modifying requests and responses, making it easier to implement and maintain your code.
2.  **Fine-grained control**: The library allows you to intercept and modify requests and responses at various stages, giving you greater control over the network behavior of your application.
3.  **Streaming and modifying response chunks**: Unlike the built-in Puppeteer features, this library supports streaming and modifying response chunks, allowing you to manipulate large responses more efficiently and without having to load the entire response into memory.
4.  **Error handling**: The library offers built-in error handling, making it easier to catch and handle errors that might occur during the request interception process.
5.  **Support for complex use cases**: The library provides additional functionality, such as applying delays and failing requests, which can be useful for advanced use cases and testing scenarios that are not easily achievable with the built-in Puppeteer features.

In summary, the `puppeteer-intercept-and-modify-requests` library offers a more powerful and flexible solution for controlling network behavior in your Puppeteer projects, making it a superior choice over the built-in `page.setRequestInterception` and `page.on('request', interceptedRequestCallback)` features.

## Installation

```shell
npm install puppeteer-intercept-and-modify-requests
```

## Example Usage

To modify intercepted requests:

```ts
import { RequestInterceptionManager } from 'puppeteer-intercept-and-modify-requests'

// assuming 'page' is your Puppeteer page object
const client = await page.target().createCDPSession()
// note: if you want to intercept requests on ALL tabs, instead use:
// const client = await browser.target().createCDPSession()

const interceptManager = new RequestInterceptionManager(client)

await interceptManager.intercept(
  {
    // specify the URL pattern to intercept:
    urlPattern: `https://example.com/*`,
    // optionally filter by resource type:
    resourceType: 'Document',
    // specify how you want to modify the response (may be async):
    modifyResponse({ body }) {
      return {
        // replace break lines with horizontal lines:
        body: body.replaceAll('<br/>', '<hr/>'),
      }
    },
  },
  {
    urlPattern: '*/api/v4/user.json',
    // specify how you want to modify the response (may be async):
    modifyResponse({ body }) {
      const parsed = JSON.parse(body)
      // set role property to 'admin'
      parsed.role = 'admin'
      return {
        body: JSON.stringify(parsed),
      }
    },
  },
)
```

## API

### Types

- `ModifiedResponse`: A type representing a modified response object.
- `ModifiedRequest`: A type representing a modified request object.
- `ModifyResponseChunkFn`: A function type for modifying response chunks.
- `StreamResponseConfig`: A configuration object for streaming responses.
- `Interception`: An interception configuration object.
- `InterceptionWithUrlPatternRegExp`: An interception configuration object extended with a RegExp representation of the URL pattern.

### Classes

- `RequestInterceptionManager`: A class for managing request interceptions.

  - `constructor(client: CDPSession, { onError } = {})`: Creates a new `RequestInterceptionManager` instance.

  - `async intercept(...interceptions: Interception[])`: Enables request interception and adds the provided interception configurations.

  - `async removeIntercept(interceptUrlPattern: string)`: Removes an existing interception configuration for the specified URL pattern.

  - `async enable()`: Enables request interception based on the current interception configurations.

  - `async disable()`: Disables request interception.

  - `async clear()`: Clears all interception configurations and disables request interception.

  - `async onRequestPausedEvent(event: Protocol.Fetch.RequestPausedEvent)`: An async event handler for when a request is paused.

## Usage Examples

Here's an example of how to use the `RequestInterceptionManager` to intercept and modify a request and a response:

```ts
import puppeteer from 'puppeteer'
import {
  RequestInterceptionManager,
  Interception,
} from 'puppeteer-intercept-and-modify-requests'

async function main() {
  const browser = await puppeteer.launch()
  const page = await browser.newPage()

  const client = await page.target().createCDPSession()
  const requestInterceptionManager = new RequestInterceptionManager(client)

  const interceptionConfig: Interception = {
    urlPattern: 'https://example.com/*',
    modifyRequest: async ({ event }) => {
      // Modify request headers
      return {
        headers: [{ name: 'X-Custom-Header', value: 'CustomValue' }],
      }
    },
    modifyResponse: async ({ body }) => {
      // Modify response body
      const modifiedBody = body.replace(/example/gi, 'intercepted')
      return { body: modifiedBody }
    },
  }

  await requestInterceptionManager.intercept(interceptionConfig)
  await page.goto('https://example.com')
  await browser.close()
}

main()
```

This example modifies the request by adding a custom header and modifies the response by replacing all occurrences of the word "example" with "intercepted".

## Advanced Usage

### Applying Delay

You can apply a delay to a request or response using the `delay` property in the `modifyRequest` or `modifyResponse` functions. Here's an example of how to add a delay to a request:

```ts
import puppeteer from 'puppeteer'
import {
  RequestInterceptionManager,
  Interception,
} from 'puppeteer-intercept-and-modify-requests'

async function main() {
  const browser = await puppeteer.launch()
  const page = await browser.newPage()

  const client = await page.target().createCDPSession()
  const requestInterceptionManager = new RequestInterceptionManager(client)

  const interceptionConfig: Interception = {
    urlPattern: 'https://example.com/*',
    modifyRequest: async ({ event }) => {
      // Add a 500 ms delay to the request
      return {
        delay: 500,
      }
    },
  }

  await requestInterceptionManager.intercept(interceptionConfig)
  await page.goto('https://example.com')
  await browser.close()
}

main()
```

In this example, a 500 ms delay is added to the request for the specified URL pattern.

### Handling Errors

You can handle errors using the `onError` option when creating a new `RequestInterceptionManager` instance. Here's an example of how to handle errors:

```ts
import puppeteer from 'puppeteer'
import {
  RequestInterceptionManager,
  Interception,
} from 'puppeteer-intercept-and-modify-requests'

async function main() {
  const browser = await puppeteer.launch()
  const page = await browser.newPage()

  const client = await page.target().createCDPSession()
  const requestInterceptionManager = new RequestInterceptionManager(client, {
    onError: (error) => {
      console.error('Request interception error:', error)
    },
  })

  const interceptionConfig: Interception = {
    urlPattern: 'https://example.com/*',
    modifyRequest: async ({ event }) => {
      // Modify request headers
      return {
        headers: [{ name: 'X-Custom-Header', value: 'CustomValue' }],
      }
    },
  }

  await requestInterceptionManager.intercept(interceptionConfig)
  await page.goto('https://example.com')
  await browser.close()
}

main()
```

In this example, any errors that occur during request interception are logged to the console with the message "Request interception error:".

### Failing a Request

To fail a request, return an object containing an `errorReason` property in the `modifyRequest` function. Here's an example of how to fail a request:

```ts
import puppeteer from 'puppeteer'
import {
  RequestInterceptionManager,
  Interception,
} from 'puppeteer-intercept-and-modify-requests'

async function main() {
  const browser = await puppeteer.launch()
  const page = await browser.newPage()

  const client = await page.target().createCDPSession()
  const requestInterceptionManager = new RequestInterceptionManager(client)

  const interceptionConfig: Interception = {
    urlPattern: 'https://example.com/*',
    modifyRequest: async ({ event }) => {
      // Fail the request with the error reason "BlockedByClient"
      return {
        errorReason: 'BlockedByClient',
      }
    },
  }

  await requestInterceptionManager.intercept(interceptionConfig)
  await page.goto('https://example.com')
  await browser.close()
}

main()
```

In this example, the request for the specified URL pattern is blocked with the error reason "BlockedByClient".

### Intercepting network requests from all Pages (rather than just the one)

When creating the `RequestInterceptionManager` instance, you can pass in the `client` object from the `CDPSession` of the `Browser` object. This will allow you to intercept requests from all the pages rather than just the one. Here's an example of how to do this:

```ts
// intercept requests on ALL tabs, instead use:
const client = await browser.target().createCDPSession()
const interceptManager = new RequestInterceptionManager(client)

// ...
```

### Streaming and Modifying Response Chunks

You can also stream and modify response chunks using the `streamResponse` and `modifyResponseChunk` options. Here's an example of how to do this:

```ts
import puppeteer from 'puppeteer'
import {
  RequestInterceptionManager,
  Interception,
} from 'puppeteer-intercept-and-modify-requests'

async function main() {
  const browser = await puppeteer.launch()
  const page = await browser.newPage()

  const client = await page.target().createCDPSession()
  const requestInterceptionManager = new RequestInterceptionManager(client)

  const interceptionConfig: Interception = {
    urlPattern: 'https://example.com/*',
    streamResponse: true,
    modifyResponseChunk: async ({ event, data }) => {
      // Modify response chunk
      const modifiedData = data.replace(/example/gi, 'intercepted')
      return { ...event, data: modifiedData }
    },
  }

  await requestInterceptionManager.intercept(interceptionConfig)
  await page.goto('https://example.com')
  await browser.close()
}

main()
```

In this example, the response is streamed and each response chunk has all occurrences of the word "example" replaced with "intercepted".
