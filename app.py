from flask import Flask, jsonify
from logging.config import dictConfig
from config import DevConfig
from rotas.api import api_bp
from rotas.paginas import paginas_bp
from banco_dados.modelos import db

def configurar_logging():
    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"default": {"format": "%(asctime)s [%(levelname)s] %(message)s"}},
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default"}},
        "root": {"level": "INFO", "handlers": ["console"]},
    })

def create_app(config=DevConfig):
    configurar_logging()
    app = Flask(__name__)
    app.config.from_object(config)
    db.init_app(app)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(paginas_bp)

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Recurso não encontrado"}), 404

    @app.errorhandler(500)
    def internal(e):
        return jsonify({"error": "Erro interno no servidor"}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
