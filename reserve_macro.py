# -*- coding: utf-8 -*-
"""
금천구 시설대관 통합예약 자동화 (Selenium Manager 버전 + GUI)
- GUI에서 날짜/시간/즉시 실행/예약 시간 선택 가능
- 상세 페이지의 [신청하기] 버튼을 확실하게 클릭 (CSS → 텍스트 기반 폴백)
"""

import os
import json
import time
import getpass
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions


# -------------------- 유틸 --------------------

BASE_DIR = Path(__file__).resolve().parent

def now_str():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def read_selectors(cfg_path: Path) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


# -------------------- Selenium --------------------

def build_driver(detach=False, user_data_dir=None):
    opts = ChromeOptions()
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

    driver = webdriver.Chrome(options=opts)
    driver.set_window_size(1400, 950)
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
    """텍스트가 text를 포함하는 tag 요소 클릭 (a/button/span 등)"""
    xp = f"//{tag}[contains(normalize-space(), '{text}')]"
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xp))
    )
    driver.execute_script("arguments[0].click();", el)
    return el

def click_input_by_value(driver, value, timeout=6):
    """value가 text인 <input> 버튼 클릭"""
    xp = f"//input[@value='{value}']"
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xp))
    )
    driver.execute_script("arguments[0].click();", el)
    return el


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


def step_go_reservation(driver, sel, reservation_url):
    driver.get(reservation_url)
    log("예약 상세 페이지 이동")
    # 상세 페이지 로딩 마커가 있으면 대기
    marker = sel.get("reservation", {}).get("page_ready_marker")
    if marker:
        try:
            wait_visible(driver, marker, timeout=10)
        except Exception:
            pass

def step_select_day(driver, chosen_date):
    """
    달력에서 chosen_date(YYYY-MM-DD)의 '일' 버튼(#day{D}) 클릭 후, 시간 선택을 수행한다.
    """
    # 1) '일' 숫자 파싱
    try:
        day = int(str(chosen_date).split("-")[-1])  # 'YYYY-MM-DD' 가정. 마지막 토큰이 'DD'
    except Exception:
        raise ValueError(f"chosen_date 형식이 잘못되었습니다: {chosen_date}")

    log(f"달력에서 {day}일 버튼 클릭 시도 (#day{day})")

    # 2) #day{day} 버튼 클릭 (클릭 가능 → presence→JS → 텍스트 기반 폴백)
    try:
        btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f"#day{day}"))
        )
        driver.execute_script("arguments[0].click();", btn)
        log(f"{day}일 버튼 클릭 (#day{day}, clickable)")
    except Exception as e1:
        try:
            btn = WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"#day{day}"))
            )
            driver.execute_script("arguments[0].click();", btn)
            log(f"{day}일 버튼 클릭 (#day{day}, presence→JS)")
        except Exception as e2:
            raise RuntimeError(
                f"{day}일 버튼을 찾거나 클릭할 수 없습니다. "
                f"(clickable:{e1} | presence:{e2})"
            )

def step_select_time(driver, chosen_date, start_hour, hours=2, click_next=True):
    """
    예약 시간 선택 (연속 hours시간 시도)
    - chosen_date: 'YYYY-MM-DD' 형식 (value='YYYYMMDDHH' 매칭용)
    - 체크박스 input(name='erntYmdh', id='erntTime_HH')를 직접 체크 후 change/input 이벤트 디스패치
    - 최소 1개도 못 고르면 에러
    - 선택 후 '다음단계' 버튼 클릭 (input[type=submit].p-button.write[value='다음단계'])
    """
    yyyymmdd = str(chosen_date).replace("-", "")
    picked = 0

    # 시간 목록 컨테이너가 뜰 때까지 잠깐 대기 (있다면)
    try:
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.timetable_list"))
        )
    except Exception:
        pass

    for h in range(start_hour, start_hour + hours):
        hh = f"{h:02d}"
        slot_id = f"erntTime_{hh}"
        slot_val = f"{yyyymmdd}{hh}"

        cb = None
        # 1) id로 우선 탐색 (erntTime_09)
        try:
            cb = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"input#{slot_id}"))
            )
        except Exception:
            # 2) value로 폴백 (2025102909)
            try:
                cb = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located(
                        (By.XPATH, f"//input[@name='erntYmdh' and @value='{slot_val}']")
                    )
                )
            except Exception:
                # 3) 라벨 텍스트 폴백 (09시~10시)
                label_text = f"{h:02d}시~{h+1:02d}시"
                try:
                    lbl = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located(
                            (By.XPATH, f"//label[contains(normalize-space(), '{label_text}')]")
                        )
                    )
                    # 라벨의 for 속성으로 input id 유추
                    for_id = lbl.get_attribute("for")
                    if for_id:
                        cb = driver.find_element(By.ID, for_id)
                except Exception:
                    cb = None

        if not cb:
            log(f"시간 체크박스 찾기 실패: {hh}시 ({slot_id}/{slot_val})")
            # 연속 선택이 아니어도 가능한 만큼만: 다음 시간대로 계속 시도
            continue

        try:
            # 보이도록 스크롤
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cb)

            # 이미 체크되어 있지 않으면 체크 + 이벤트 디스패치
            is_checked = cb.is_selected() or (cb.get_attribute("checked") is not None)
            if not is_checked:
                driver.execute_script("""
                    const el = arguments[0];
                    el.checked = true;
                    el.dispatchEvent(new Event('input', {bubbles:true}));
                    el.dispatchEvent(new Event('change', {bubbles:true}));
                """, cb)

            # 여전히 체크가 안 되었으면 클릭 폴백
            if not (cb.is_selected() or (cb.get_attribute("checked") is not None)):
                driver.execute_script("arguments[0].click();", cb)

            # 최종 확인
            if cb.is_selected() or (cb.get_attribute("checked") is not None):
                picked += 1
                log(f"예약 시간 선택: {h:02d}시~{h+1:02d}시")
            else:
                log(f"시간 선택 실패(체크 미반영): {h:02d}시")

        except Exception as e:
            log(f"시간 선택 중 오류: {h:02d}시 ({e})")

        # 원하는 개수만큼 선택되면 종료
        if picked >= hours:
            break

    if picked == 0:
        raise RuntimeError("선택 가능한 시간대가 없습니다.")

    if click_next:
        log("다음단계 버튼 클릭 시도")
        # 1) CSS로 시도
        try:
            css_click(driver, "input.p-button.write[type='submit'][value='다음단계']", timeout=6)
            log("다음단계 클릭 (CSS 매칭)")
            return
        except Exception:
            pass
        # 2) value 폴백
        try:
            click_input_by_value(driver, "다음단계", timeout=6)
            log("다음단계 클릭 (input[value] 폴백)")
            return
        except Exception:
            pass
        # 3) 버튼/링크 텍스트 폴백(혹시 변형된 경우)
        for try_fn, desc in [
            (lambda: click_by_text(driver, "button", "다음단계"), "button 텍스트"),
            (lambda: click_by_text(driver, "a", "다음단계"), "a 텍스트"),
        ]:
            try:
                try_fn()
                log(f"다음단계 클릭 (폴백: {desc})")
                return
            except Exception:
                continue

        raise RuntimeError("다음단계 버튼을 찾지 못했습니다.")


