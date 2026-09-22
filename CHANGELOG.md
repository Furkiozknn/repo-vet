# Changelog

Format close to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

Every number here is measured. An unmeasured claim does not go in this file.

---

## [0.1.0] — 2026-09-22

First release.

### Checks

Six, all over the GitHub API, no clone:

- **install** — distribution names in fenced code blocks, against PyPI and npm
- **links** — relative links and images, against the repository tree
- **badges** — workflow-status badges, against the workflow files and their runs
- **release** — newest tag without a Release; a declared version never tagged
- **web** — outbound links, reporting 404 and 410 only
- **pages** — a dead homepage, or a live GitHub Pages site left unadvertised

### Output

Text, `--json`, and `--markdown` for a GitHub step summary. Exit code `0` clean,
`1` findings, `2` usage. Warnings do not fail a run unless `--fail-on any`.

### Shipped alongside

A composite GitHub Action (`action.yml`) that installs the tool from its own
checkout, so it works before the distribution is on PyPI and the pinned version
is the version that runs.

### Measured

- **70 tests**, standard library only, no network in any of them
  (CI log: `=== 70 tests passed ===`), on Python 3.9 through 3.13.
- Checked against `psf/requests` and `astral-sh/uv`: clean, no false positives.
- The `install` check was written after a real failure: a sibling repository's
  README opened with `uv tool install ptm-cli` for a distribution that had never
  been published, so a first-time visitor's first command died with
  *"ptm-cli was not found in the package registry"*.
