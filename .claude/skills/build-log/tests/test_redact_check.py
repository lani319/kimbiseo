from redact_check import check, thread_posts

ALLOW = ["ayhlabs.com"]


def errors(text, **kw):
    kw.setdefault("blocklist", [])
    kw.setdefault("identities", set())
    kw.setdefault("allow_domains", ALLOW)
    return [f for f in check(text, **kw) if f.level == "error"]


def test_clean_draft_passes():
    text = "## A안\n### 1/1\n할 일 앱은 열어야 보인다.\nhttps://ayhlabs.com/kimbiseo?utm_source=threads\n"
    assert check(text, blocklist=[], identities=set(), allow_domains=ALLOW) == []


def test_blocklist_is_case_insensitive():
    [f] = errors("우리 ACME 팀에서", blocklist=["acme"])
    assert "acme" in f.message and f.line == 1


def test_git_identity_and_email_and_phone():
    text = "by lani319\ncontact: someone@example.com\n010-1234-5678"
    msgs = [f.message for f in errors(text, identities={"lani319"})]
    assert any("lani319" in m for m in msgs)
    assert any("email" in m for m in msgs)
    assert any("phone" in m for m in msgs)


def test_github_link_blocked_and_missing_utm_warns():
    found = check("https://github.com/lani319/kimbiseo\nhttps://ayhlabs.com/x",
                  blocklist=[], identities=set(), allow_domains=ALLOW)
    assert [f.level for f in found] == ["error", "warn"]


def test_subdomain_allowed_but_lookalike_not():
    assert errors("https://www.ayhlabs.com/a?utm_source=t") == []
    assert len(errors("https://evil-ayhlabs.com/a?utm_source=t")) == 1


def test_allow_terms_override_identity():
    assert errors("필명 lani319", identities={"lani319"}, allow_terms=["LANI319"]) == []


def test_meta_comments_skipped():
    assert errors("<!-- meta: commits=abc author lani319 -->", identities={"lani319"}) == []


def test_threads_length_limit_excludes_blog():
    long = "가" * 501
    text = f"## A안\n### 1/2\n짧다\n### 2/2\n{long}\n## 블로그\n### 소제목\n{long}\n"
    posts = thread_posts(text.splitlines())
    assert [len(b) for _, b in posts] == [2, 501]
    [f] = errors(text)
    assert "501 chars" in f.message and f.line == 4
