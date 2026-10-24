import logging
import threading
import webbrowser
from urllib.parse import urlparse

import click
from flask import Flask, request
from werkzeug.serving import make_server
from xdk.oauth2_auth import OAuth2PKCEAuth

DEFAULT_PORT = 8080
CALLBACK_PATH = "/callback"
DEFAULT_SCOPE = "tweet.read tweet.write users.read offline.access"
CALLBACK_TIMEOUT = 5 * 60

logger = logging.getLogger(__name__)


def _wait_for_callback(redirect_uri: str, timeout: float) -> str:
    """Serve the OAuth redirect URI locally and return the full callback URL."""
    parsed = urlparse(redirect_uri)
    received = threading.Event()
    result: dict[str, str] = {}

    app = Flask(__name__)

    @app.route(parsed.path)
    def callback() -> str:
        result["url"] = request.url
        received.set()
        if "error" in request.args:
            return f"Authorization failed: {request.args['error']}. You can close this tab."
        return "Authorization complete. You can close this tab."

    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    server = make_server(parsed.hostname, parsed.port or 80, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if not received.wait(timeout):
            raise click.ClickException("Timed out waiting for the OAuth callback.")
    finally:
        server.shutdown()
        thread.join()
    return result["url"]


def authenticate(
    client_id: str,
    port: int = DEFAULT_PORT,
    scope: str = DEFAULT_SCOPE,
    timeout: float = CALLBACK_TIMEOUT,
) -> dict:
    """Run the OAuth 2.0 PKCE flow and return the token dict."""
    redirect_uri = f"http://localhost:{port}{CALLBACK_PATH}"
    auth = OAuth2PKCEAuth(client_id=client_id, redirect_uri=redirect_uri, scope=scope)
    auth_url = auth.get_authorization_url()
    logger.info("Visit this URL to authorize: %s", auth_url)
    webbrowser.open(auth_url)

    callback_url = _wait_for_callback(redirect_uri, timeout)
    return auth.fetch_token(authorization_response=callback_url)
