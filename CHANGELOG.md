# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Changed

- Formatted the Python source with Black.
- Normalized import ordering with isort.
- Corrected PEP 8 whitespace, indentation, quoting, and `None` comparison style.
- Preserved the existing public camelCase APIs to avoid breaking current callers.
- Git commits for updates are now signed with GPG.
- Added a cached JPEG artwork proxy for formats such as WebP, with download,
  image-size, redirect, and private-address protections.
- Added channel-level iTunes artwork, News category, non-explicit status, and
  episodic show type metadata.

### Validation

- Python bytecode compilation, formatter, import-order, pycodestyle, whitespace,
  and focused utility smoke checks pass.
- **Not fully tested:** the application has not undergone end-to-end or live Podimo
  API testing. The artwork and feed test suite passes, and the application starts
  successfully with the configured Hypercorn server.
