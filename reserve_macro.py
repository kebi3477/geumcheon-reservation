# -*- coding: utf-8 -*-
"""
금천구 시설대관 통합예약 자동화 (Selenium Manager 버전 + GUI)
- GUI에서 '연/월/일' 직접 입력 (기본값 = 오늘+10일)
- 오픈시각 / 즉시 실행 / 시작 시간(연속 2시간) 선택 가능
- 상세 페이지 [신청하기] 버튼 클릭 안정화 (CSS → 텍스트 폴백)
- RESERVATION_URL 은 searchErntNo 까지만 넣고, 실행 시 sYear/sMonth 자동 부여
- 날짜/시간/다음단계 초고속화 + 다음단계 alert 처리 → 동의/인원/목적 입력 → 다음단계 자동 진행
"""

import os
import json
import time
import getpass
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import UnexpectedAlertPresentException, TimeoutException

# -------------------- 유틸 --------------------

BASE_DIR = Path(__file__).resolve().parent

def now_str():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def read_selectors(cfg_path: Path) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_reservation_url(base_url: str, chosen_date: str) -> str:
    """
    base_url: searchErntNo까지만 포함된 URL
      예) https://www.geumcheon.go.kr/reserve/erntApplcntStep01.do?key=115&searchErntNo=140305
    chosen_date: 'YYYY-MM-DD'
    실행 시 sYear=YYYY, sMonth=MM 을 자동으로 쿼리에 부여
    """
    y, m, _ = chosen_date.split("-")
    parts = urlsplit(base_url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q.pop("sYear", None)
    q.pop("sMonth", None)
    q["sYear"] = y
    q["sMonth"] = m
    full_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))
    log(f"예약 상세 페이지 URL 구성: {full_url}")
    return full_url

def drain_alerts_until_clear(driver, max_rounds=6):
    """
    뜨는 즉시 alert을 연속으로 비워서 'unexpected alert open'을 방지.
    '저장되었습니다.' 같은 토스트성 alert이 여러 번 떠도 안전.
    """
    for _ in range(max_rounds):
        try:
            # 이미 정의된 accept_alert_if_present 재활용
            if not accept_alert_if_present(driver, timeout=0.8):
                return
            # alert 연속 발생 간 짧게 양보
            time.sleep(0.1)
        except Exception:
            return  

# -------------------- Selenium --------------------

def build_driver(detach=False, user_data_dir=None):
    opts = ChromeOptions()
    # DOMContentLoaded까지만 대기 → 페이지 전환 즉시 제어 가능
    opts.page_load_strategy = "eager"

    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    if detach:
        opts.add_experimental_option("detach", True)
    if user_data_dir:
        opts.add_argument(f"--user-data-dir={user_data_dir}")

    # 네트워크 부하↓: 이미지 차단 (사이트 안 깨지는 선)
    prefs = {
        "profile.managed_default_content_settings.images": 2,
    }
    opts.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=opts)
    driver.set_window_size(1400, 950)
    driver.set_page_load_timeout(15)
    return driver

def css_click(driver, selector, timeout=12):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
    )
    driver.execute_script("arguments[0].click();", el)
    return el

def wait_visible(driver, selector, timeout=12):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )

def click_by_text(driver, tag, text, timeout=6):
    xp = f"//{tag}[contains(normalize-space(), '{text}')]"
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xp))
    )
    driver.execute_script("arguments[0].click();", el)
    return el

def click_input_by_value(driver, value, timeout=6):
    xp = f"//input[@value='{value}']"
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xp))
    )
    driver.execute_script("arguments[0].click();", el)
    return el

def accept_alert_if_present(driver, timeout=1.5):
    """alert/confirm이 빨리 뜨면 바로 수락, 없으면 패스"""
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        al = driver.switch_to.alert
        txt = (al.text or "").strip()
        al.accept()
        log(f"알림 수락: {txt}")
        return True
    except Exception:
        return False


# -------------------- 단계 함수 --------------------

