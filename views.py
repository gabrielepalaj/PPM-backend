import base64
import socket
from flask import request, jsonify, Blueprint
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError
from .models import db, User, Website, MonitoredArea, Change
from werkzeug.security import generate_password_hash, check_password_hash
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException
from validators import url as validate_url
from .models import Website, MonitoredArea
from .logger import Logger
import requests
from urllib.parse import urlparse
import time

views = Blueprint('views', __name__)

def getIdJWT():
    return get_jwt_identity()["id"]

def getUsernameJWT():
    return get_jwt_identity()["username"]

def JWTIdentity(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email
    }

@views.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    username = data['username']
    email = data['email']
    password = data['password']

    user = User.query.filter_by(username=username).first()
    if user:
        return jsonify({'message': 'Username already exists'}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({'message': 'Email already exists'}), 400

    if not re.match(r'^(?=.*[A-Z])(?=.*\W).{8,}$', password):
        return jsonify({'message': 'Weak password'}), 400

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    new_user = User(username=username, password=hashed_password, email=email)
    Logger.getInstance().log(f"New user: {new_user}")
    db.session.add(new_user)
    db.session.commit()
    access_token = create_access_token(identity=JWTIdentity(new_user))
    return jsonify(access_token=access_token), 201

@views.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password, data['password']):
        access_token = create_access_token(identity=JWTIdentity(user))
        return jsonify(access_token=access_token), 200
    return jsonify({'message': 'Invalid credentials'}), 401

def check_new_website(user_id, name, url):
    if url:
        # Normalizza l'URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # Valida l'URL
        if not validate_url(url):
            return jsonify({'message': 'Invalid URL'}), 400

        # Controlla se il dominio è valido
        parsed_url = urlparse(url)
        try:
            socket.gethostbyname(parsed_url.netloc)
        except socket.gaierror:
            return jsonify({'message': 'Invalid domain'}), 400

        # Controlla se il sito è già monitorato dall'utente
        existing_website = Website.query.filter_by(url=url).first()
        if existing_website and MonitoredArea.query.filter_by(user_id=user_id, website_id=existing_website.id).first():
            return jsonify({'message': 'You are already monitoring this website'}), 400

        # Configura le opzioni di Chrome
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')

        try:
            with webdriver.Chrome(options=options) as driver:
                driver.set_page_load_timeout(5)
                driver.get(url)
                time.sleep(2)

                # Verifica se la pagina è stata caricata correttamente
                if "This site can't be reached" in driver.title or "Access Denied" in driver.page_source:
                    raise WebDriverException("Page couldn't be loaded")

                # Se arriviamo qui, il sito è accessibile
        except (WebDriverException, TimeoutException) as e:
            Logger.getInstance().log(f"URL access denied or timed out: {str(e)}")
            return jsonify({'message': 'Website does not exist or is not accessible'}), 400

    # Controlla se il nome è già utilizzato dall'utente
    if name and MonitoredArea.query.filter_by(user_id=user_id, name=name).first():
        return jsonify({'message': 'You are already using this name for another monitored area'}), 400

    return '', 200
@views.route('/websites', methods=['POST'])
@jwt_required()
def add_website():
    current_user_id = getIdJWT()
    data = request.get_json()
    url = data['url']
    name = data.get('name')
    area_selector = data.get('selector')
    time_interval = data.get('time_interval', 60)

    try:
        error, status = check_new_website(current_user_id, name, url)
        if error != '':
            return error, status

        existing_website = Website.query.filter_by(url=url).first()
        if not existing_website:
            website = Website(url=url)
            db.session.add(website)
            db.session.commit()
        else:
            website = existing_website

        # Crea l'area monitorata
        new_monitored_area = MonitoredArea(
            user_id=current_user_id,
            website_id=website.id,
            name=name,
            area_selector=area_selector,
            time_interval=time_interval
        )
        db.session.add(new_monitored_area)
        db.session.commit()

        return jsonify({'message': 'Website and monitored area added'}), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': 'Database error', 'error': str(e)}), 500
    except ValueError as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500


