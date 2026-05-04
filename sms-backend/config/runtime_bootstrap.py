from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def ensure_pkg_resources_compat() -> None:
    """Load a local shim when the venv's pkg_resources install is broken.

    Some local environments in this workspace expose ``pkg_resources`` as an
    empty namespace package, which breaks ``rest_framework_simplejwt`` during
    Django startup. In healthy environments we leave setuptools untouched; in
    broken ones we swap in the lightweight compatibility shim already checked
    into this repo.
    """

    try:
        import pkg_resources  # type: ignore

        if all(
            hasattr(pkg_resources, attr)
            for attr in ("DistributionNotFound", "get_distribution")
        ):
            return
    except Exception:
        pass

    shim_path = Path(__file__).resolve().parent.parent / "artifacts" / "test_shims" / "pkg_resources.py"
    spec = importlib.util.spec_from_file_location("pkg_resources", shim_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load pkg_resources shim from {shim_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules["pkg_resources"] = module
