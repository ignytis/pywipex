# pywipex

A command-line tool for cleaning up an X (Twitter) account through the official X API, built on the
[`xdk`](https://pypi.org/project/xdk/) SDK. Currently it can bulk-delete tweets; more commands (e.g. ones that
prepare the list of tweets to delete) are planned.

> **Warning:** deletions are real and irreversible.

## Prerequisites

- Python 3.10+ and [`uv`](https://docs.astral.sh/uv/)
- An X developer app with OAuth 2.0 enabled, the callback URL `http://localhost:8080/callback` registered
  (or `http://localhost:PORT/callback` if you use `--port`),
  and the scopes `tweet.read tweet.write users.read offline.access`.

## Installation

```
uv venv
uv pip install -e .
```

Then either activate the venv (`source .venv/bin/activate`) or call `.venv/bin/pywipex` directly.

## Usage

```
pywipex --help
pywipex delete INPUT_FILE [--remaining-file PATH] --client-id ID [--port PORT]
```

### `delete`

Deletes every tweet listed in `INPUT_FILE`: a plain text file with one tweet ID per line (no header; blank lines ignored).

1. A browser window opens for the OAuth 2.0 PKCE authorization. A temporary local server on `localhost:8080` (configurable with `--port`)
   receives the callback automatically; nothing needs to be pasted.
2. Tweets are deleted one by one. Connection errors are retried every 5 seconds.
3. The X API allows 50 deletions per 15 minutes, so the tool sleeps 15 minutes after every 50 deletions.

Progress is logged to stderr with a date and time on every line.

Options:

- `--remaining-file PATH` – if the run stops early (Ctrl+C, API error, ...), the not-yet-processed IDs
  (including the one that was in flight) are written to this file in the same format as the input.
  Re-run with that file as `INPUT_FILE` to resume. The file is not created when everything was deleted.
- `--client-id ID` (env `PYWIPEX_CLIENT_ID`) – **required**. OAuth 2.0 client ID of your X app.
- `--port PORT` – local port for the callback server (default 8080). Use it if 8080 is busy; the matching callback URL must be registered in the X app.

Example:

```
pywipex delete tweets_to_delete.csv --client-id YOUR_ID --remaining-file remaining.txt
```

## Development

Source lives in `src/pywipex/`:

- `cli.py` – the `click` group; commands are registered with `main.add_command(...)`.
- `auth.py` – OAuth PKCE flow with a temporary Flask callback server.
- `commands/` – one module per command.

To add a command, create a module in `commands/` exposing a `click.command` and register it in `cli.py`.
