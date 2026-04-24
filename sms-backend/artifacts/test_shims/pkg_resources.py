"""Minimal pkg_resources shim for local test execution.

This workspace venv has a broken setuptools/pkg_resources install, but
`rest_framework_simplejwt` only imports `DistributionNotFound` and
`get_distribution` to populate `__version__`.

We keep this shim outside the application packages and inject it through
`PYTHONPATH` only for ad hoc verification commands.
"""

from importlib.metadata import PackageNotFoundError, version


class DistributionNotFound(Exception):
    """Compatibility exception for callers expecting pkg_resources."""


class _Distribution:
    def __init__(self, package_name: str):
        self.project_name = package_name
        try:
            self.version = version(package_name)
        except PackageNotFoundError as exc:
            raise DistributionNotFound(str(exc)) from exc


def get_distribution(package_name: str) -> _Distribution:
    return _Distribution(package_name)
