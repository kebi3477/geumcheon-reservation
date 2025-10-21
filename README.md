
# 금천구 시설대관 자동 예약 (사용자 플로우 버전)

## 실행 예
```bash
pip install selenium webdriver-manager python-dotenv
python reserve_macro.py --run-at 09:00:00 --date 2025-09-02 --slot 09:00 --people 2 --purpose 테니스
```
- 스크립트 파일명은 `reserve_macro.py` 입니다.
- 크롬 프로필을 쓰고 싶으면 `--user-data-dir`로 경로를 추가하세요.

## 선택자 매핑(필수)
`config_selectors.json`의 각 항목을 크롬 개발자도구(F12)로 실제 사이트에 맞게 교체하세요.
- 로그인: `login.*`
- 예약 홈: `reservation.apply_button`
- 개인정보 동의: `consent.*`
- 달력/시간: `calendar.*`, `timeslot.*`
- 할인/다음: `discount.*`
- 승인/입력/다음: `terms.*`, `form.*`
- 신청서 제출: `submit.*`
- 공통 모달 확인: `common.modal_ok_button`

## 팝업 처리
- JS alert는 자동으로 감지 후 `확인`을 누릅니다.
- 모달 버튼은 `common.modal_ok_button` 선택자로 클릭합니다.

## 참고
- 사이트 정책(자동화/봇 금지)을 확인하고 사용하세요.
- headless 차단 시 `--headless` 옵션을 제거하세요.
- 09:00 컷 정확도는 PC 시계에 의존합니다. 인터넷 시간 동기화를 권장합니다.