def step_login(driver, sel, user_id, user_pw, login_url):
    driver.get(login_url)
    log("로그인 페이지 접속")
    id_box = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, sel["login"]["id_input"]))
    )
    pw_box = driver.find_element(By.CSS_SELECTOR, sel["login"]["pw_input"])
    id_box.clear(); id_box.send_keys(user_id)
    pw_box.clear(); pw_box.send_keys(user_pw)
    css_click(driver, sel["login"]["submit_button"])
    log("로그인 시도")

    # 알림 감지는 짧게만
    accept_alert_if_present(driver, timeout=0.8)

def step_go_reservation(driver, sel, reservation_url_base, chosen_date_str):
    """예약 상세 페이지로 이동(sYear/sMonth 자동 추가)"""
    url = build_reservation_url(reservation_url_base, chosen_date_str)
    driver.get(url)
    log("예약 상세 페이지 이동")
    # DOM만 준비되었는지 간단 체크
    try:
        WebDriverWait(driver, 2).until(
            lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
        )
    except Exception:
        pass
    marker = sel.get("reservation", {}).get("page_ready_marker")
    if marker:
        try:
            wait_visible(driver, marker, timeout=2)  # 긴 대기 제거
        except Exception:
            pass

def step_select_day(driver, chosen_date):
    """#day{D} 를 JS로 바로 클릭 (대기 최소화)"""
    try:
        day = int(str(chosen_date).split("-")[-1])
    except Exception:
        raise ValueError(f"chosen_date 형식이 잘못되었습니다: {chosen_date}")

    js = """
    const day = arguments[0];
    const sel = "#day"+day;
    const el = document.querySelector(sel);
    if(!el) return "notfound";
    el.scrollIntoView({block:"center"});
    el.click();
    return "clicked";
    """
    for _ in range(4):  # 짧게 4번 재시도
        res = driver.execute_script(js, day)
        if res == "clicked":
            log(f"{day}일 버튼 클릭(JS)")
            return
        time.sleep(0.15)
    # 폴백 (아주 짧은 대기)
    try:
        btn = WebDriverWait(driver, 1.5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f"#day{day}"))
        )
        driver.execute_script("arguments[0].click();", btn)
        log(f"{day}일 버튼 클릭(폴백)")
    except Exception as e:
        raise RuntimeError(f"{day}일 버튼을 찾거나 클릭할 수 없습니다: {e}")

def step_select_time(driver, chosen_date, start_hour, hours=2):
    """
    시간 체크박스들을 JS 한 방에 처리 (빠름)
    - 우선 id=erntTime_HH 을 찾고, 없으면 value=YYYYMMDDHH 로 찾음
    """
    time.sleep(1)
    yyyymmdd = str(chosen_date).replace("-", "")
    js = r"""
    const yyyymmdd = arguments[0];
    const start = arguments[1];
    const hours = arguments[2];
    let picked = 0, tried = 0;
    for (let h = start; h < start + hours; h++) {
        const hh = ('0'+h).slice(-2);
        let el = document.getElementById('erntTime_' + hh)
               || document.querySelector(`input[name="erntYmdh"][value="${yyyymmdd}${hh}"]`);
        tried++;
        if (!el || el.disabled) continue;
        el.scrollIntoView({block:'center'});
        if (!el.checked) {
            el.checked = true;
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
        }
        if (el.checked) picked++;
    }
    return [picked, tried];
    """
    # timetable DOM이 생성될 시간을 아주 짧게만 준다
    for _ in range(20):
        try:
            driver.find_element(By.CSS_SELECTOR, "ul.timetable_list")
            break
        except Exception:
            time.sleep(0.08)

    picked, tried = driver.execute_script(js, yyyymmdd, int(start_hour), int(hours)) or (0, 0)
    if picked <= 0:
        raise RuntimeError(f"선택 가능한 시간대가 없습니다. (tried={tried})")
    log(f"예약 시간 선택 완료: {start_hour:02d}시~{start_hour+hours:02d}시 (picked={picked}, tried={tried})")

