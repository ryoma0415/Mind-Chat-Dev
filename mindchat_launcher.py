from __future__ import annotations

"""
Entry script for PyInstaller builds.

PyInstaller expects a top-level script without package-relative imports.
This launcher simply delegates to the package entry point defined in app.main.
"""

from app.main import main


if __name__ == "__main__":
    main()
