"""Peng configuration — environment-driven settings for data paths and runtime behavior.

All data paths default to ``<project_root>/data`` and can be overridden via
environment variables. The ``PENG_DATA_DIR`` variable is the primary override
for the data root directory.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def _env(*names: str) -> str | None:
    """Return the first non-empty value from the given environment variable names."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _path_from_env(names: tuple[str, ...], default: Path) -> Path:
    """Resolve a path from environment variables, falling back to a default."""
    value = _env(*names)
    if not value:
        return default
    return Path(value).expanduser().resolve()


def get_data_dir() -> Path:
    """Return the root data directory for Peng.

    Controlled by ``PENG_DATA_DIR`` (or legacy ``SPIIR_ALT_DATA_DIR``).
    Defaults to ``<project_root>/data``.
    """
    return _path_from_env(("PENG_DATA_DIR", "SPIIR_ALT_DATA_DIR"), ROOT_DIR / "data")


def get_enable_banking_app_id() -> str:
    """Return the Enable Banking application ID from environment."""
    app_id = _env("ENABLEBANKING_APP_ID")
    if not app_id:
        raise RuntimeError("Set ENABLEBANKING_APP_ID before calling Enable Banking")
    return app_id


def get_enable_banking_key_path() -> Path:
    """Return the path to the Enable Banking RSA private key."""
    configured = _env("ENABLEBANKING_PRIVATE_KEY_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return get_data_dir() / "local_secrets" / "enablebanking" / f"{get_enable_banking_app_id()}.pem"


def get_enable_banking_redirect_url() -> str:
    """Return the Enable Banking OAuth redirect URL."""
    url = _env("ENABLEBANKING_REDIRECT_URL")
    if not url:
        raise RuntimeError("Set ENABLEBANKING_REDIRECT_URL for Enable Banking")
    return url

def get_kvitteringer_db_path() -> Path:
    return get_data_dir() / "kvitteringer.db"

def get_kvitteringer_data_dir() -> Path:
    return get_data_dir() / "kvitteringer"

def get_kvitteringer_category_overrides_file() -> Path:
    return get_data_dir() / "kvitteringer-categories.json"

def get_storebox_source_dir() -> Path:
    return get_data_dir() / "storebox-downloads"
