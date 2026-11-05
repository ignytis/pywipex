import json
import logging
import re

import click

logger = logging.getLogger(__name__)

# e.g. "window.YTD.tweets.part0 = [" (the name is "tweet" or "tweets" depending on archive version)
_PREFIX_RE = re.compile(r"\A\s*window\.YTD\.\w+\.part\d+\s*=\s*(?=\[)")


@click.command()
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("output_file", type=click.Path(dir_okay=False))
def convert(input_file: str, output_file: str) -> None:
    """Convert the tweets.js file of an X archive (data/tweets.js) to JSON Lines."""
    with open(input_file, encoding="utf-8") as f:
        text = f.read()

    match = _PREFIX_RE.match(text)
    if not match:
        raise click.ClickException(
            f"{input_file} does not look like an X archive JavaScript file (expected 'window.YTD.<name>.partN = [...]')."
        )
    try:
        records = json.loads(text[match.end():])
    except ValueError as e:
        raise click.ClickException(f"Unable to parse {input_file}: {e}") from e

    with open(output_file, "w", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("Converted %d records to %s", len(records), output_file)
