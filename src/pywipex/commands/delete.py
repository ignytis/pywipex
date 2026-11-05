import json
import logging
import time
from datetime import datetime, timedelta

import click
from requests.exceptions import ConnectionError, HTTPError
from xdk import Client
from xdk.posts import PostsClient

from pywipex.auth import DEFAULT_PORT, authenticate

# X API limit: 50 deletes per 15 minutes
RATE_LIMIT_BATCH = 50
RATE_LIMIT_SLEEP = 15 * 60
RETRY_DELAY = 5

logger = logging.getLogger(__name__)


def _read_ids(path: str) -> list[str]:
    """Read tweet IDs: one per line, either a bare ID or a JSON Lines record (see `filter`)."""
    ids = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                try:
                    record = json.loads(line)
                    tweet = record.get("tweet", record)
                    line = str(tweet.get("id_str") or tweet["id"])
                except (ValueError, KeyError, AttributeError) as e:
                    raise click.ClickException(f"{path}, line {line_no}: cannot find a tweet ID ({e!r})") from e
            ids.append(line)
    return ids


def _describe_http_error(error: HTTPError) -> str:
    """Build a message with the details X returned in the response body."""
    response = error.response
    if response is None:
        return str(error)

    message = f"{response.status_code} {response.reason}"
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        details = [str(body[k]) for k in ("title", "detail") if body.get(k)]
        for item in body.get("errors") or []:
            if isinstance(item, dict) and item.get("message"):
                details.append(str(item["message"]))
        text = ": ".join(details) if details else response.text.strip()
    else:
        text = response.text.strip()
    if text:
        message += f" - {text}"

    reset = response.headers.get("x-rate-limit-reset")
    if response.status_code == 429 and reset and reset.isdigit():
        message += f" (rate limit resets at {datetime.fromtimestamp(int(reset)).strftime('%H:%M:%S')})"
    return message


def _write_remaining(path: str, ids: list[str]) -> None:
    with open(path, "w") as f:
        f.writelines(f"{tweet_id}\n" for tweet_id in ids)


@click.command()
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--remaining-file",
    type=click.Path(dir_okay=False),
    help="If the run stops before all tweets are deleted, write the unprocessed IDs here.",
)
@click.option(
    "--client-id",
    envvar="PYWIPEX_CLIENT_ID",
    required=True,
    help="OAuth 2.0 client ID of the X app (env: PYWIPEX_CLIENT_ID).",
)
@click.option(
    "--port",
    type=click.IntRange(1, 65535),
    default=DEFAULT_PORT,
    show_default=True,
    help="Local port for the OAuth callback server. The callback URL http://localhost:PORT/callback must be registered in the X app.",
)
def delete(input_file: str, remaining_file: str | None, client_id: str, port: int) -> None:
    """Delete the tweets listed in INPUT_FILE (one tweet ID per line)."""
    ids = _read_ids(input_file)
    tokens = authenticate(client_id, port=port)
    client = Client(token=tokens)
    posts_client = PostsClient(client)

    done = 0  # index of the next unprocessed ID
    batch_count = 0
    try:
        while done < len(ids):
            tweet_id = ids[done]
            while True:
                try:
                    logger.info("Deleting tweet with ID: '%s'", tweet_id)
                    posts_client.delete(tweet_id)
                    break
                except ConnectionError:
                    logger.warning("Connection error occurred. Retrying in %d seconds...", RETRY_DELAY)
                    time.sleep(RETRY_DELAY)
                except HTTPError as e:
                    logger.error("X API rejected deletion of tweet '%s': %s", tweet_id, _describe_http_error(e))
                    raise click.exceptions.Exit(1) from e

            done += 1
            batch_count += 1
            if batch_count == RATE_LIMIT_BATCH and done < len(ids):
                resume_at = datetime.now() + timedelta(seconds=RATE_LIMIT_SLEEP)
                logger.info("Rate limit reached. Pausing for 15 minutes, will resume at %s.", resume_at.strftime("%H:%M:%S"))
                time.sleep(RATE_LIMIT_SLEEP)
                # The server drops idle keep-alive connections; start with a fresh one
                client.session.close()
                batch_count = 0
    finally:
        if remaining_file and done < len(ids):
            _write_remaining(remaining_file, ids[done:])
            logger.warning("Remaining %d tweet IDs written to %s", len(ids) - done, remaining_file)
