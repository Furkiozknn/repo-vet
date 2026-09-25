# Contributing to repo-vet

Thanks for looking. repo-vet is small on purpose, and the rules below are what
keep it trustworthy.

## Run it

```bash
git clone https://github.com/Furkiozknn/repo-vet
cd repo-vet
PYTHONPATH=. python -m unittest discover -s tests -p "test_*.py"   # what CI runs
python -m repo_vet psf/requests --skip web                         # a real run
```

No dependencies to install. `python -m pytest tests -q` runs the same suite if
you have pytest.

## The rules a change is held to

- **No runtime dependencies.** A tool that audits other projects has no
  business widening its own supply chain. Standard library only.
- **No test touches the network.** Everything that goes out goes through
  `repo_vet/sources.py`; tests replace it with `tests/fakes.py`. A new
  `Client` method needs a matching fake method.
- **Unknown is not absent.** A timeout, a rate limit or a 5xx is never a
  finding and never a pass. Return `None` (or `(None, False)`) from the
  client, and raise `checks.NotChecked(reason)` from a check that could not
  see what it needs.
- **A new rule comes with the repository that motivated it.** If a real
  repository produced a false positive, name it in the test.
- **A bug fix starts with a test that fails without it.**

## Pull requests

Say what changed, why, and how you verified it: the command and the number
it printed, not "tests pass". The template asks for exactly that. Security
problems go through [SECURITY.md](SECURITY.md), not a public issue.
