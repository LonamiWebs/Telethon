"""
This file is only the "core" of the bot. It is responsible for loading the
plugins module and initializing it. You may obtain the plugins by running:

    git clone https://github.com/Lonami/TelethonianBotExt plugins

In the same folder where this file lives. As a result, the directory should
look like the following:

    assistant.py
    plugins/
        ...
"""
import asyncio
import os
import sys
import time

from telethon import TelegramClient

try:
    # Standalone script assistant.py with folder plugins/
    import plugins
except ImportError:
    try:
        # Running as a module with `python -m assistant` and structure:
        #
        #     assistant/
        #         __main__.py (this file)
        #         plugins/    (cloned)
        from . import plugins
    except ImportError:
        print('could not load the plugins module, does the directory exist '
              'in the correct location?', file=sys.stderr)

        exit(1)


def get_env(name, message, cast=str):
    if name in os.environ:
        return os.environ[name]
    while True:
        value = input(message)
        try:
            return cast(value)
        except ValueError as e:
            print(e, file=sys.stderr)
            time.sleep(1)


API_ID = get_env('TG_API_ID', 'Enter your API ID: ', int)
API_HASH = get_env('TG_API_HASH', 'Enter your API hash: ')
TOKEN = get_env('TG_TOKEN', 'Enter the bot token: ')
NAME = TOKEN.split(':')[0]


async def main():
    bot = TelegramClient(NAME, API_ID, API_HASH)

    await bot.start(bot_token=TOKEN)

    try:
        await plugins.init(bot)
        await bot.run_until_disconnected()
    finally:
        await bot.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
