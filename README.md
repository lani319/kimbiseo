# ayhlabs

[ayhlabs.com](https://ayhlabs.com) 에 올리는 위젯 · 앱 · 웹사이트 소스를 모아두는 모노레포.

## 구조

```
widgets/            # 독립 실행형 위젯 (각자 자체 의존성 · 테스트 · CI)
  kimbiseo/         # 김비서 — 바탕화면 업무 스케줄 위젯 (Python/tkinter)
tools/              # 개인용 CLI 도구
  ticketing/        # 예매 오픈 시각 보조 (버튼 클릭 → 날짜·회차 선택 후 사람에게 핸드오프)
sites/              # 웹사이트 (예정: ayhlabs.com)
.github/workflows/  # 프로젝트별 워크플로, paths 필터로 변경된 프로젝트만 실행
```

| 프로젝트 | 설명 | 상태 |
|---|---|---|
| [김비서](widgets/kimbiseo) | 업무명 · 기한 · 담당자를 D-Day 순으로 보여주는 always-on-top 위젯 | [![kimbiseo](https://github.com/lani319/kimbiseo/actions/workflows/kimbiseo.yml/badge.svg)](https://github.com/lani319/kimbiseo/actions/workflows/kimbiseo.yml) |
| [ticketing](tools/ticketing) | 예매 오픈 시각에 맞춰 날짜·회차까지 자동 선택, 이후 사람에게 핸드오프 | [![ticketing](https://github.com/lani319/kimbiseo/actions/workflows/ticketing.yml/badge.svg)](https://github.com/lani319/kimbiseo/actions/workflows/ticketing.yml) |

## 규칙

- 프로젝트는 서로 import 하지 않는다. 공유가 필요해지면 `packages/` 로 분리한다.
- 새 프로젝트 = 디렉터리 + `README.md` + 테스트 + `.github/workflows/<name>.yml` (paths 필터 필수).
- 커밋 메시지: `<type>: <subject>` (feat, fix, refactor, ci, docs, chore)
