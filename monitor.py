from .models import db, User, Website, MonitoredWebsite, MonitoredArea, Change
from selenium import webdriver
from bs4 import BeautifulSoup
from PIL import Image
import time
import io

def monitor_websites():
    monitored_websites = MonitoredWebsite.query.all()
    for mw in monitored_websites:
        url = mw.website.url
        selector = mw.monitored_area.selector if mw.monitored_area else None
        last_change = Change.query.filter_by(monitored_area_id=mw.area_id).order_by(
            Change.change_detected_at.desc()).first()
        last_snapshot = last_change.screenshot if last_change else None
        change_detected, current_snapshot = detect_changes(url, selector, last_snapshot)
        if change_detected:
            new_change = Change(
                monitored_area_id=mw.area_id,
                change_snapshot="",  # Potresti voler salvare il contenuto HTML effettivo qui
                change_summary="Change detected",
                screenshot=current_snapshot
            )
            db.session.add(new_change)
            db.session.commit()



def take_screenshot(url, selector=None):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(2)
    
    screenshot_path = 'screenshot.png'
    driver.save_screenshot(screenshot_path)
    
    if selector:
        element = driver.find_element_by_css_selector(selector)
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
        last_image = Image.open(io.BytesIO(last_snapshot))
        current_image = Image.open(io.BytesIO(current_snapshot))
        
        if list(last_image.getdata()) == list(current_image.getdata()):
            return False, current_snapshot
        else:
            return True, current_snapshot
    else:
        return True, current_snapshot
