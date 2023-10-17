/* eslint-disable no-continue,no-await-in-loop,node/no-unpublished-import */
import { promisify } from 'util'
import type { CDPSession, Protocol } from 'puppeteer-core'
import { getUrlPatternRegExp } from './urlPattern'

export { getUrlPatternRegExp }

const STATUS_CODE_OK = 200

export type ModifiedResponse =
  | ((
      | {
          responseCode?: number
          responseHeaders?: Protocol.Fetch.HeaderEntry[]
          body?: string
        }
      | {
          errorReason: Protocol.Network.ErrorReason
        }
    ) & {
      delay?: number
    })
  | void

export type ModifiedRequest =
  | (ModifiedResponse &
      Omit<
        Protocol.Fetch.ContinueRequestRequest,
        'requestId' | 'interceptResponse'
      >)
  | void

export type ModifyResponseChunkFn = (
  responseChunk: Protocol.IO.ReadResponse & {
    event: Protocol.Fetch.RequestPausedEvent
  },
) => Protocol.IO.ReadResponse | Promise<Protocol.IO.ReadResponse>

export interface StreamResponseConfig {
  chunkSize?: number
}

export type Interception = Omit<Protocol.Fetch.RequestPattern, 'requestStage'> &
  Pick<Required<Protocol.Fetch.RequestPattern>, 'urlPattern'> & {
    modifyResponse?: (response: {
      body: string | undefined
      event: Protocol.Fetch.RequestPausedEvent
    }) => ModifiedResponse | Promise<ModifiedResponse>
    modifyResponseChunk?: ModifyResponseChunkFn
    streamResponse?: boolean | StreamResponseConfig
    modifyRequest?: (request: {
      event: Protocol.Fetch.RequestPausedEvent
    }) => ModifiedRequest | Promise<ModifiedRequest>
  }

export type InterceptionWithUrlPatternRegExp = Interception & {
  urlPatternRegExp: RegExp
}

const wait = promisify(setTimeout)

export class RequestInterceptionManager {
  interceptions: Map<string, InterceptionWithUrlPatternRegExp> = new Map()
  #client: CDPSession
  #requestPausedHandler: (event: Protocol.Fetch.RequestPausedEvent) => void
  #isInstalled = false

  // eslint-disable-next-line no-console
  constructor(client: CDPSession, { onError = console.error } = {}) {
    this.#client = client
    this.#requestPausedHandler = (event: Protocol.Fetch.RequestPausedEvent) =>
      void this.onRequestPausedEvent(event).catch(onError)
  }

  async intercept(...interceptions: Interception[]) {
    if (interceptions.length === 0) return
    interceptions.forEach((interception) => {
      this.interceptions.set(interception.urlPattern, {
        ...interception,
        urlPatternRegExp: getUrlPatternRegExp(interception.urlPattern),
      })
    })
    await this.enable()
  }

  async removeIntercept(interceptUrlPattern: string) {
    if (this.interceptions.delete(interceptUrlPattern)) {
      await (this.interceptions.size > 0 ? this.enable() : this.disable())
    }
  }

