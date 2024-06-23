from flask import request, jsonify, Blueprint
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from logger import Logger
from .models import db, User, Website, MonitoredWebsite, MonitoredArea, Change
from werkzeug.security import generate_password_hash, check_password_hash
import re

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
    new_website = Website(url=data['url'], name=data['name'])
    db.session.add(new_website)
    db.session.commit()
    new_monitored_website = MonitoredWebsite(user_id=current_user_id, website_id=new_website.id,
                                             time_interval=data.get('time_interval', 60))
    db.session.add(new_monitored_website)
    db.session.commit()
    return jsonify({'message': 'Website added'}), 201


@views.route('/websites', methods=['GET'])
@jwt_required()
def get_websites():
    current_user_id = get_jwt_identity()
    monitored_websites = MonitoredWebsite.query.filter_by(user_id=current_user_id).all()
    websites = [
        {
            'id': mw.website.id,
            'url': mw.website.url,
            'name': mw.website.name,
            'time_interval': mw.time_interval
        }
        for mw in monitored_websites
    ]
    return jsonify(websites), 200


@views.route('/monitor', methods=['POST'])
@jwt_required()
def monitor_site():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    monitored_website = MonitoredWebsite.query.filter_by(user_id=current_user_id, website_id=data['website_id']).first()
    if not monitored_website:
        return jsonify({'message': 'Website not found or not authorized'}), 404

    url = monitored_website.website.url
    selector = data.get('selector')
    monitored_area = MonitoredArea.query.filter_by(id=data['area_id']).first()

    if not monitored_area:
        return jsonify({'message': 'Monitored area not found'}), 404

    last_change = Change.query.filter_by(monitored_area_id=monitored_area.id).order_by(
        Change.change_detected_at.desc()).first()
    last_snapshot = last_change.screenshot if last_change else None

    change_detected, current_snapshot = detect_changes(url, selector, last_snapshot)

    if change_detected:
        new_change = Change(
            monitored_area_id=monitored_area.id,
            change_snapshot="",  # Potresti voler salvare il contenuto HTML effettivo qui
            change_summary="Change detected",
            screenshot=current_snapshot
        )
        db.session.add(new_change)
        db.session.commit()
        return jsonify({'message': 'Change detected', 'screenshot': 'path/to/screenshot'}), 200
    else:
        return jsonify({'message': 'No change detected'}), 200


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
