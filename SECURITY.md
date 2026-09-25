# Security policy

## Supported versions

Only the latest state of the default branch (`main`) is supported. Fixes go
forward in a new version; old tags are not patched.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.** Use GitHub's
private channel instead: the **Security** tab of this repository, then
**Report a vulnerability**. If that button is not there, open an issue that
says only that you have something to report privately, without details, and
a private channel will be arranged.

A useful report has the commit (`git rev-parse HEAD`), the smallest command
that reproduces it, and what an attacker gains.

This is a one-person project. Expect an acknowledgement within a week.

## What repo-vet touches, stated precisely

It is easier to judge a report against a surface that is written down.

- **No code from the checked repository is run.** repo-vet does not clone,
  install, import or execute anything. It reads text over HTTPS and matches it
  against patterns.
- **The token** (`--token`, `GITHUB_TOKEN` or `GH_TOKEN`) is sent only with
  requests to `api.github.com`, and to wherever GitHub's own API redirects
  them. It is never sent to PyPI, npm, or any URL taken from a README. It is
  never written to the report, the JSON file or the step summary.
- **Hosts contacted:** `api.github.com`, `pypi.org`, `registry.npmjs.org`, the
  repository's homepage and its `github.io` address, and — only for the `web`
  check — the outbound links in the README, up to `--web-limit` of them
  (40 by default). A README therefore decides which URLs repo-vet sends a GET
  to. Skip `web` and `pages` if that matters where you run it.
- **Files written:** only the path given to `--json-out`.
- **The GitHub Action** passes its inputs to the script as environment
  variables, not by `${{ }}` substitution, so an input value is never parsed
  as shell code. Its default token is the job's own `github.token`; for a
  public repository it needs no more than `contents: read`.

## Out of scope

- A finding that is wrong, or a missed one. That is a bug; please open an
  ordinary issue.
- Rate limiting by GitHub or a registry.
