from flask import Flask
from flask_cors import CORS

from .extensions import db


def create_app():
    app = Flask(__name__)
    CORS(app)

    # Load configuration
    try:
        app.config.from_object('config.Config')
    except Exception:
        # Fallback to module-level config values
        import config as _cfg
        app.config.update({k: v for k, v in vars(_cfg).items() if k.isupper()})

    # Initialize extensions
    db.init_app(app)

    # Register routes blueprint
    from .routes import api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='')

    return app
