from flask import request, jsonify, Blueprint
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from .models import db, User, Website, MonitoredWebsite, MonitoredArea, Change
from werkzeug.security import generate_password_hash, check_password_hash
import re

from .monitor import detect_changes

views = Blueprint('views', __name__)

@views.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    password = data['password']

    if not re.match(r'^(?=.*[A-Z])(?=.*\W).{8,}$', password):
        return jsonify({
            'message': 'Password must be at least 8 characters, contain at least one uppercase letter and one symbol'}), 400

    hashed_password = generate_password_hash(password, method='sha256')
    new_user = User(username=data['username'], password=hashed_password, email=data['email'])
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