def step_click_next(driver):
    """다음단계 버튼 초고속 클릭 + alert 즉시 수락/무시"""
    # 클릭 전에 혹시 남은 alert 비우기
    drain_alerts_until_clear(driver)

    js = """
    const el =
      document.querySelector('input.p-button.write[type="submit"][value="다음단계"]')
      || document.querySelector('input[type="submit"][value="다음단계"]')
      || document.querySelector('button, a');
    if (!el) return "notfound";
    el.scrollIntoView({block:"center"});
    el.click();
    return "clicked";
    """
    try:
        for _ in range(3):
            res = driver.execute_script(js)
            if res == "clicked":
                log("다음단계 클릭(JS)")
                break
            time.sleep(0.1)
        if res != "clicked":
            try:
                css_click(driver, 'input.p-button.write[type="submit"][value="다음단계"]', timeout=1.2)
                log("다음단계 클릭(폴백)")
            except Exception:
                click_input_by_value(driver, "다음단계", timeout=1.2)
                log("다음단계 클릭(값 폴백)")
    except UnexpectedAlertPresentException:
        # 클릭 과정에서 alert가 뜬 경우
        drain_alerts_until_clear(driver)
    finally:
        # 클릭 직후 연쇄 alert 정리
        drain_alerts_until_clear(driver)

def step_fill_agree_people_purpose_and_next(driver, people: str, purpose: str):
    """
    다음 단계 폼 처리:
      - checkAgress 체크
      - expectNmpr 입력 (PEOPLE)
      - usePurps 입력 (PURPOSE)
      - '다음단계' 제출
      - 중간/제출 alert이 있으면 자동 수락
    """
    # 폼 요소가 나타날 시간을 아주 짧게만 준다
    def _js_set_checked(css):
        return driver.execute_script("""
            const el = document.querySelector(arguments[0]);
            if(!el) return false;
            el.scrollIntoView({block:'center'});
            el.checked = true;
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            return true;
        """, css)

    def _js_set_value(css, value):
        return driver.execute_script("""
            const el = document.querySelector(arguments[0]);
            if(!el) return false;
            el.scrollIntoView({block:'center'});
            el.value = arguments[1];
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            return true;
        """, css, value)

    # 폼 등장 대기(짧게 폴링)
    for _ in range(30):  # 최대 ~2.4s
        ok = driver.execute_script("return !!document.querySelector('#checkAgress') || !!document.querySelector('#expectNmpr') || !!document.querySelector('#usePurps');")
        if ok:
            break
        time.sleep(0.08)

    # 동의 체크
    if not _js_set_checked("#checkAgress"):
        log("⚠️ checkAgress 요소를 찾지 못함(무시하고 진행)")

    # 인원/목적 입력
    if not _js_set_value("#expectNmpr", str(people)):
        log("⚠️ expectNmpr 요소를 찾지 못함")
    if not _js_set_value("#usePurps", purpose):
        log("⚠️ usePurps 요소를 찾지 못함")

    # 제출 버튼 클릭
    step_click_next(driver) 

    # 제출 후 추가 alert/confirm이 한 번 더 뜨는 경우 대비
    accept_alert_if_present(driver, timeout=1.2)


# -------------------- 메인 실행 --------------------

def run_main(chosen_date, run_at, immediate=False, start_hour=9):
    load_dotenv(BASE_DIR / ".env")
    USER_ID = os.getenv("USER_ID") or input("아이디: ")
    USER_PW = os.getenv("USER_PW") or getpass.getpass("비밀번호: ")
    LOGIN_URL = os.getenv("LOGIN_URL")
    # ✅ 환경변수에는 searchErntNo까지만!
    # 예) RESERVATION_URL=https://www.geumcheon.go.kr/reserve/erntApplcntStep01.do?key=115&searchErntNo=140305
    RESERVATION_URL_BASE = os.getenv("RESERVATION_URL")

    # 인원/목적
    PEOPLE = os.getenv("PEOPLE", "2")
    PURPOSE = os.getenv("PURPOSE", "테니스")

    sel = read_selectors(BASE_DIR / "config_selectors.json")
    driver = build_driver(detach=True)

    try:
        if not immediate and run_at:
            h, m, s = map(int, run_at.split(":"))
            target = datetime.now().replace(hour=h, minute=m, second=s, microsecond=0)
            if target < datetime.now():
                target += timedelta(days=1)
            log(f"예약 오픈 대기: {target}")
            while datetime.now() < target:
                time.sleep(0.5)

        step_login(driver, sel, USER_ID, USER_PW, LOGIN_URL)
        step_go_reservation(driver, sel, RESERVATION_URL_BASE, chosen_date)

        step_select_day(driver, chosen_date)
        step_select_time(driver, chosen_date, start_hour, hours=2)
        drain_alerts_until_clear(driver)
        step_click_next(driver)
        step_fill_agree_people_purpose_and_next(driver, PEOPLE, PURPOSE)

        log(f"✅ 예약 절차 완료 (날짜: {chosen_date}, 시간: {start_hour}시~{start_hour+2}시, 인원:{PEOPLE}, 목적:{PURPOSE})")

    except Exception as e:
        log(f"에러 발생: {e}")
        input("브라우저 창을 닫으려면 엔터...")


