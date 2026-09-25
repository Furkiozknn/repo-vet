"""repo-vet — check what a repository claims against what is actually there.

A README is a promise. `pip install thing` promises the distribution exists.
A workflow badge promises the workflow exists and has run. A relative link
promises the file is in the tree. A tag promises a release. Promises rot
quietly, because the only way to notice is to try them, and nobody tries
their own README twice.

This package tries them.
"""

__version__ = "0.2.0"

from .model import Finding, Report            # noqa: F401
