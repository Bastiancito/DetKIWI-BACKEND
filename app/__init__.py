from flask import Flask
from config import Config
from app.extensions import db, migrate, jwt, cors

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    
    from app.blueprints.auth import auth_bp
    from app.blueprints.sedes import sedes_bp
    from app.blueprints.estudiante import estudiante_bp
    from app.blueprints.paralelos import paralelos_bp
    from app.blueprints.roles import roles_bp
    from app.blueprints.users import users_bp
    from app.blueprints.reporte import reportes_bp
    from app.blueprints.casos import casos_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.evaluaciones import evaluaciones_bp
    from app.blueprints.periodos import periodos_bp
    from app.blueprints.casos_sancionados import casos_sancionados_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(sedes_bp, url_prefix='/api/sedes')
    app.register_blueprint(estudiante_bp, url_prefix='/api/estudiante')
    app.register_blueprint(paralelos_bp, url_prefix='/api/paralelos')
    app.register_blueprint(roles_bp, url_prefix='/api/roles')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(reportes_bp, url_prefix='/api/reportes')
    app.register_blueprint(casos_bp, url_prefix='/api/casos')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(evaluaciones_bp, url_prefix='/api/evaluaciones')
    app.register_blueprint(periodos_bp, url_prefix='/api/periodos')
    app.register_blueprint(casos_sancionados_bp, url_prefix='/api/casos_sancionados')

    @app.route('/api/health')
    def health_check():
        return {"status": "ok", "message": "Detective KIWI API funcionando 🥝"}

    return app