# -*- coding: utf-8 -*-
"""The real client, behind an injectable opener: what a crates.io answer
means, and which requests carry the token."""

import json
import unittest
import urllib.error

from repo_vet.sources import Client


class Reply(object):
    status = 200
    headers = {}

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class CargoVersions(unittest.TestCase):
    def test_crates_io_request_uses_descriptive_user_agent(self):
        requests = []

        def opener(request, timeout):
            requests.append((request.full_url, request.get_header("User-agent")))
            return Reply(json.dumps({
                "crate": {"newest_version": "1.0.0"},
                "versions": [{"num": "1.0.0"}, {"num": "0.9.0"}],
            }).encode("utf-8"))

        client = Client(opener=opener)
        self.assertEqual(client.cargo_versions("serde"), {"1.0.0", "0.9.0"})
        self.assertEqual(requests[0][0], "https://crates.io/api/v1/crates/serde")
        self.assertIn("repo-vet", requests[0][1])
        self.assertIn("github.com/Furkiozknn/repo-vet", requests[0][1])

    def test_not_found_is_absent(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, None)

        self.assertEqual(Client(opener=opener).cargo_versions("missing-crate"), set())

    def test_forbidden_is_unknown_not_absent(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 403, "forbidden", {}, None)

        self.assertIsNone(Client(opener=opener).cargo_versions("serde"))

    def test_network_error_is_unknown_not_absent(self):
        def opener(request, timeout):
            raise TimeoutError("registry timeout")

        self.assertIsNone(Client(opener=opener).cargo_versions("serde"))

    def test_malformed_success_response_is_unknown(self):
        client = Client(opener=lambda request, timeout: Reply(b"{}"))
        self.assertIsNone(client.cargo_versions("serde"))


class TokenStaysOnGitHub(unittest.TestCase):
    """SECURITY.md says the token goes to api.github.com and nowhere else.

    The redirect tests hold that for a redirect; these hold it for the
    requests repo-vet makes on purpose. A single `auth=True` on a registry
    call would hand the user's GitHub token to PyPI, npm or crates.io, and
    nothing else in the suite would notice.
    """

    def _client(self):
        seen = []

        def opener(request, timeout):
            seen.append((request.full_url, request.get_header("Authorization")))
            return Reply(b"{}")

        return Client(token="t", opener=opener), seen

    def test_registries_never_receive_the_token(self):
        client, seen = self._client()
        client.pypi_versions("requests")
        client.npm_versions("@scope/pkg")
        client.cargo_versions("serde")
        self.assertEqual(seen, [
            ("https://pypi.org/pypi/requests/json", None),
            ("https://registry.npmjs.org/@scope/pkg", None),
            ("https://crates.io/api/v1/crates/serde", None),
        ])

    def test_readme_links_and_the_homepage_never_receive_the_token(self):
        # A URL taken from a README goes out bare even when it points at
        # api.github.com: the README chose it, not repo-vet.
        client, seen = self._client()
        client.status("https://example.org/")
        client.statuses(["https://example.org/a",
                         "https://api.github.com/repos/o/r"])
        self.assertEqual(sorted(seen), [
            ("https://api.github.com/repos/o/r", None),
            ("https://example.org/", None),
            ("https://example.org/a", None),
        ])

    def test_github_api_calls_do_carry_it(self):
        # Without this the two tests above would also pass if the recording
        # opener could not see headers at all.
        client, seen = self._client()
        client.repo("o/r")
        client.readme("o/r")
        client.tags("o/r")
        self.assertEqual([auth for _, auth in seen], ["Bearer t"] * 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