# -------------------- GUI --------------------

def open_gui():
    root = tk.Tk()
    root.title("금천구 예약 매크로")

    # 기본 날짜 = 오늘 + 10일
    default_date = (datetime.today() + timedelta(days=10)).date()
    year_var = tk.IntVar(value=default_date.year)
    month_var = tk.IntVar(value=default_date.month)
    day_var = tk.IntVar(value=default_date.day)

    default_time = tk.StringVar(value="09:00:00")
    immediate_mode = tk.BooleanVar(value=False)

    ttk.Label(root, text="예약 날짜 (기본: 오늘+10일)").grid(row=0, column=0, padx=5, pady=5, sticky="e")

    # 연/월/일 입력 (Spinbox)
    y_spin = tk.Spinbox(root, from_=2024, to=2035, width=6, textvariable=year_var)
    m_spin = tk.Spinbox(root, from_=1, to=12, width=4, textvariable=month_var)
    d_spin = tk.Spinbox(root, from_=1, to=31, width=4, textvariable=day_var)
    y_spin.grid(row=0, column=1, padx=(5,2), sticky="w")
    ttk.Label(root, text="년").grid(row=0, column=2, sticky="w")
    m_spin.grid(row=0, column=3, padx=(10,2), sticky="w")
    ttk.Label(root, text="월").grid(row=0, column=4, sticky="w")
    d_spin.grid(row=0, column=5, padx=(10,2), sticky="w")
    ttk.Label(root, text="일").grid(row=0, column=6, sticky="w")

    ttk.Label(root, text="오픈 시각 (HH:MM:SS)").grid(row=1, column=0, padx=5, pady=5, sticky="e")
    tk.Entry(root, textvariable=default_time, width=10).grid(row=1, column=1, padx=5, sticky="w")

    tk.Checkbutton(root, text="즉시 실행 모드", variable=immediate_mode).grid(row=2, column=0, columnspan=3, pady=5, sticky="w")

    ttk.Label(root, text="예약 시작 시간 (연속 2시간)").grid(row=3, column=0, padx=5, pady=5, sticky="e")
    hours = [f"{h}시~{h+1}시" for h in range(9, 22)]
    combo = ttk.Combobox(root, values=hours, state="readonly", width=10)
    combo.current(0)
    combo.grid(row=3, column=1, padx=5, pady=5, sticky="w")

    def start():
        try:
            y = int(year_var.get())
            m = int(month_var.get())
            d = int(day_var.get())
            chosen = datetime(year=y, month=m, day=d).strftime("%Y-%m-%d")
        except ValueError:
            messagebox.showerror("날짜 오류", "유효하지 않은 날짜입니다. 연/월/일을 확인하세요.")
            return

        run_at = default_time.get()
        immediate = immediate_mode.get()
        sh = int(hours.index(combo.get())) + 9

        root.destroy()
        run_main(chosen, run_at, immediate, start_hour=sh)

    ttk.Button(root, text="시작", command=start).grid(row=4, column=0, columnspan=2, pady=10)

    root.mainloop()


if __name__ == "__main__":
    open_gui()
