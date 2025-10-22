# gc-reservation-macro-v3 (v0.1.0)

금천구 통합예약 사이트에서 **예약 오픈 시각 대기 → 날짜/시간(연속 2시간) 선택 → 다음 단계 진행 → 약관 동의/인원/사용목적 입력**까지 자동화하는 데스크톱 GUI 도구입니다.

- **Python 3.13+**, **Chrome 최신 버전** 필요
- **Selenium Manager** 기본 사용(드라이버 자동 관리) + *(옵션)* **webdriver-manager** 의존성 포함
- GUI에서 **연/월/일**, **오픈 시각(대기)** / **즉시 실행**, **시작 시간(2시간)** 을 지정

---

## 빠른 시작

### 1) 필수 사항
- **Python**: `>= 3.13` (프로젝트 루트에 `.python-version` = `3.13` 사용 가능)
- **Chrome**: 최신 버전 권장
- **OS**: Windows / macOS / Linux

### 2) 설치

**uv 사용 권장** (없다면 `pip` 사용)

```bash
# uv가 있다면 (권장)
uv venv
uv pip install -r requirements.txt  # 또는 uv pip install selenium python-dotenv pyinstaller webdriver-manager
# 실행
uv run python main.py
```

```bash
# pip로도 가능
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -U pip
pip install selenium python-dotenv pyinstaller webdriver-manager
python main.py
```

> `requirements.txt` 예시
>
> ```txt
> selenium>=4.37.0
> python-dotenv>=1.1.1
> pyinstaller>=6.16.0
> webdriver-manager>=4.0.2
> ```

---

## 실행 환경(.env) 샘플

루트에 `.env` 파일을 생성하세요. 아래 값은 사용자가 제공한 최신 예시입니다.

```dotenv
# 환경
RUN_AT=09:00:00
LOGIN_URL=https://www.geumcheon.go.kr/portal/login.do?key=996
# RESERVATION_URL=https://www.geumcheon.go.kr/reserve/webErntView.do?key=115&searchErntNo=140305
# 본문
PEOPLE=2
PURPOSE=테니스

# 로그인 계정
USER_ID=
USER_PW=
```

> 코드의 `build_reservation_url()`은 `.env`의 `RESERVATION_URL`에 `sYear/sMonth`가 있어도 **선택 날짜(YYYY-MM-DD)** 기준으로 값을 **강제 반영**합니다.

---

## 선택자 설정(`config_selectors.json`)

아래는 사용자가 제공한 최신 선택자 템플릿입니다. 사이트 구조 변경 시 이 파일만 수정하면 됩니다.

```json
{
  "login": {
    "id_input": "#userId",
    "pw_input": "#userPasswd",
    "submit_button": "input[value='로그인']",
    "login_success_marker": "a.gnb_text[href*='logout']"
  },
  "reservation": {
    "page_ready_marker": ".facilities.view",
    "apply_button": "input.p-button.write[value='신청하기']"
  },
  "consent": {
    "privacy_required_checkbox": "label.p-form-radio__label",
    "privacy_submit_button": "a.p-button.write"
  },
  "agree": {
    "radio": "input#a3",
    "submit_button": "a.p-button.write"
  },
  "calendar": {
    "month_option_template": "a:contains('{M}월')",
    "date_cell_template": "button#day{DD}"
  },
  "timeslot": {
    "time_item": "label.p-form-checkbox__label"
  },
  "discount": {
    "none_radio": "label.p-form-radio__label",
    "next_button": "input.p-button.write[value='다음단계']"
  },
  "terms": {
    "agree_checkbox": "label.p-form-checkbox__label"
  },
  "form": {
    "people_input": "#expectNmpr",
    "purpose_input": "textarea#usePurps",
    "next_button": "input.p-button.write[value='다음단계']"
  },
  "submit": {
    "final_submit_button": "input.p-button.write[value='신청서 제출']"
  },
  "common": {
    "modal_ok_button": "button.modal-ok"
  }
}
```

> 기존 README의 간단한 선택자보다 **더 정밀**합니다. 로그인 성공 마커, 동의/약관/개인정보, 캘린더/시간 선택, 할인/다음단계, 최종 제출, 공통 모달 버튼까지 반영했습니다.

---

## 사용 방법 (GUI)

1. 실행: `python main.py` (또는 `uv run python main.py`)
2. GUI에서 **예약 날짜(기본: 오늘+10일)**, **오픈 시각(HH:MM:SS)**, **즉시 실행 모드**, **시작 시간(2시간 연속)** 을 설정
3. **[시작]** 클릭 → 아래 순서 자동 진행
   1) 로그인 → 2) 상세 페이지 이동(선택 날짜로 URL 보정) → 3) 날짜 선택 → 4) 시작 시간부터 2시간 체크 → 5) 다음단계 → 6) 약관/인원/목적 입력 → 7) 다음단계/제출

### 내부 동작 포인트
- `page_load_strategy="eager"`, 이미지 로딩 차단으로 속도 최적화
- 날짜/시간 선택은 JS로 **일괄 체크**, 실패 시 폴백
- 연쇄 알림은 `drain_alerts_until_clear()`로 즉시 수락/정리
- **다음단계/신청하기**는 CSS/XPath/텍스트 클릭 폴백

---

## 빌드(배포 파일 생성)

`PyInstaller`로 독립 실행 파일을 만듭니다. 사용자가 제공한 커맨드를 그대로 사용하세요.

```bash
uv run pyinstaller reserve_macro.py \
  --name GeumcheonReserve \
  --onedir \
  --icon icon.icns \
  --add-data "config_selectors.json:." \
  --add-data ".env:." \
  --noconfirm
```

- 결과물: `dist/GeumcheonReserve/` 폴더
- **Windows**에서는 아이콘을 `.ico`로 교체하세요: `--icon icon.ico`
- **단일 실행 파일**이 필요하면 `--onefile` 사용 가능(시작 속도는 약간 느려질 수 있음)
- 실행 시 `config_selectors.json`과 `.env`가 포함되도록 `--add-data` 경로를 OS 규칙에 맞게 지정하세요  
  - Windows: `"config_selectors.json;."` 형태
  - macOS/Linux: `"config_selectors.json:."` 형태

> 기본 동작은 **Selenium Manager**로 드라이버를 자동 관리합니다. 환경에 따라 크롬 드라이버 문제가 생기면 `webdriver-manager`를 사용해 드라이버 경로를 명시하는 방식을 고려할 수 있습니다(코드 변경 필요).

---

## 프로젝트 메타

- **name**: `gc-reservation-macro-v3`
- **version**: `0.1.0` (revision `3`)
- **requires-python**: `>=3.13`
- **핵심 의존성**
  - `selenium>=4.37.0`
  - `python-dotenv>=1.1.1`
  - `pyinstaller>=6.16.0`
  - `webdriver-manager>=4.0.2` *(옵션 사용)*

> transitive deps: `trio`, `trio-websocket`, `urllib3[socks]`, `websocket-client` 등은 `selenium`이 자동으로 설치합니다.

---

## 주의/정책

- 해당 사이트의 **이용약관/로봇정책**을 준수하세요.
- 계정 정보는 `.env`에 저장하거나 실행 시 프롬프트로 입력받고, 공용 PC 사용 후에는 로그아웃/세션 종료를 확인하세요.

행복한 예약 되세요! 🎾
