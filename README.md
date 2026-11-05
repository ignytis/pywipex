# pywipex

A command-line tool for cleaning up an X (Twitter) account through the official X API, built on the
[`xdk`](https://pypi.org/project/xdk/) SDK. It can convert an X archive to JSON Lines, filter tweets with
expressions, and bulk-delete them.

> **Warning:** deletions are real and irreversible.

## Prerequisites

- Python 3.10+ and [`uv`](https://docs.astral.sh/uv/)
- An X developer app with OAuth 2.0 enabled and a funded (paid) developer account; see
  [Setting up the X app](#setting-up-the-x-app).

## Setting up the X app

> **Warning: the X API is paid.** X uses pay-per-use pricing: you buy credits upfront in the Developer Console
> (with a payment method such as a credit card) and each API request draws them down. Deleting posts through the API
> is a billable write request, so you must top up the developer account before `pywipex delete` will work.
> The pricing page lists "Interaction: Delete" at about $0.01 per request, but does not name `DELETE /2/tweets/:id`
> explicitly, so check the current rates at <https://docs.x.com/x-api/getting-started/pricing> and estimate the cost
> for your number of tweets first. Without credits the API returns an error and the run aborts
> (the `--remaining-file` is still written).

1. Sign in at <https://developer.x.com> and sign up for a developer account.
2. In the Developer Console, create an app (inside a Project if prompted).
3. Add credits under the billing section of the Developer Console.
4. Open the app's settings, find **User authentication settings** and click **Set up**:
   - **App permissions:** Read and write
   - **Type of App:** Native App (public client, PKCE; no client secret is needed). Choosing "Web App" can cause an
     `unauthorized_client` error.
   - **Callback URI / Redirect URL:** `http://localhost:8080/callback`
     (or `http://localhost:PORT/callback` if you use `--port`)
   - **Website URL:** any valid URL (the form requires one)
   - Save. The scopes pywipex requests are `tweet.read tweet.write users.read offline.access`.
5. Open the **Keys and tokens** tab and copy the **OAuth 2.0 Client ID** (it appears only after step 4). Ignore the
   API Key/Secret, Bearer Token and Client Secret; pywipex does not use them.
6. Pass the ID with `--client-id`, or export it: `export PYWIPEX_CLIENT_ID=YOUR_ID`.
   To keep it out of your shell history, store it in a file (outside version control) and read it from there:
   `pywipex delete tweets_to_delete.jsonl --client-id "$(cat path/to/client_id)"`.

The portal UI changes from time to time, so field names may differ slightly.

## Installation

```
uv sync
```

`uv sync` creates `.venv` from the committed `uv.lock` and installs the project in editable mode. Then either activate the venv (`source .venv/bin/activate`) or call `.venv/bin/pywipex` directly.

## Usage

```
pywipex --help
pywipex convert TWEETS_JS OUTPUT_JSONL
pywipex filter INPUT_JSONL OUTPUT_JSONL -e EXPRESSION
pywipex delete INPUT_FILE [--remaining-file PATH] --client-id ID [--port PORT]
```

Typical workflow: request your [X archive](https://help.x.com/en/managing-your-account/how-to-download-your-x-archive),
`convert` its `data/tweets.js`, `filter` the result, then `delete` the filtered file.

### `convert`

`pywipex convert data/tweets.js tweets.jsonl` turns the JavaScript file of the archive into JSON Lines (one `{"tweet": {...}}` record per line).

### `filter`

Keeps the records for which a Python-style expression is true:

```
pywipex filter tweets.jsonl filtered.jsonl -e "created_time >= '2022-01-01 00:00:00' and created_time < '2022-02-01 00:00:00'"
pywipex filter tweets.jsonl filtered.jsonl -e "favorite_count + retweet_count * 20 > 100"
pywipex filter tweets.jsonl filtered.jsonl -e "contains(lower(full_text), 'giveaway')"
```

- Variables: `id` (string), `created_time` (UTC string `YYYY-MM-DD HH:MM:SS`), `favorite_count`, `retweet_count` (ints), `full_text`.
- Operators: arithmetic, comparisons, `and` / `or` / `not` (not `&&` / `||`), `in`.
- Functions: `len`, `lower`, `contains(text, sub)`, `re_search(pattern, text)`.
- Expressions are evaluated with [`simpleeval`](https://pypi.org/project/simpleeval/), a sandboxed evaluator, not Python's `eval`.

### `delete`

Deletes every tweet listed in `INPUT_FILE`: one tweet per line, either a bare tweet ID or a JSON Lines record as produced by `filter`
(no header; blank lines ignored).

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
- `commands/` – one module per command (`convert`, `filter`, `delete`).

To add a command, create a module in `commands/` exposing a `click.command` and register it in `cli.py`.
