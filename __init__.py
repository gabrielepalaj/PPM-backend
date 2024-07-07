from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS

db = SQLAlchemy()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.config.from_object('config.Config')

    db.init_app(app)
    jwt.init_app(app)

    with app.app_context():
        from . import views
        db.create_all()
        app.register_blueprint(views.views)
        from .monitor import start_async_monitor
        start_async_monitor()
        print(app.url_map)

    return app
