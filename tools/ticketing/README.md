# ticketing — 오픈 시각 예매 보조 도구

예매 오픈 시각에 맞춰 **예매 버튼 클릭 → 날짜 선택 → 회차 선택**까지만 자동으로 처리하고, 그 뒤는 사람에게 넘깁니다.

| 단계 | 담당 |
|---|---|
| 로그인 / 본인 인증 | **사람** |
| 서버 시간 동기화, 오픈 대기, 버튼 활성화 감지 | 자동 |
| 예매 버튼 클릭 (팝업 창이면 따라감) | 자동 |
| 날짜·회차 선택 (우선순위대로, 매진이면 다음 후보) | 자동 |
| 보안문자 / 좌석 / 결제 | **사람** (알림음과 함께 넘겨줌) |

## 하지 않는 것 (의도된 범위)

- 대기열(waiting room) 우회. 대기열이 보이면 새로고침도 클릭도 하지 않고 기다립니다.
- 봇 탐지 회피 (stealth 패치, 지문 위조, 다중 계정·IP)
- 보안문자 자동 풀이
- 0.5초 미만 간격의 새로고침 (설정에서 거부됨)

## 주의

- 대부분의 예매처 약관은 자동화 도구 사용을 금지합니다. 탐지되면 예매 취소나 계정 정지가 될 수 있습니다.
- 매크로로 산 입장권을 되파는 행위는 국가에 따라 처벌 대상입니다 (한국 공연법 등). **본인 관람용으로만** 쓰세요.
- 사이트의 WAF가 자동화 브라우저를 막으면 그대로 실패합니다. 우회는 하지 않습니다.

## 설치 (본인 PC)

```bash
cd tools/ticketing
pip install -e .
playwright install chromium
cp config.example.yaml config.yaml   # config.yaml 은 git 에 올라가지 않음
```

## 셀렉터 채우기

사이트 구조는 공연마다 다르므로 `playwright codegen` 으로 직접 기록합니다.

```bash
playwright codegen "https://event.thaiticketmajor.com/..."
```

평소처럼 로그인 → 공연 페이지 → 예매 → 날짜 → 회차까지 진행한 뒤, 생성된 코드에서 셀렉터를 `config.yaml` 의 `selectors` 에 옮깁니다. 날짜·회차 셀렉터에는 `{value}` 를 넣고, 우선순위 목록은 `preferences` 에 화면에 보이는 텍스트 그대로 적습니다.

## 실행

```bash
python -m ticketing clock config.yaml       # 서버 시계 오차 확인 (오픈 전 필수)
python -m ticketing run config.yaml --now   # 리허설: 대기 없이 즉시 실행
python -m ticketing run config.yaml         # 실전: open_at 에 맞춰 실행
```

본인 Chrome을 그대로 쓰고 싶다면 Chrome을 `--remote-debugging-port=9222 --user-data-dir=<별도 폴더>` 로 띄우고 `cdp_url: http://127.0.0.1:9222` 를 설정합니다.

## 구조

```
ticketing/
  clock.py    # HTTP Date 헤더 기반 서버 시계 오프셋 (초 경계 이진 탐색, 오차 ≈ RTT/2)
  config.py   # YAML 설정 로드·검증 (UTC 오프셋 필수, reload 하한)
  flow.py     # 오픈 대기 → 클릭 → 날짜 → 회차 → 핸드오프 (사이트 비종속)
  notify.py   # 핸드오프 알림
  __main__.py # CLI, 브라우저 실행/CDP 연결, 로그인 대기
tests/        # 시계 수렴, 설정 검증, 로컬 HTML 로 전체 흐름 (headless Chromium)
```

## 테스트

```bash
pip install -e ".[dev]" && playwright install chromium
pytest -v
```
