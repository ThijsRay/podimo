import type { ScaffoldConfig } from '@niieani/scaffold'

const config: ScaffoldConfig = {
  module: '@niieani/scaffold',
  drivers: ['babel', 'eslint', 'jest', 'prettier', 'typescript'],
  settings: {
    node: true,
    engineTarget: 'node',
    codeTarget: 'es2018',
  },
}

export default config
