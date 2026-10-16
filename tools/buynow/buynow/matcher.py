"""Pure text matching, kept free of Playwright so it is trivially testable."""

import re
import unicodedata

_WS = re.compile(r"\s+")


def normalize(text: str | None) -> str:
    """NFKC + collapse whitespace (incl. NBSP / newlines) + casefold.

    'Buy<NBSP>Ticket', ' BUY<newline>TICKET ' and 'buy ticket' all compare equal.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return _WS.sub(" ", text).strip().casefold()


def matches(actual: str | None, expected: str, *, exact: bool = True) -> bool:
    """exact=True: whole label must equal expected (safe default).
    exact=False: expected may appear inside a longer label, e.g. 'BUY TICKET (R석)'."""
    a, e = normalize(actual), normalize(expected)
    if not e:
        return False
    return a == e if exact else e in a
