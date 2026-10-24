# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

pywipex is a `click`-based CLI that bulk-deletes tweets (X posts) via the official X API using the `xdk` SDK (v0.10.x).
It is packaged with `pyproject.toml` (hatchling, `src/` layout). There is no test suite or linter. The directory is not a git repository.

## Setup and running

```
uv venv && uv pip install -e .
.venv/bin/pywipex --help
.venv/bin/pywipex delete INPUT_FILE [--remaining-file PATH] --client-id ID [--port PORT]
```

`delete` opens a browser for the OAuth 2.0 PKCE flow; a temporary Flask server on `localhost:8080` (override with `--port`) receives the callback.
It then deletes every tweet ID in `INPUT_FILE`. Running it performs real, irreversible deletions against the authenticated
account, so don't run it without the user's explicit go-ahead.

## Architecture

- `src/pywipex/cli.py` – `click` group `main`; new commands are registered with `main.add_command(...)`.
- `src/pywipex/auth.py` – `authenticate(client_id, port=8080)`: `OAuth2PKCEAuth` with scopes `tweet.read tweet.write users.read offline.access`,
  local Flask callback server (redirect URI is `http://localhost:{port}/callback`), returns the token dict. The dict is passed to `Client(token=...)` so the SDK can refresh automatically.
- `src/pywipex/commands/delete.py` – `delete` command. Input file is one bare tweet ID per line, no header (the repo's
  `tweets_to_delete.csv` is not really CSV). `PostsClient.delete(id)` per ID; `requests.ConnectionError` is retried every 5 s
  indefinitely; the X limit is 50 deletes per 15 minutes, so it sleeps 15 min after every 50.
  If it stops early and `--remaining-file` is given, the unprocessed IDs (including the in-flight one) are written there (`try/finally`).

Notes:
- Logging uses stdlib `logging`, configured once in `cli.py` (`%(asctime)s %(levelname)s %(message)s`, no logger name). Use `logging.getLogger(__name__)` in modules instead of `click.echo` for status output.
- API errors other than `ConnectionError` (e.g. 429, already-deleted tweets) are not handled; they abort the run (the remaining file is still written).
- The OAuth client ID is required (`--client-id` / `PYWIPEX_CLIENT_ID`); there is no default and no persistent config.