# -------------------- 메인 실행 --------------------

def run_main(chosen_date, run_at, immediate=False, start_hour=9):
    load_dotenv(BASE_DIR / ".env")
    USER_ID = os.getenv("USER_ID") or input("아이디: ")
    USER_PW = os.getenv("USER_PW") or getpass.getpass("비밀번호: ")
    LOGIN_URL = os.getenv("LOGIN_URL")
    RESERVATION_URL = os.getenv("RESERVATION_URL")
    sel = read_selectors(BASE_DIR / "config_selectors.json")

    driver = build_driver(detach=True)

    try:
        if not immediate and run_at:
            # 예약 오픈 시간까지 대기
            h, m, s = map(int, run_at.split(":"))
            target = datetime.now().replace(hour=h, minute=m, second=s, microsecond=0)
            if target < datetime.now():
                target += timedelta(days=1)
            log(f"예약 오픈 대기: {target}")
            while datetime.now() < target:
                time.sleep(0.5)

        step_login(driver, sel, USER_ID, USER_PW, LOGIN_URL)
        step_go_reservation(driver, sel, RESERVATION_URL)
        step_select_day(driver, chosen_date)
        step_select_time(driver, chosen_date, start_hour, hours=2)
        log(f"✅ 예약 절차 완료 (날짜: {chosen_date}, 시간: {start_hour}시~{start_hour+2}시)")

    except Exception as e:
        log(f"에러 발생: {e}")
        input("브라우저 창을 닫으려면 엔터...")


# -------------------- GUI --------------------

def open_gui():
    root = tk.Tk()
    root.title("금천구 예약 매크로")

    today = datetime.today()
    default_days = tk.IntVar(value=10)
    default_time = tk.StringVar(value="09:00:00")
    immediate_mode = tk.BooleanVar(value=False)
    start_hour = tk.IntVar(value=9)

    ttk.Label(root, text="며칠 뒤 날짜 선택 (기본 10일)").grid(row=0, column=0, padx=5, pady=5)
    tk.Entry(root, textvariable=default_days, width=10).grid(row=0, column=1, padx=5)

    ttk.Label(root, text="오픈 시각 (HH:MM:SS)").grid(row=1, column=0, padx=5, pady=5)
    tk.Entry(root, textvariable=default_time, width=10).grid(row=1, column=1, padx=5)

    tk.Checkbutton(root, text="즉시 실행 모드", variable=immediate_mode).grid(row=2, column=0, columnspan=2, pady=5)

    ttk.Label(root, text="예약 시작 시간 (연속 2시간)").grid(row=3, column=0, padx=5, pady=5)
    hours = [f"{h}시~{h+1}시" for h in range(9, 22)]
    combo = ttk.Combobox(root, values=hours, textvariable=start_hour, state="readonly")
    combo.current(0)
    combo.grid(row=3, column=1, padx=5, pady=5)

    def start():
        days = default_days.get()
        chosen_date = (today + timedelta(days=days)).strftime("%Y-%m-%d")
        run_at = default_time.get()
        immediate = immediate_mode.get()
        sh = int(hours.index(combo.get())) + 9
        root.destroy()
        run_main(chosen_date, run_at, immediate, start_hour=sh)

    ttk.Button(root, text="시작", command=start).grid(row=4, column=0, columnspan=2, pady=10)

    root.mainloop()


if __name__ == "__main__":
    open_gui()
