from threading import Thread
from selenium.common import WebDriverException
from selenium import webdriver
from datetime import datetime, timedelta
from PIL import Image
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from flask import current_app
from .models import db, Change, MonitoredArea

def async_monitor(app):
    with app.app_context():
        while True:
            now = datetime.now()
            monitored_areas = MonitoredArea.query.all()
            for ma in monitored_areas:
                last_check = ma.last_change_checked if ma.last_change_checked else ma.created_at
                if now - last_check >= timedelta(minutes=ma.time_interval):
                    change_detected, current_snapshot = detect_changes(ma.website.url, ma.area_selector)
                    if change_detected or not Change.query.filter_by(monitored_area_id=ma.id).first():
                        new_change = Change(monitored_area_id=ma.id, change_snapshot="", change_summary="Change detected", screenshot=current_snapshot)
                        db.session.add(new_change)
                        db.session.commit()
            time.sleep(60)

def start_async_monitor():
    app = current_app._get_current_object()
    monitor_thread = Thread(target=async_monitor, args=(app,))
    monitor_thread.daemon = True
    monitor_thread.start()

def accept_cookies(driver):
    try:
        cookie_selectors = [
            "button[aria-label='Accept cookies']",  # esempio di selettore aria-label
            "button[aria-label='Agree']",           # esempio di selettore aria-label
            "button#accept-cookies",                # esempio di selettore id
            "button.cookie-consent-accept",         # esempio di selettore classe
            "button.btn-accept"                     # altro esempio di selettore classe
        ]
        for selector in cookie_selectors:
            try:
                cookie_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                cookie_button.click()
                break
            except:
                continue
    except Exception as e:
        print(f"Errore durante l'accettazione dei cookie: {e}")

def take_screenshot(url, selector=None):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
    except WebDriverException as e:
        return None

    accept_cookies(driver)

    screenshot_path = 'screenshot.png'
    driver.save_screenshot(screenshot_path)

    if selector:
        element = driver.find_element(By.CSS_SELECTOR, selector)
        location = element.location
        size = element.size
        image = Image.open(screenshot_path)
        left = location['x']
        top = location['y']
        right = location['x'] + size['width']
        bottom = location['y'] + size['height']
        image = image.crop((left, top, right, bottom))
        cropped_path = 'screenshot_cropped.png'
        image.save(cropped_path)
        driver.quit()
        with open(cropped_path, "rb") as image_file:
            return image_file.read()
    else:
        driver.quit()
        with open(screenshot_path, "rb") as image_file:
            return image_file.read()

def detect_changes(url, selector=None, last_snapshot=None):
    current_snapshot = take_screenshot(url, selector)

    if last_snapshot:
        if current_snapshot != last_snapshot:  # Replace with actual comparison logic
            return True, current_snapshot
        else:
            return False, current_snapshot
    else:
        return True, current_snapshot
