from datetime import datetime, timedelta
from threading import Thread
from selenium.common.exceptions import WebDriverException
from selenium import webdriver
import time
from flask import current_app
import cv2
from PIL import Image
from io import BytesIO
import traceback
from logger import Logger
import numpy as np

from .models import db, Change, MonitoredArea, Difference
from skimage.metrics import structural_similarity as ssim

def start_async_monitor():
    print("Starting monitor thread")
    app = current_app._get_current_object()
    monitor_thread = Thread(target=async_monitor, args=(app,))
    monitor_thread.daemon = True
    monitor_thread.start()
    print("Monitor thread started")


def accept_cookies(driver):
    return


def take_screenshot(url):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
    except WebDriverException as e:
        Logger.getInstance().log(f"URL access denied: {e.msg}")
        driver.quit()
        return None, None

    time.sleep(2)

    screenshot_path = 'current_screenshot.png'
    driver.save_screenshot(screenshot_path)
    driver.quit()

    with open(screenshot_path, "rb") as image_file:
        return image_file.read(), screenshot_path


def save_image_to_disk(image_bytes, filename):
    image = Image.open(BytesIO(image_bytes))
    image.save(filename)
    return filename

def compare_images(img1_path, img2_path):
    try:
        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)

        if img1 is None or img2 is None:
            raise ValueError("One of the images could not be loaded. Please check the paths.")

        img1_gray = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        img2_gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        if img1_gray.shape != img2_gray.shape:
            img2_gray = cv2.resize(img2_gray, (img1_gray.shape[1], img1_gray.shape[0]))

        img1_array = np.array(img1_gray, dtype=np.float32)
        img2_array = np.array(img2_gray, dtype=np.float32)

        img1_array = (img1_array - np.min(img1_array)) / (np.max(img1_array) - np.min(img1_array))
        img2_array = (img2_array - np.min(img2_array)) / (np.max(img2_array) - np.min(img2_array))

        ssim_score = ssim(img1_array, img2_array, data_range=1.0)

        diff = cv2.absdiff(img1_gray, img2_gray)
        Logger.getInstance().log(f"SSIM Score: {ssim_score}")

        img1_pil = Image.fromarray(cv2.cvtColor(img1, cv2.COLOR_BGR2RGB))
        img2_pil = Image.fromarray(cv2.cvtColor(img2, cv2.COLOR_BGR2RGB))
        diff_pil = Image.fromarray(diff)

        change_detected = ssim_score < 0.85

        return change_detected, {
            'before': img1_pil,
            'after': img2_pil,
            'diff': diff_pil,
            'ssim': ssim_score,
        }
    except Exception as e:
        # Log the error and its traceback
        error_message = f"Error comparing images: {e}"
        print(error_message)
        traceback_message = traceback.format_exc()
        print(traceback_message)
        Logger.getInstance().log(error_message)
        Logger.getInstance().log(traceback_message)
        return False, None
def detect_changes(url, last_snapshot=None):
    current_snapshot, current_snapshot_path = take_screenshot(url)

    if last_snapshot and current_snapshot:
        last_snapshot_path = save_image_to_disk(last_snapshot, 'last_screenshot.png')
        change_detected, diff_images = compare_images(current_snapshot_path, last_snapshot_path)
        return change_detected, current_snapshot, diff_images
    elif current_snapshot:
        return True, current_snapshot, None
    else:
        return False, None, None


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

                    last_changed = Change.query.filter_by(monitored_area_id=ma.id).order_by(
                        Change.change_detected_at.desc()).first()

                    change_detected, current_snapshot, diff_images = detect_changes(ma.website.url,
                                                                                    last_changed.screenshot if last_changed else None)
                    Logger.getInstance().log(f"Change detected: {change_detected}")
                    Logger.getInstance().log(f"Current snapshot exists: {'yes' if current_snapshot else 'no'}")

                    if current_snapshot is not None:
                        Logger.getInstance().log(f"Screenshot taken, change detected: {change_detected}")
                        if change_detected or not last_changed:
                            change_summary = "First screenshot" if not last_changed else "Change detected"
                            new_change = Change(monitored_area_id=ma.id, change_snapshot="",
                                                change_summary=change_summary,
                                                screenshot=current_snapshot)
                            db.session.add(new_change)
                            try:
                                db.session.commit()
                                Logger.getInstance().log(f"New change detected for {ma.website.url}")

                                if change_detected and last_changed and diff_images:
                                    save_differences(last_changed.id, new_change.id, diff_images)

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


def save_differences(change_id1, change_id2, diff_images):
    for image_type, image_data in diff_images.items():
        if image_type in ['before', 'after', 'diff']:

            new_diff = Difference(
                change_id1=change_id1,
                change_id2=change_id2,
                diff_image=image_data,
                created_at=datetime.utcnow()
            )
            db.session.add(new_diff)
        elif image_type in ['ssim', 'percent_diff']:

            change1 = Change.query.get(change_id1)
            if change1:
                summary = change1.change_summary or {}
                summary[image_type] = image_data
                change1.change_summary = str(summary)
            change2 = Change.query.get(change_id2)
            if change2:
                summary = change2.change_summary or {}
                summary[image_type] = image_data
                change2.change_summary = str(summary)
        else:
            Logger.getInstance().log(f"Unknown diff type: {image_type}")
            continue

    try:
        db.session.commit()
        Logger.getInstance().log(f"Successfully saved differences for changes {change_id1} and {change_id2}")
    except Exception as e:
        db.session.rollback()
        Logger.getInstance().log(f"Error adding new differences: {e}")