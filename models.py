from datetime import datetime, timedelta
from . import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Website(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class MonitoredArea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    website_id = db.Column(db.Integer, db.ForeignKey('website.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    area_selector = db.Column(db.String(500), nullable=False)
    time_interval = db.Column(db.Integer, nullable=False, default=60)
    last_change_checked = db.Column(db.DateTime, nullable=True)

    website = db.relationship('Website', backref=db.backref('monitored_areas', lazy=True))
    changes = db.relationship('Change', back_populates='monitored_area', cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super(MonitoredArea, self).__init__(**kwargs)
        self.last_change_checked = None  # Explicitly set to None for new instances

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'website_id': self.website_id,
            'name': self.name,
            'area_selector': self.area_selector,
            'time_interval': self.time_interval,
            'last_change_checked': self.last_change_checked.isoformat() if self.last_change_checked else None,
            'changes': [change.to_dict() for change in self.changes]
        }


class Change(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monitored_area_id = db.Column(db.Integer, db.ForeignKey('monitored_area.id'), nullable=False)
    change_detected_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    change_snapshot = db.Column(db.Text, nullable=False)
    change_summary = db.Column(db.Text)
    screenshot = db.Column(db.LargeBinary, nullable=False)
    reviewed = db.Column(db.Boolean, default=False)

    monitored_area = db.relationship('MonitoredArea', back_populates='changes')
    differences1 = db.relationship('Difference', foreign_keys='Difference.change_id1', back_populates='change1',
                                   cascade="all, delete-orphan")
    differences2 = db.relationship('Difference', foreign_keys='Difference.change_id2', back_populates='change2',
                                   cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'monitored_area_id': self.monitored_area_id,
            'change_detected_at': self.change_detected_at.isoformat(),
            'change_snapshot': self.change_snapshot,
            'change_summary': self.change_summary,
            'screenshot': self.screenshot.decode('utf-8') if self.screenshot else None,
            'reviewed': self.reviewed,
            'differences1': [difference.to_dict() for difference in self.differences1],
            'differences2': [difference.to_dict() for difference in self.differences2]
        }


class Difference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    change_id1 = db.Column(db.Integer, db.ForeignKey('change.id'), nullable=False)
    change_id2 = db.Column(db.Integer, db.ForeignKey('change.id'), nullable=False)
    diff_image = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    change1 = db.relationship('Change', foreign_keys=[change_id1], back_populates='differences1')
    change2 = db.relationship('Change', foreign_keys=[change_id2], back_populates='differences2')

    def to_dict(self):
        return {
            'id': self.id,
            'change_id1': self.change_id1,
            'change_id2': self.change_id2,
            'diff_image': self.diff_image.decode('utf-8') if self.diff_image else None,
            'created_at': self.created_at.isoformat()
        }
