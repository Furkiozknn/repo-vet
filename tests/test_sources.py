# -*- coding: utf-8 -*-
"""The real crates.io client stays isolated behind an injectable opener."""

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
