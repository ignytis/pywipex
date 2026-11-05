import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import click
from simpleeval import EvalWithCompoundTypes, InvalidExpression

logger = logging.getLogger(__name__)

# Format of "created_at" in X archives, e.g. "Wed Oct 10 20:19:24 +0000 2018"
_CREATED_AT_FORMAT = "%a %b %d %H:%M:%S %z %Y"

_FUNCTIONS = {
    "len": len,
    "lower": lambda s: str(s).lower(),
    "contains": lambda s, sub: sub in s,
    "re_search": lambda pattern, s: re.search(pattern, s) is not None,
}


def _tweet_names(record: dict[str, Any]) -> dict[str, Any]:
    """Variables available in filter expressions."""
    tweet = record["tweet"]
    created_at = datetime.strptime(tweet["created_at"], _CREATED_AT_FORMAT).astimezone(timezone.utc)
    return {
        "id": str(tweet.get("id_str") or tweet["id"]),
        # UTC, 'YYYY-MM-DD HH:MM:SS': compares correctly with plain string literals
        "created_time": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "favorite_count": int(tweet.get("favorite_count", 0)),
        "retweet_count": int(tweet.get("retweet_count", 0)),
        "full_text": tweet.get("full_text", ""),
    }


@click.command("filter")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("output_file", type=click.Path(dir_okay=False))
@click.option(
    "-e",
    "--expression",
    required=True,
    help="Python-like expression; records for which it is true are kept. "
    "Variables: id, created_time, favorite_count, retweet_count, full_text. "
    "Functions: len, lower, contains(text, sub), re_search(pattern, text).",
)
def filter_command(input_file: str, output_file: str, expression: str) -> None:
    """Keep only the tweets of a JSON Lines file (see `convert`) matching an expression."""
    evaluator = EvalWithCompoundTypes(functions=_FUNCTIONS)
    # Fail early on syntax errors / unknown names
    evaluator.names = _tweet_names(
        {"tweet": {"id_str": "0", "created_at": "Mon Jan 01 00:00:00 +0000 2018", "full_text": ""}}
    )
    try:
        evaluator.eval(expression)
    except (InvalidExpression, SyntaxError) as e:
        raise click.ClickException(f"Invalid expression: {e}") from e
    except TypeError:
        pass  # sample data may not suit the expression; real records are checked below

    total = kept = 0
    with open(input_file, encoding="utf-8") as src, open(output_file, "w", encoding="utf-8") as dst:
        for line_no, line in enumerate(src, 1):
            if not line.strip():
                continue
            total += 1
            try:
                evaluator.names = _tweet_names(json.loads(line))
                matched = evaluator.eval(expression)
            except (ValueError, KeyError) as e:
                raise click.ClickException(f"Line {line_no}: unable to read the tweet: {e!r}") from e
            except (InvalidExpression, TypeError) as e:
                raise click.ClickException(f"Line {line_no}: unable to evaluate the expression: {e}") from e
            if matched:
                dst.write(line if line.endswith("\n") else line + "\n")
                kept += 1
    logger.info("Kept %d of %d tweets, written to %s", kept, total, output_file)
