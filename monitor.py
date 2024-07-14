from datetime import datetime, timedelta
from threading import Thread
from io import BytesIO
from PIL import Image
import numpy as np
import cv2
from skimage.metrics import structural_similarity
from selenium.common import WebDriverException
from selenium import webdriver
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from flask import current_app

from .models import db, Change, MonitoredArea, Difference
from logger import Logger


def async_monitor(app):
    with app.app_context():
        while True:
            now = datetime.now()
            monitored_areas = MonitoredArea.query.all()
            for ma in monitored_areas:
                if ma.last_change_checked is None:
                    last_check = datetime.min
                else:
                    last_check = ma.last_change_checked

                if now - last_check >= timedelta(minutes=ma.time_interval):
                    Logger.getInstance().log(f"Checking {ma.website.url}")

                    # Prende l'ultima change e la passa a detect_changes
                    last_changed = Change.query.filter_by(monitored_area_id=ma.id).order_by(
                        Change.change_detected_at.desc()).first()

                    change_detected, current_snapshot, diff_image = detect_changes(ma.website.url,
                                                                                   last_changed.screenshot if last_changed else None)
                    existing_change = Change.query.filter_by(monitored_area_id=ma.id).first()
                    Logger.getInstance().log(f"Change detected: {change_detected}")
                    Logger.getInstance().log(f"Current snapshot exists: {"si" if current_snapshot else "no"}")
                    if current_snapshot is not None:
                        Logger.getInstance().log(f"Screenshot eseguito, cambiamento: {change_detected}")
                        if change_detected or not existing_change:
                            change_summary = "First screenshot" if not existing_change else "Change detected"
                            new_change = Change(monitored_area_id=ma.id, change_snapshot="", change_summary=change_summary,
                                                screenshot=current_snapshot)
                            db.session.add(new_change)
                            try:
                                db.session.commit()
                                Logger.getInstance().log(f"New change detected for {ma.website.url}")

                                if change_detected and last_changed:
                                    save_differences(last_changed.id, new_change.id, diff_image)

                            except Exception as e:
                                db.session.rollback()
                                Logger.getInstance().log(f"Error adding new change: {e}")

                        ma.last_change_checked = now
                        try:
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                            Logger.getInstance().log(f"Error updating last check time: {e}")
            time.sleep(10)


def start_async_monitor():
    print("Starting monitor thread")
    app = current_app._get_current_object()
    monitor_thread = Thread(target=async_monitor, args=(app,))
    monitor_thread.daemon = True
    monitor_thread.start()
    print("Monitor thread started")

def accept_cookies(driver):
    return
    try:
        cookie_selectors = [
            "button[aria-label='Accept cookies']",
            "button[aria-label='Agree']",
            "button#accept-cookies",
            "button.cookie-consent-accept",
            "button.btn-accept"
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

def take_screenshot(url):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
    except WebDriverException as e:
        Logger.log(f"URL access denied: {e.msg}")
        return None

    time.sleep(2)

    screenshot_path = 'screenshot.png'
    driver.save_screenshot(screenshot_path)
    driver.quit()

    with open(screenshot_path, "rb") as image_file:
        return image_file.read()

def compare_images(image1, image2):
    img1 = np.array(Image.open(BytesIO(image1)).convert('RGB'))
    img2 = np.array(Image.open(BytesIO(image2)).convert('RGB'))

    img1_gray = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY)
    img2_gray = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)

    score, diff = structural_similarity(img1_gray, img2_gray, full=True)
    print("Similarity Score: {:.3f}%".format(score * 100))

    diff = (diff * 255).astype("uint8")
    thresh = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    mask = np.zeros(img1.shape, dtype='uint8')
    filled = img2.copy()

    for c in contours:
        area = cv2.contourArea(c)
        if area > 100:
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(img1, (x, y), (x + w, y + h), (36, 255, 12), 2)
            cv2.rectangle(img2, (x, y), (x + w, y + h), (36, 255, 12), 2)
            cv2.drawContours(mask, [c], 0, (0, 255, 0), -1)
            cv2.drawContours(filled, [c], 0, (0, 255, 0), -1)

    diff_image = Image.fromarray(diff)

    return score < 0.95, diff_image

def detect_changes(url, last_snapshot=None):
    current_snapshot = take_screenshot(url)

    if last_snapshot:
        if current_snapshot:
            change_detected, diff_image = compare_images(last_snapshot, current_snapshot)
            if change_detected:
                return True, current_snapshot, diff_image
            else:
                return False, current_snapshot, None
        return False, current_snapshot, None
    else:
        return True, current_snapshot, None

def save_differences(change_id1, change_id2, diff_image):
    new_diff = Difference(
        change_id1=change_id1,
        change_id2=change_id2,
        diff_image=diff_image.tobytes()
    )
    db.session.add(new_diff)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        Logger.getInstance().log(f"Error adding new difference: {e}")
