"""Flask 앱 진입점."""

from flask import Flask
from flask_cors import CORS

from backend.routes.convert import convert_bp


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(convert_bp)

    @app.route("/api/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
