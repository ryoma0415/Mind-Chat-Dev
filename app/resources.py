from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _package_root() -> Path:
    """Return the base directory for bundled/static resources."""

    base = getattr(sys, "_MEIPASS", None)
    if base:
        # PyInstaller で固めた場合は一時展開ディレクトリを指す
        return Path(base).resolve()
    return Path(__file__).resolve().parent.parent


def resource_path(*relative_parts: str) -> Path:
    """Resolve a resource path that works for PyInstaller bundles as well."""

    if not relative_parts:
        return _package_root()
    # アプリ直下の screen_display などにアクセスするときに使う
    return _package_root().joinpath(*relative_parts)
