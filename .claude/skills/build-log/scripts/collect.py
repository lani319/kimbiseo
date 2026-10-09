"""Collect repo activity since the last published build log, as JSON for drafting.

Privacy by construction: author names/emails are never emitted, and commit
trailers (Co-Authored-By, Signed-off-by, session URLs) are stripped.

    python collect.py                 # commits since last --mark (or all)
    python collect.py --since <sha>   # explicit range start
    python collect.py --mark HEAD     # record HEAD as published
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EXCLUDE_PATHS = (".build-log", "research_notes", "reports")
TRAILER = re.compile(r"^[A-Za-z][A-Za-z-]*:\s|^https?://\S+$")
CONVENTIONAL = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?!?:\s*(?P<subject>.+?)(?:\s+\(#(?P<pr>\d+)\))?$")
MAX_PATCH_LINES = 120


def git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", check=True
    )
    return out.stdout


def repo_root(start: Path) -> Path:
    return Path(git(start, "rev-parse", "--show-toplevel").strip())


def state_path(root: Path) -> Path:
    return root / ".build-log" / "state.json"


def load_since(root: Path) -> str | None:
    p = state_path(root)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("last_commit")
    return None


def mark(root: Path, rev: str) -> str:
    sha = git(root, "rev-parse", rev).strip()
    p = state_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"last_commit": sha}, indent=2), encoding="utf-8")
    return sha


def clean_body(body: str) -> str:
    lines = [ln for ln in body.strip().splitlines() if not TRAILER.match(ln.strip())]
    return "\n".join(lines).strip()


def _path_ok(path: str) -> bool:
    return not path.startswith(EXCLUDE_PATHS)


def collect(root: Path, since: str | None, until: str = "HEAD") -> dict:
    rev_range = f"{since}..{until}" if since else until
    raw = git(root, "log", "--reverse", "--date=short", "--format=%H%x1f%ad%x1f%s%x1f%b%x1e", rev_range)
    commits = []
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, date, subject, body = rec.split("\x1f")
        m = CONVENTIONAL.match(subject)
        files = []
        for row in git(root, "show", "--numstat", "--format=", sha).splitlines():
            parts = row.split("\t")
            if len(parts) == 3 and _path_ok(parts[2]):
                files.append({"path": parts[2], "added": parts[0], "deleted": parts[1]})
        patch = git(root, "show", "--format=", "--unified=1", sha, "--", ".",
                    *[f":(exclude){p}" for p in EXCLUDE_PATHS]).splitlines()
        commits.append({
            "sha": sha[:7],
            "date": date,
            "type": m.group("type") if m else None,
            "subject": m.group("subject") if m else subject,
            "pr": int(m.group("pr")) if m and m.group("pr") else None,
            "body": clean_body(body),
            "files": files,
            "patch_excerpt": "\n".join(patch[:MAX_PATCH_LINES]),
            "patch_truncated": len(patch) > MAX_PATCH_LINES,
        })
    return {"range": rev_range, "head": git(root, "rev-parse", "--short", until).strip(), "commits": commits}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", help="start revision (exclusive); default: last --mark")
    ap.add_argument("--mark", metavar="REV", help="record REV as the last published commit and exit")
    ap.add_argument("--repo", default=".", help="path inside the repository")
    args = ap.parse_args(argv)

    root = repo_root(Path(args.repo))
    if args.mark:
        print(f"marked {mark(root, args.mark)[:7]} as published")
        return 0
    data = collect(root, args.since or load_since(root))
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
