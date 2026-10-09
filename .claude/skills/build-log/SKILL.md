---
name: build-log
description: 이 레포의 커밋·PR을 읽어 필명 빌드인퍼블릭용 쓰레드(Threads) 체인 초안과 블로그 초안을 만든다. 실명·회사명 노출 검사를 통과한 초안만 내놓는다. 사용자가 "빌드 로그", "제작기 써줘", "오늘 커밋으로 쓰레드", "쓰레드 초안", "/build-log", "게시했어"(마킹) 같은 말을 하면 사용한다.
---

# build-log

커밋 → 쓰레드 초안. 목적은 **콘텐츠 제작 시간 절감**이고, 게시는 항상 사람이 한다.

경로 (레포 루트 기준):
- 스크립트: `.claude/skills/build-log/scripts/`
- 규칙: `.claude/skills/build-log/references/style.md` — 초안 쓰기 전에 반드시 읽는다
- 로컬 전용(gitignore): `.build-log/config.json`, `.build-log/drafts/`, `.build-log/metrics.csv`, `.build-log/state.json`

## 절대 규칙
- 이 레포는 **공개**다. 블락리스트·초안·지표를 추적되는 파일에 쓰지 않는다. `.build-log/` 밖으로 옮기지 않는다.
- `redact_check.py` 를 통과하지 못한 초안은 사용자에게 "게시 가능"으로 내놓지 않는다. 통과시키려고 config(블락리스트·허용 도메인)를 고치지 않는다 — 초안을 고친다.
- 커밋·diff로 확인되지 않는 사실을 지어내지 않는다 (style.md "사실 규칙").
- 자동 게시하지 않는다.

## 절차

### 0. 설정 확인 (최초 1회)
`.build-log/config.json` 이 없으면 `config.example.json` 을 복사해 만들고, 사용자에게 묻는다:
- 필명
- 블락리스트: 회사명(약칭·영문 포함), 실명, 팀/사내 서비스명, 동료 이름
- 링크: 위젯별 ayhlabs.com 소개 페이지 URL
답을 받으면 `.build-log/config.json` 에만 쓴다.

### 1. 재료 수집
```bash
python .claude/skills/build-log/scripts/collect.py            # 마지막 게시 이후
python .claude/skills/build-log/scripts/collect.py --since <sha>
```
커밋이 없으면 그렇게 말하고 끝낸다 (억지로 쓰지 않는다).

### 2. 스토리 고르기
커밋들을 스토리 1~3개로 묶는다. 스토리마다 style.md 의 이야기 유형 하나를 고른다. 사용자가 주제를 지정했으면 그것을 따른다.
`.build-log/metrics.csv` 가 있으면 `link_clicks/views` 상위 훅 3개를 참고 예시로 쓴다.

### 3. 초안 쓰기
스토리마다 파일 하나: `.build-log/drafts/<YYYY-MM-DD>-<slug>.md`

```markdown
# <스토리 제목>
<!-- meta: commits=<sha,...> type=<유형> campaign=<slug> -->
<!-- hooks: A=<점수>/10 <감점이유> | B=… | C=… -->

## A안
### 1/3
…
### 2/3
…
### 3/3
… <링크+UTM>
[직접 쓰기: 한 문장]

## B안
### 1/1 …
## C안
…

## 블로그
(ayhlabs.com/네이버 블로그용 600~1200자. 쓰레드와 문장 중복 최소화, 소제목 2~3개)
```
- A/B/C 는 **훅과 구성이 달라야** 한다 (같은 글의 표현만 바꾸지 않는다).
- 훅은 style.md 채점표로 매기고 7점 미만은 다시 쓴다.

### 4. 노출 검사
```bash
python .claude/skills/build-log/scripts/redact_check.py .build-log/drafts/<file>.md
```
ERROR 가 0이 될 때까지 초안을 고친다. WARN(UTM 누락)도 고친다.

### 5. 전달
사용자에게: 파일 경로, 추천안(A/B/C 중 하나와 이유), `[확인 필요]`·`[링크 필요]`·`[직접 쓰기]` 항목 목록, 게시 팁(퇴근 후 시간대 예약, 링크는 마지막 포스트만).

### 6. 게시 후
사용자가 게시했다고 하면:
```bash
python .claude/skills/build-log/scripts/collect.py --mark <마지막으로 다룬 커밋 sha>
```
그리고 `.build-log/metrics.csv` 에 행을 추가한다 (없으면 헤더부터):
`date,draft,variant,hook,views,likes,replies,link_clicks,waitlist` — 수치는 비워두고 1주 뒤 사용자에게 채워달라고 한다.