  async enable(): Promise<void> {
    this.#install()
    return this.#client.send('Fetch.enable', {
      handleAuthRequests: false,
      patterns: [...this.interceptions.values()].map(
        ({ modifyRequest, modifyResponse, ...config }) =>
          ({
            ...config,
            requestStage: modifyRequest ? 'Request' : 'Response',
          } as const),
      ),
    })
  }

  async disable(): Promise<void> {
    this.#uninstall()
    try {
      await this.#client.send('Fetch.disable')
    } catch {
      // ignore (most likely session closed)
    }
  }

  async clear() {
    this.interceptions.clear()
    await this.disable()
  }

  onRequestPausedEvent = async (event: Protocol.Fetch.RequestPausedEvent) => {
    const { requestId, responseStatusCode, request, responseErrorReason } =
      event
    for (const {
      modifyRequest,
      modifyResponse,
      modifyResponseChunk,
      streamResponse,
      resourceType,
      urlPattern,
      urlPatternRegExp,
    } of this.interceptions.values()) {
      if (resourceType && resourceType !== event.resourceType) continue
      if (urlPattern && !urlPatternRegExp.test(request.url)) continue

      if (!responseStatusCode) {
        // handling a request
        const { delay, headers, method, postData, url, ...modification } =
          (await modifyRequest?.({ event })) ?? {}
        if (delay) await wait(delay)

        if (headers || method || postData || url) {
          await this.#client.send('Fetch.continueRequest', {
            headers,
            method,
            postData,
            url,
            requestId,
            interceptResponse: Boolean(modifyResponse),
          })
        } else if ('errorReason' in modification) {
          await this.#client.send('Fetch.failRequest', {
            requestId,
            errorReason: modification.errorReason,
          })
        } else if (responseErrorReason) {
          await this.#client.send('Fetch.failRequest', {
            requestId,
            errorReason: responseErrorReason,
          })
        } else {
          await this.#client.send('Fetch.fulfillRequest', {
            ...modification,
            requestId,
            body: modification.body
              ? Buffer.from(modification.body).toString('base64')
              : undefined,
            responseCode: modification.responseCode ?? STATUS_CODE_OK,
          })
        }
      } else if (modifyResponse || modifyResponseChunk) {
        const { base64Encoded, body: rawBody } =
          modifyResponseChunk || streamResponse
            ? await this.#streamResponseBody(
                event,
                modifyResponseChunk,
                typeof streamResponse === 'boolean' ? {} : streamResponse,
              )
            : await this.#getResponseBody(event)

        const body =
          base64Encoded && rawBody
            ? Buffer.from(rawBody, 'base64').toString('utf8')
            : rawBody
        const { delay, ...modification } = (await modifyResponse?.({
          body,
          event,
        })) ?? { body }

        if (delay) await wait(delay)

        if ('errorReason' in modification) {
          await this.#client.send('Fetch.failRequest', {
            requestId,
            errorReason: modification.errorReason,
          })
          return
        }

        await this.#client.send('Fetch.fulfillRequest', {
          requestId,
          responseCode: responseStatusCode,
          responseHeaders: event.responseHeaders,
          ...modification,
          body: modification.body
            ? Buffer.from(modification.body).toString('base64')
            : undefined,
        })
      }
    }
  }

  #install() {
    if (this.#isInstalled) return

    this.#client.on('Fetch.requestPaused', this.#requestPausedHandler)
    this.#isInstalled = true
  }

  #uninstall() {
    if (!this.#isInstalled) return

    this.#client.off('Fetch.requestPaused', this.#requestPausedHandler)
    this.#isInstalled = false
  }

  async #getResponseBody(
    event: Protocol.Fetch.RequestPausedEvent,
  ): Promise<{ body: string | undefined; base64Encoded?: boolean }> {
    return (
      this.#client
        .send('Fetch.getResponseBody', { requestId: event.requestId })
        // handle the case of redirects (e.g. 301) and other situations without a body:
        .catch(() => ({ base64Encoded: false, body: undefined }))
    )
  }

  async #streamResponseBody(
    event: Protocol.Fetch.RequestPausedEvent,
    modifyResponseChunk?: ModifyResponseChunkFn,
    { chunkSize }: StreamResponseConfig = {},
  ): Promise<{ body: string | undefined; base64Encoded?: boolean }> {
    const { stream } = await this.#client
      .send('Fetch.takeResponseBodyAsStream', { requestId: event.requestId })
      // handle the case of redirects (e.g. 301) and other situations without a body:
      .catch(() => ({ stream: null }))

    if (!stream) {
      return { body: undefined }
    }

    let body = ''
    let base64Encoded = false

    try {
      // TODO: run loop at most once per XXms
      while (stream) {
        const result = await this.#client.send('IO.read', {
          handle: stream,
          size: chunkSize,
        })
        const {
          data,
          eof,
          base64Encoded: isBase64,
        } = (await modifyResponseChunk?.({ ...result, event })) ?? result

        if (isBase64) {
          base64Encoded = true
        }
        body += data
        if (eof) break
      }
    } finally {
      if (stream) {
        await this.#client.send('IO.close', { handle: stream })
      }
    }
    return { base64Encoded, body }
  }
}
