# spidtok-server/main.py
# author: Найзер (spidos team)
"""Entry point: the http endpoints the mod polls, and the telegram bot that
edits the badge table. Both share one sqlite file, so run them as one process."""

import asyncio
import logging

import api
import bot
import db


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db.init()
    api.start_in_thread()
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
