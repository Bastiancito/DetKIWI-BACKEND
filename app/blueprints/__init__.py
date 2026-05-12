def create_app():
    app = Flask(__name__)

    from app.blueprints.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    from app.blueprints.upload import upload_bp
    app.register_blueprint(upload_bp, url_prefix='/api/upload')

    from app.blueprints.cases import cases_bp
    app.register_blueprint(cases_bp, url_prefix='/api/cases')

    from app.blueprints.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')

    return app