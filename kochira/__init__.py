import asyncio

import click

from .bot import Bot


@click.command
@click.option('--config', default='config.yml', help="Configuration file.")
@click.option('--console', is_flag=True, default=False, help="Whether to start the console instead of the bot.")
def main(config: str, console: bool) -> None:
    import os
    import logging

    if not os.path.exists(config):
        logging.error("""\
Could not find the configuration file: %s

If this is your first time starting Kochira, copy the file `config.yml.dist` to
`config.yml` and edit it appropriately.
""", config)
        return

    bot = Bot(config)
    if console:
        banner = """\
Welcome to the Kochira console!

Variables:
bot     -> current bot
"""
        my_locals = {"bot": bot}
        try:
            import IPython
        except ImportError:
            import code
            code.interact(banner, local=my_locals)
        else:
            IPython.embed(banner1=banner, user_ns=my_locals)

    else:
        asyncio.run(bot.run())
