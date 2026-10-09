# ayhlabs

[ayhlabs.com](https://ayhlabs.com) 에 올리는 위젯 · 앱 · 웹사이트 소스를 모아두는 모노레포.

## 구조

```
widgets/            # 독립 실행형 위젯 (각자 자체 의존성 · 테스트 · CI)
  kimbiseo/         # 김비서 — 바탕화면 업무 스케줄 위젯 (Python/tkinter)
sites/              # 웹사이트 (예정: ayhlabs.com)
.claude/skills/     # 레포 전용 Claude Code 스킬
  build-log/        # 커밋 → 쓰레드·블로그 초안 (노출 검사 포함)
.github/workflows/  # 프로젝트별 워크플로, paths 필터로 변경된 프로젝트만 실행
```

| 프로젝트 | 설명 | 상태 |
|---|---|---|
| [김비서](widgets/kimbiseo) | 업무명 · 기한 · 담당자를 D-Day 순으로 보여주는 always-on-top 위젯 | [![kimbiseo](https://github.com/lani319/kimbiseo/actions/workflows/kimbiseo.yml/badge.svg)](https://github.com/lani319/kimbiseo/actions/workflows/kimbiseo.yml) |
| [build-log](.claude/skills/build-log) | 커밋·PR을 필명 빌드인퍼블릭 쓰레드 초안으로 바꾸는 스킬 | [![build-log](https://github.com/lani319/kimbiseo/actions/workflows/build-log.yml/badge.svg)](https://github.com/lani319/kimbiseo/actions/workflows/build-log.yml) |

## 규칙

- 프로젝트는 서로 import 하지 않는다. 공유가 필요해지면 `packages/` 로 분리한다.
- 새 프로젝트 = 디렉터리 + `README.md` + 테스트 + `.github/workflows/<name>.yml` (paths 필터 필수).
- 공개 레포: 회사명·실명·초안·지표 등 민감 데이터는 `.build-log/` 등 gitignore 경로에만 둔다.
- 커밋 메시지: `<type>: <subject>` (feat, fix, refactor, ci, docs, chore)
