"""Gate a draft before it leaves the machine: identity leaks and Threads limits.

Fails (exit 1) on:
  - blocklist terms from .build-log/config.json (company, real name, ...)
  - git author names/emails of this repo, and github.com/<author> links
  - any email address or Korean phone number
  - links to domains not in allow_domains
  - a Threads post (### block under a 쓰레드/variant section) over 500 chars
Warns on site links without utm_source.

    python redact_check.py .build-log/drafts/2026-10-09-foo.md
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

THREADS_LIMIT = 500
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)01[016789][-. ]?\d{3,4}[-. ]?\d{4}(?!\d)")
URL = re.compile(r"https?://[^\s)>\]]+")
DEFAULT_ALLOW = ["ayhlabs.com"]


@dataclass
class Finding:
    line: int
    level: str  # "error" | "warn"
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper()} L{self.line}: {self.message}"


def load_config(root: Path) -> dict:
    p = root / ".build-log" / "config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def git_identities(root: Path) -> set[str]:
    try:
        out = subprocess.run(["git", "log", "--format=%an%n%ae%n%cn%n%ce"], cwd=root,
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    # Bots/tools are not identifying; keep the human ones.
    return {s.strip() for s in out.splitlines()
            if s.strip() and not re.search(r"noreply|github|claude|anthropic", s, re.I)}


def _domain_allowed(host: str, allow: list[str]) -> bool:
    host = host.lower().removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in allow)


def thread_posts(lines: list[str]) -> list[tuple[int, str]]:
    """(start_line, text) for every '### ' post block outside the 블로그 section."""
    posts, cur, start, in_blog = [], None, 0, False
    for i, ln in enumerate(lines, 1):
        if ln.startswith("## "):
            in_blog = "블로그" in ln or "blog" in ln.lower()
        if ln.startswith(("## ", "### ")) and cur is not None:
            posts.append((start, "\n".join(cur).strip()))
            cur = None
        if ln.startswith("### ") and not in_blog:
            cur, start = [], i
        elif cur is not None:
            cur.append(ln)
    if cur is not None:
        posts.append((start, "\n".join(cur).strip()))
    return posts


def check(text: str, *, blocklist: list[str], identities: set[str], allow_domains: list[str],
          allow_terms: list[str] = ()) -> list[Finding]:
    findings: list[Finding] = []
    allowed = {t.lower() for t in allow_terms}
    terms = [t for t in [*blocklist, *identities] if t and t.lower() not in allowed]
    lines = text.splitlines()

    for n, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("<!--"):
            continue  # meta comments are stripped before posting
        low = ln.lower()
        for t in terms:
            if t.lower() in low:
                findings.append(Finding(n, "error", f"blocked term {t!r}"))
        for m in EMAIL.finditer(ln):
            findings.append(Finding(n, "error", f"email address {m.group()!r}"))
        for m in PHONE.finditer(ln):
            findings.append(Finding(n, "error", f"phone number {m.group()!r}"))
        for m in URL.finditer(ln):
            u = urlparse(m.group())
            if not _domain_allowed(u.hostname or "", allow_domains):
                findings.append(Finding(n, "error", f"link to non-allowed domain {u.hostname!r}"))
            elif "utm_source=" not in (u.query or ""):
                findings.append(Finding(n, "warn", f"link without utm_source: {m.group()}"))

    for start, body in thread_posts(lines):
        if len(body) > THREADS_LIMIT:
            findings.append(Finding(start, "error", f"Threads post is {len(body)} chars (> {THREADS_LIMIT})"))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft", type=Path)
    args = ap.parse_args(argv)

    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=args.draft.resolve().parent,
                               capture_output=True, text=True, check=True).stdout.strip())
    cfg = load_config(root)
    findings = check(
        args.draft.read_text(encoding="utf-8"),
        blocklist=cfg.get("blocklist", []),
        identities=git_identities(root),
        allow_domains=cfg.get("allow_domains", DEFAULT_ALLOW),
        allow_terms=cfg.get("allow_terms", []),
    )
    for f in findings:
        print(f)
    errors = sum(f.level == "error" for f in findings)
    print(f"{errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
