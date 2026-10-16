"""PyInstaller entry point (kept outside the package so `buynow` imports cleanly)."""

import sys

from buynow.cli import main

sys.exit(main())
