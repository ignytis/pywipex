import logging

import click

from pywipex.commands.delete import delete


@click.group()
def main() -> None:
    """Tools for cleaning up an X (Twitter) account."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


main.add_command(delete)
