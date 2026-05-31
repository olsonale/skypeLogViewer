"""Entry point for the packaged (PyInstaller) build.

The package uses relative imports, so PyInstaller needs a top-level script
that imports the package and calls into it.
"""

from skype_log_viewer.__main__ import main

if __name__ == "__main__":
    main()
