from . import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class MonitoredWebsite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    website_id = db.Column(db.Integer, db.ForeignKey('website.id'), nullable=False)
    area_id = db.Column(db.Integer, db.ForeignKey('monitored_area.id'))
    time_interval = db.Column(db.Integer, nullable=False, default=60)

class Website(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class MonitoredArea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    area_selector = db.Column(db.String(500), nullable=False)

class Change(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monitored_area_id = db.Column(db.Integer, db.ForeignKey('monitored_area.id'), nullable=False)
    change_detected_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    change_snapshot = db.Column(db.Text, nullable=False)
    change_summary = db.Column(db.Text)
    screenshot = db.Column(db.LargeBinary, nullable=False)
    reviewed = db.Column(db.Boolean, default=False)
