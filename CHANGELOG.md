# Changelog

Format close to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

Every number here is measured. An unmeasured claim does not go in this file.

---

## [0.2.0] — 2026-09-22

Run against thirty public repositories that disagree with each other
([`corpus.txt`](corpus.txt)). Every false positive it produced is now a
named test, and every rule it broke is now narrower.

### Fixed — three rules that real repositories disproved

- **"The newest tag has no Release"** is gone. The tags API promises no
  order and duly reported `v0.1.16` as the newest tag of `tiangolo/fastapi`
  and `wincolor-0.1.6` as `BurntSushi/ripgrep`'s. The release check now
  anchors on the version the manifest declares, which needs no ordering.
- **"A declared version should be tagged"** is gone too. A repository
  between releases declares the version it is working towards —
  `pallets/flask` says `3.2.0.dev`, `astral-sh/ruff` says `0.16.8`,
  `prettier` says `3.10.0-dev`. What is left: a project that declares a
  finished version and has never tagged anything, and a tag carrying the
  declared version while every other tag got a Release.
- **A missing relative link is no longer always an error.** A target with a
  file extension still is. A route like `tutorial/` — how `tiangolo/fastapi`
  links into its documentation site — is a warning: it really does 404 on
  GitHub, and it is the author's call.

### Fixed — findings invented out of thin air

- A registry that could not be reached read as "not published". A 403, a
  rate limit or a timeout now produces silence instead of an accusation.
- A truncated file tree read as missing files. `torvalds/linux` returns
  71,638 paths and a flag saying there are more; the link and badge checks
  now step aside and the report says so.
- Markdown links and install commands inside fenced code blocks were treated
  as promises. They are examples.
- Percent-encoded paths (`docs/my%20guide.md`) and parent-directory links
  (`../sibling`) were reported as missing.
- A GitHub rate limit was reported as "no such repository".

### Added

- `--from-file`, for running a list of repositories in one go.
- [`corpus.txt`](corpus.txt), the list itself, with the expected result.
- Outbound links are checked in parallel; a link-heavy README went from
  minutes to seconds.

### Measured

**97 tests**, standard library only, no network in any of them
(CI log: `=== 97 tests passed ===`), on Python 3.9 through 3.13.
The corpus run on 22 September 2026: **4 findings across 30 repositories, 1
of them an error**, all four verified by hand.

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
