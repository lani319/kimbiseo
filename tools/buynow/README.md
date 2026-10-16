# buynow

예매 오픈 시각(KST) **10초 전부터 새로고침** → XPath 요소의 라벨이 `BUY TICKET` 인지 확인 → **마우스 클릭**.
Windows 11 기본 브라우저 **Edge** 를 그대로 사용하므로 별도 브라우저 다운로드가 필요 없다.

## 설치 A — Python 없는 PC (권장)

1. GitHub `Actions > buynow-release` 최신 성공 실행에서 **`buynow-windows`** 아티팩트 다운로드
   (태그 `buynow-v*` 를 푸시하면 Releases 에도 올라간다)
2. 압축 해제 → `buynow\buynow.exe` **더블클릭** → URL · XPath · 오픈 시각 · 버튼 글자 입력
   - 또는 `run_example.bat` 값을 고쳐 더블클릭 (exe 가 옆에 있으면 자동으로 exe 사용)
3. 처음 실행 시 SmartScreen 경고(서명 안 된 exe)가 뜨면 `추가 정보 > 실행`

브라우저는 Windows 11 기본 Edge 를 쓰므로 추가 설치는 필요 없다.

## 설치 B — Python 있는 PC (Python 3.10+)

```powershell
cd tools\buynow
pip install -e .
```

## 사용

```powershell
# 1) 로그인 준비: 오픈 수 분 전에 실행 → 뜬 브라우저에서 로그인 (프로필이 저장되어 다음부터 유지)
# 2) 리허설: 클릭 없이 XPath/라벨 매칭만 확인
python -m buynow "https://ticket.example.com/goods/123" "//button[@id='buy']" --dry-run --max-attempts 1 --text "구매하기"

# 3) 실전: 20:00:00 KST 오픈, 19:59:50 부터 1초 간격 새로고침
python -m buynow "https://ticket.example.com/goods/123" "//button[@id='buy']" --at "2026-10-20 20:00:00"
```

`run_example.bat` 을 복사해 값만 바꾸고 더블클릭해도 된다.

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--at` | (즉시 시작) | 오픈 시각, KST 기준 `YYYY-MM-DD HH:MM[:SS]` |
| `--lead` | `10` | 오픈 N초 전부터 새로고침 |
| `--give-up` | `300` | 오픈 N초 후에도 못 누르면 종료 (0 = 무한) |
| `--text` | `BUY TICKET` | 기대 라벨. 대소문자·공백·NBSP·전각 무시 |
| `--contains` | off | `BUY TICKET (R석)` 처럼 라벨에 포함만 돼도 매칭 |
| `--interval` / `--jitter` | `1.0` / `0.2` | 새로고침 간격(로드 시간 포함) + 랜덤 지연. 최소 0.5초 |
| `--timeout` | `2.0` | 새로고침마다 XPath 요소를 기다리는 최대 시간 |
| `--no-sync-clock` | off | 사이트 서버 시간 보정 끄기 (PC 시계 그대로 사용) |
| `--browser` | `msedge` | `msedge` / `chrome` / `chromium` |
| `--browser-path` | - | 웨일 등 Chromium 계열 exe 경로 직접 지정 |
| `--profile` | `~/.buynow/profile` | 로그인 쿠키 저장 위치 |
| `--dry-run` | off | 매칭만 확인, 클릭 안 함 |
| `--exit-after-click` | off | 클릭 후 브라우저 닫기 (기본은 결제 진행하도록 유지) |

## 동작

1. 전용 프로필로 Edge 실행 → URL 접속 (이때 로그인)
2. `--at` 이 있으면 사이트 HTTP `Date` 헤더로 **서버 시계 오차 측정** (±0.5초) → `오픈 - lead` 까지 대기
3. 반복: 새로고침 → XPath 요소 대기 → 라벨 비교 → 보이고 활성화 상태면 `click()`
   - Playwright 클릭 = 요소 중앙으로 실제 마우스 down/up 이벤트 (JS `el.click()` 아님, `isTrusted=true`)
   - 오픈 전 `COMING SOON` / 비활성 버튼은 누르지 않음
4. 클릭 성공 시 브라우저를 열어둔 채 대기 → 직접 좌석·결제 진행 → 창 닫으면 종료

## 주의 (Risk)

- **약관/법**: 대부분의 예매처는 매크로 사용을 약관으로 금지하며 적발 시 예매 취소·계정 정지가 될 수 있다.
  공연법·국민체육진흥법은 매크로로 구매한 표의 **부정판매(재판매)** 를 처벌한다. 본인 관람 목적 1매 범위에서만 쓸 것.
- **대기열(인터파크·멜론·예스24 NOL 등)**: 오픈 시 대기열/보안문자 페이지로 넘어가면 XPath 가 안 잡힌다 — 이 단계는 사람이 처리해야 한다.
- **iframe**: 버튼이 iframe 안에 있으면 XPath 로 못 찾는다 (현재 미지원).
- **시계**: 서버 시간 보정이 실패하면 경고가 뜬다. 그 경우 Windows `설정 > 시간 및 언어 > 지금 동기화` 를 먼저 실행.
- 새로고침 간격을 너무 줄이면 IP 차단될 수 있어 0.5초 미만은 막아뒀다.

## 개발

exe 빌드는 Windows 에서만 가능 (CI: `.github/workflows/buynow-release.yml`). 로컬 Windows 에서 직접 빌드:
`pip install . pyinstaller && pyinstaller --onedir --console --name buynow --paths . packaging/entry.py`

```bash
pip install -e ".[dev]" && playwright install chromium
pytest -v
```
