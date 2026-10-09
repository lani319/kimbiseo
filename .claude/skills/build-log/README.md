# build-log (Claude Code skill)

이 레포의 커밋·PR을 읽어 **필명 빌드인퍼블릭용 쓰레드 체인 + 블로그 초안**을 만든다.
사용: Claude Code에서 `/build-log` 또는 "오늘 커밋으로 쓰레드 써줘".

| 파일 | 역할 |
|---|---|
| `SKILL.md` | 절차 (수집 → 스토리 → 초안 A/B/C → 노출 검사 → 전달 → 게시 후 마킹) |
| `references/style.md` | 문체·사실 규칙·훅 채점표·비틀기 원칙 |
| `scripts/collect.py` | 마지막 게시 이후 커밋을 JSON으로 (작성자·트레일러 제거) |
| `scripts/redact_check.py` | 블락리스트·git 작성자·이메일·전화·비허용 링크·500자 초과 검사 |
| `config.example.json` | 로컬 설정 예시 → `.build-log/config.json` 으로 복사 |

**공개 레포 주의**: 블락리스트(회사명·실명), 초안, 지표는 전부 `.build-log/`(gitignore)에만 둔다.

```bash
pytest .claude/skills/build-log/tests
```
