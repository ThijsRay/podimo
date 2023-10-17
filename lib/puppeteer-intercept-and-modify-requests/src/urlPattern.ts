import escapeRegExp from 'escape-string-regexp'

export const getUrlPatternRegExp = (urlPattern: string) =>
  new RegExp(
    escapeRegExp(urlPattern)
      .replace(/(?<!\\)\\\*/g, '.*')
      .replace(/\\{3}\*/g, '\\*')
      .replace(/(?<!\\)\\\?/g, '.{1}')
      .replace(/\\{3}\?/g, '\\?'),
  )