@views.route('/websites/<int:monitoredarea_id>', methods=['PUT'])
@jwt_required()
def update_website(monitoredarea_id):
    current_user_id = getIdJWT()
    data = request.get_json()
    name = data.get('name', '')
    url = data.get('url', '')
    area_selector = data.get('selector', '')
    time_interval = data.get('time_interval', 60)

    try:
        monitored_area = MonitoredArea.query.filter_by(id=monitoredarea_id, user_id=current_user_id).first()
        if not monitored_area:
            return jsonify({'message': 'Monitored area not found'}), 404

        if monitored_area.website.url == url:
            url = ''
        if monitored_area.name == name:
            name = ''

        error, status = check_new_website(current_user_id, name, url)
        if error != '':
            return error, status

        if name != '':
            monitored_area.name = name
        if url != '':
            monitored_area.website.url = url

        db.session.commit()

        return jsonify({'message': 'Monitored area updated successfully'}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': 'Database error', 'error': str(e)}), 500
    except ValueError as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500


@views.route('/websites/<int:monitoredarea_id>', methods=['DELETE'])
@jwt_required()
def delete_website(monitoredarea_id):
    current_user_id = getIdJWT()
    try:
        monitored_area = MonitoredArea.query.filter_by(id=monitoredarea_id, user_id=current_user_id).first()
        if not monitored_area:
            return jsonify({'message': 'Monitored area not found'}), 404

        db.session.delete(monitored_area)
        db.session.commit()

        return jsonify({'message': 'Monitored area deleted successfully'}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': 'Database error', 'error': str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500


@views.route('/websites', methods=['GET'])
@jwt_required()
def get_websites():
    current_user_id = getIdJWT()
    monitored_areas = db.session.query(MonitoredArea).join(Website, MonitoredArea.website_id == Website.id).filter(
        MonitoredArea.user_id == current_user_id).all()

    def change_to_dict(change):
        if change is None:
            return None
        return {
            'id': change.id,
            'monitored_area_id': change.monitored_area_id,
            'change_detected_at': change.change_detected_at.isoformat(),
            'change_snapshot': change.change_snapshot,
            'change_summary': change.change_summary,
            'screenshot': base64.b64encode(change.screenshot).decode('utf-8') if change.screenshot else None,
            'reviewed': change.reviewed
        }

    websites = [
        {
            'id': ma.id,
            'url': ma.website.url,
            'name': ma.name,
            'time_interval': ma.time_interval,
            'last_change': change_to_dict(db.session.query(Change).filter_by(monitored_area_id=ma.id).order_by(
                Change.change_detected_at.desc()).first()),
            'previous_change': change_to_dict(db.session.query(Change).filter_by(monitored_area_id=ma.id).order_by(
                Change.change_detected_at.desc()).offset(1).first())
        }
        for ma in monitored_areas
    ]
    return jsonify(websites), 200

@views.route('/changes/<int:change_id>/read', methods=['POST'])
@jwt_required()
def mark_change_as_read(change_id):
    current_user_id = getIdJWT()
    change = Change.query.filter_by(id=change_id).join(MonitoredArea).filter(MonitoredArea.user_id == current_user_id).first()
    if not change:
        return jsonify({'message': 'Change not found'}), 404

    change.reviewed = True
    db.session.commit()
    return jsonify({'message': 'Change marked as read'}), 200

@views.route('/changes', methods=['GET'])
@jwt_required()
def get_changes():
    current_user_id = getIdJWT()
    monitored_areas = MonitoredArea.query.filter_by(user_id=current_user_id).all()
    area_ids = [ma.id for ma in monitored_areas]
    changes = Change.query.filter(Change.monitored_area_id.in_(area_ids)).all()
    changes_list = [
        {
            'id': change.id,
            'monitored_area_id': change.monitored_area_id,
            'change_detected_at': change.change_detected_at,
            'change_summary': change.change_summary,
            'screenshot': change.screenshot
        }
        for change in changes
    ]
    return jsonify(changes_list), 200

@views.route('/verify', methods=['POST'])
@jwt_required()
def verify():
    current_user_id = getIdJWT()
    if not User.query.filter_by(id=current_user_id).first():
        return jsonify({'message': 'User not found'}), 404

    return jsonify({"msg": "Token is valid", "user_id": current_user_id}), 200

@views.route('/health', methods=['GET'])
def health():
    return jsonify({"msg": "OK"}), 200