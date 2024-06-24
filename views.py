from flask import request, jsonify, Blueprint
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from logger import Logger
from .models import db, User, Website, MonitoredWebsite, MonitoredArea, Change
from werkzeug.security import generate_password_hash, check_password_hash
import re
import validators

from .monitor import detect_changes

views = Blueprint('views', __name__)


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
        return jsonify({
            'message': 'Password debole'}), 400

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    new_user = User(username=username, password=hashed_password, email=email)
    Logger.getInstance().log(f"New user: {new_user}")
    db.session.add(new_user)
    db.session.commit()
    access_token = create_access_token(identity=new_user.id)
    return jsonify(access_token=access_token), 201


@views.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password, data['password']):
        access_token = create_access_token(identity=user.id)
        return jsonify(access_token=access_token), 200
    return jsonify({'message': 'Invalid credentials'}), 401


@views.route('/websites', methods=['POST'])
@jwt_required()
def add_website():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    url = data['url']

    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    new_website = Website(url=url, name=data['name'])
    if not validators.url(new_website.url):
        return jsonify({'message': 'Invalid URL'}), 400

    db.session.add(new_website)
    db.session.commit()
    area_selector = data.get('selector')  # Use get so it returns None if the selector is not provided
    new_monitored_area = MonitoredArea(area_selector=area_selector)  # Change 'selector' to 'area_selector'
    db.session.add(new_monitored_area)
    db.session.commit()
    new_monitored_website = MonitoredWebsite(user_id=current_user_id, website_id=new_website.id,
                                             area_id=new_monitored_area.id,
                                             time_interval=data.get('time_interval', 60))
    db.session.add(new_monitored_website)
    db.session.commit()

    # Set the first Change with the current view of the page
    change_detected, current_snapshot = detect_changes(new_website.url, area_selector)
    new_change = Change(
        monitored_area_id=new_monitored_area.id,
        change_snapshot="",  # You might want to save the actual HTML content here
        change_summary="Initial snapshot",
        screenshot=current_snapshot
    )
    db.session.add(new_change)
    db.session.commit()

    return jsonify({'message': 'Website added'}), 201


@views.route('/websites', methods=['GET'])
@jwt_required()
def get_websites():
    current_user_id = get_jwt_identity()
    monitored_websites = db.session.query(MonitoredWebsite, Website).join(Website, MonitoredWebsite.website_id == Website.id).filter(MonitoredWebsite.user_id == current_user_id).all()
    websites = [
        {
            'id': mw.Website.id,
            'url': mw.Website.url,
            'name': mw.Website.name,
            'time_interval': mw.MonitoredWebsite.time_interval
        }
        for mw in monitored_websites
    ]
    return jsonify(websites), 200



@views.route('/changes', methods=['GET'])
@jwt_required()
def get_changes():
    current_user_id = get_jwt_identity()
    monitored_websites = MonitoredWebsite.query.filter_by(user_id=current_user_id).all()
    area_ids = [mw.area_id for mw in monitored_websites if mw.area_id]
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
