from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    host = Config.HOST
    port = Config.PORT
    print(f"Starting Nourish server on http://localhost:{port} (bound to {host}:{port})...")
    app.run(host=host, port=port, debug=True)
