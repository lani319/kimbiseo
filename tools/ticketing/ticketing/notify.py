"""Get the human's attention at hand-off time."""
from __future__ import annotations

import sys


def alert(message: str) -> None:
    print(f"\a\n>>> {message}\n", flush=True)
    if sys.platform == "win32":
        try:
            import winsound

            for _ in range(3):
                winsound.Beep(1500, 200)
        except Exception:
            pass
