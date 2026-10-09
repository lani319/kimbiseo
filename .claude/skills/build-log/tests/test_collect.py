import json
import subprocess

import pytest

from collect import clean_body, collect, load_since, mark


def run(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    run(tmp_path, "git", "init", "-q", "-b", "main")
    run(tmp_path, "git", "config", "user.name", "Real Name")
    run(tmp_path, "git", "config", "user.email", "real@example.com")
    (tmp_path / "a.py").write_text("x = 1\n")
    run(tmp_path, "git", "add", ".")
    run(tmp_path, "git", "commit", "-q", "-m", "feat: 위젯 추가 (#1)\n\n본문 설명\n\nCo-Authored-By: Bot <b@x.io>\nClaude-Session: https://claude.ai/code/s")
    (tmp_path / "a.py").write_text("x = 2\n")
    (tmp_path / "research_notes").mkdir()
    (tmp_path / "research_notes" / "n.md").write_text("secret\n")
    run(tmp_path, "git", "add", ".")
    run(tmp_path, "git", "commit", "-q", "-m", "fix(ui): 버그 수정")
    return tmp_path


def test_collect_parses_and_strips_identity(repo):
    data = collect(repo, since=None)
    first, second = data["commits"]
    assert (first["type"], first["subject"], first["pr"], first["body"]) == ("feat", "위젯 추가", 1, "본문 설명")
    assert (second["type"], second["subject"], second["pr"]) == ("fix", "버그 수정", None)
    assert [f["path"] for f in second["files"]] == ["a.py"]  # research_notes excluded
    dumped = json.dumps(data, ensure_ascii=False)
    for leak in ("Real Name", "real@example.com", "b@x.io", "claude.ai", "secret"):
        assert leak not in dumped


def test_mark_then_collect_only_new(repo):
    assert load_since(repo) is None
    sha = mark(repo, "HEAD~1")
    assert load_since(repo) == sha
    data = collect(repo, since=load_since(repo))
    assert [c["subject"] for c in data["commits"]] == ["버그 수정"]


def test_clean_body_drops_trailers_and_bare_urls():
    assert clean_body("설명\nSigned-off-by: A <a@b>\nhttps://x.y/z\n") == "설명"
