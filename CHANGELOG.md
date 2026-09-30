# Changelog

Format close to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

Every number here is measured. An unmeasured claim does not go in this file.

---

## [Unreleased]

First-run experience; no behaviour, exit code or output contract changed.

### Changed

- A slug that is not `OWNER/NAME` still exits `2`, and now prints the command
  that would have worked: a pasted `https://github.com/...` or clone URL
  becomes `repo-vet OWNER/NAME`, a trailing slash is dropped, a folder (`.`,
  `../x`) is told that repo-vet reads over the API and does not scan folders.
- `repo-vet` with no arguments prints an example and points at `--help`.
- `--help` carries examples, the exit-code table and the "no clone, no local
  folder" note; `--timeout` is described.
- "no such repository" now says a private repository needs `--token`; "GitHub
  could not be read" names the likely causes (no network, a proxy, an outage);
  an unreadable repository prints `nothing was looked at: ...` instead of
  `- *: skipped (...)`.
- README first screen: definition, one install command, a recorded terminal
  demo, when to use it and when not. The 15-second reel and the older
  `assets/demo.gif` are gone: nothing in the repository could regenerate them.

### Added

- `scripts/demo-uret.py` and `scripts/demo-kayit.js` record the demo from real
  runs into `docs/demo/` (`komutlar.txt` is the record).
- 16 tests for the above (`tests/test_first_run.py`), including one that parses
  every command the README shows.

### Fixed

- `ActionStep.test_exit_code_passes_through_and_findings_are_written` failed on
  Windows only: bash ate the backslashes of the interpreter path in the stub.
  The suite is now 173 tests, all passing there as well as on Linux.

---

## [0.2.0] — 2026-09-25

Minor version, because two behaviours change on purpose: an unreadable
repository now exits `3` instead of `0`, and the Action run on a pull request
reads the pull request's README instead of the default branch's.

### Added

- `--json-out PATH` writes the machine-readable report to a file while the
  console keeps whatever it was producing — text, `--markdown`, either.
- `--ref REF` reads the README, the tree and the manifest at a branch, tag or
  commit instead of the default branch. The ref is resolved to one commit
  first, so every file comes from the same snapshot, and a ref that does not
  exist is reported as `not checked` (exit `3`), not as a repository without
  a README.
- Action input `ref`, and output `report` (the path of the JSON report).
- Exit code `3`: a repository could not be read at all. See *Fixed*.
- `SECURITY.md`, `CONTRIBUTING.md`, a pull request template, and Dependabot
  for the workflow actions.

### Changed

- **The GitHub Action now scans once instead of three times.** It used to run
  the tool once for the JSON, once for the job summary and once for the exit
  code, and every pass re-checked all the outbound links. The cost was the
  smaller half of the problem: three passes over a flaky network can disagree,
  so the summary could say "no findings" while the third pass failed the job,
  with nothing in the output to explain the contradiction. One pass now
  produces the file, the summary and the exit code.
- A rate limit now says which limit it was (60 an hour without a token, or
  this token's own) and when it resets, and only asks for a token when none
  was given. A token GitHub rejects (401) is named instead of reported as
  "GitHub could not be read".
- A GitHub API request that times out or gets a 500/502/503/504 is asked once
  more after a second. Rate limits, 404s and outbound links are never retried.
- Every slug is validated before the first request, so a typo at the end of a
  `--from-file` list fails in a second instead of after the whole scan. A
  slug is now held to the characters GitHub allows: `o/..`, `o/r?x=1` or
  `o/r/contents` used to go into an API URL, with the token, and ask GitHub
  for something other than a repository.
- **The Action checks the commit under test.** With no `ref` given and the
  repository being the one running the workflow, it reads the README at
  `GITHUB_SHA`: on a pull request, the merge result. Before, a pull request
  that broke a link was vetted against `main` and passed.
- **The Action no longer changes your job's Python.** It used
  `actions/setup-python`, which in a composite action puts its 3.12 first on
  `PATH` for every later step of the caller's job. It now installs into a
  venv of its own under `RUNNER_TEMP`, and writes `repo-vet.json` there
  instead of into your checkout.
- Python 3.14 is tested and declared. CI actions moved off the deprecated
  Node 20 majors (`checkout@v5`, `setup-python@v6`, `upload-artifact@v6`,
  `download-artifact@v7`).

### Fixed

- A relative link to a dotfile or dot-directory (`.github/workflows/ci.yml`,
  `.env.example`) lost its leading dot and was reported missing as an error.
- **A repository nobody could read passed as clean.** A mistyped slug, a rate
  limit, a rejected token or GitHub being down printed `clean (0 checks)` —
  `Clean. 0 checks ran: .` in the step summary — and exited `0`, so the Action
  gave CI a green tick for an audit that never happened. It now prints
  `not checked` with the reason and exits `3` (still `0` under
  `--fail-on none`). The JSON report keeps its shape.
- **An unreadable tag list read as "never tagged".** `tags()` folded a
  timeout or a rate limit into an empty list, and the release check then told
  a project it had never shipped. Unknown is now `None`, and the check stays
  quiet. `releases()` likewise.
- **A README that could not be read was reported as missing.** A rate limit,
  a timeout or a 5xx on the README printed "the repository has no README".
  The client now tells "not there" (404) from "could not ask", for the README
  and for manifests alike.
- **A check that could not read its input still counted as having run.** The
  release check with an unreadable `pyproject.toml`, tag list or release list
  returned no findings and went into the "ran" column, so the report could
  say `clean` on its behalf. It now goes into *Not checked* with the reason,
  and a run in which nothing requested could be read exits `3`.
- "clean (1 checks)" is "clean (1 check)".
- **The token followed redirects to any host.** urllib copies every header,
  `Authorization` included, onto a redirected request. The client now drops
  it whenever a redirect leaves the origin (host, port or scheme).
- **The Action lost its `findings` output exactly when there were findings.**
  Actions runs the step with `bash -e`, so a non-zero exit from `repo-vet`
  ended the script before the count was written. The inputs also reached the
  script by `${{ }}` substitution, where a value is shell code; they now
  arrive as environment variables.

### Measured

**157 tests**, standard library only, no network in any of them, on Python
3.9 through 3.14 (`python3 -m pytest tests -q` → `157 passed`).

---

## [0.1.0] — 2026-09-22

Run against twenty-nine public repositories that disagree with each other
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
The corpus run on 22 September 2026: **4 findings across 29 repositories, 1
of them an error**, all four verified by hand.

---

### Before the corpus run

The first cut, as it stood before it was checked against the corpus. The
section above and this one were released together as `v0.1.0`: the corpus
work was once headed `0.2.0`, but the code never declared that version and no
such tag exists.

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
