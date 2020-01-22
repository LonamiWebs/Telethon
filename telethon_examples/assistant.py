import asyncio
import html
import logging
import os
import re
import sys
import time
import urllib.parse

from telethon import TelegramClient, events, types, custom, utils, errors

logging.basicConfig(level=logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.ERROR)

try:
    import aiohttp
except ImportError:
    aiohttp = None
    logging.warning('aiohttp module not available; #haste command disabled')


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
bot = TelegramClient(NAME, API_ID, API_HASH)


# ============================== Constants ==============================
WELCOME = {
    -1001109500936:
    'Hi and welcome to the group. Before asking any questions, **please** '
    'read [the docs](https://docs.telethon.dev/). Make sure you are '
    'using the latest version with `pip3 install -U telethon`, since most '
    'problems have already been fixed in newer versions.',

    -1001200633650:
    'Welcome to the off-topic group. Feel free to talk, ask or test anything '
    'here, politely. Check the description if you need to test more spammy '
    '"features" of your or other people\'s bots (sed commands too).'
}

READ_FULL = (
    'Please read [Accessing the Full API](https://docs.telethon.dev'
    '/en/latest/concepts/full-api.html)'
)

SEARCH = (
    'Remember [search is your friend]'
    '(https://tl.telethon.dev/?q={}&redirect=no)'
)

DOCS = 'TL Reference for [{}](https://tl.telethon.dev/?q={})'
RTD = '[Read The Docs!](https://docs.telethon.dev)'
RTFD = '[Read The F* Docs!](https://docs.telethon.dev)'
UPDATES = (
    'Check out [Working with Updates](https://docs.telethon.dev'
    '/en/latest/basic/updates.html) in the documentation.'
)

SPAM = (
    "Telethon is free software. That means using it is a right: you are " 
    "free to use it for absolutely any purpose whatsoever. However, help "
    "and support with using it is a privilege. If you misbehave or want "
    "to do bad things, nobody is obligated to help you and you're not "
    "welcome here."
)

OFFTOPIC = {
    -1001109500936:
    'That is not related to Telethon. '
    'You may continue the conversation in @TelethonOffTopic',
    -1001200633650:
    'That seems to be related to Telethon. Try asking in @TelethonChat'
}

UNKNOWN_OFFTOPIC = (
    "I don't know of any off-topic group for this chat! Maybe you want to "
    "visit the on-topic @TelethonChat, or the off-topic @TelethonOffTopic?"
)

ASK = (
    "Hey, that's not how you ask a question! If you want helpful advice "
    "(or any response at all) [read this first](https://stackoverflow.com"
    "/help/how-to-ask) and then ask again. If you have the time, [How To "
    "Ask Questions The Smart Way](catb.org/~esr/faqs/smart-questions.html)"
    " is another wonderful resource worth reading."
)

LOGGING = '''
**Please enable logging:**
```import logging
logging.basicConfig(level=logging.WARNING)```

If you need more information, use `logging.DEBUG` instead.
'''

ALREADY_FIXED = (
    "This issue has already been fixed, but it's not yet available in PyPi. "
    "You can upgrade now with `pip3 install -U https://github.com/LonamiWebs"
    "/Telethon/archive/master.zip`."
)

GOOD_RESOURCES = (
    "Some good resources to learn Python:\n"
    "• [Official Docs](https://docs.python.org/3/tutorial/index.html).\n"
    "• [Dive Into Python 3](https://rawcdn.githack.com/diveintomark/"
    "diveintopython3/master/table-of-contents.html).\n"
    "• [Learn Python](https://www.learnpython.org/).\n"
    "• [Project Python](http://projectpython.net/).\n"
    "• [Computer Science Circles](https://cscircles.cemc.uwaterloo.ca/).\n"
    "• [MIT OpenCourse](https://ocw.mit.edu/courses/electrical-engineering-"
    "and-computer-science/6-0001-introduction-to-computer-science-and-progr"
    "amming-in-python-fall-2016/).\n"
    "• [Hitchhiker’s Guide to Python](https://docs.python-guide.org/).\n"
    "• The @PythonRes Telegram Channel.\n"
    "• Corey Schafer videos for [beginners](https://www.youtube.com/watch?v="
    "YYXdXT2l-Gg&list=PL-osiE80TeTskrapNbzXhwoFUiLCjGgY7) and in [general]"
    "(https://www.youtube.com/watch?v=YYXdXT2l-Gg&list=PL-osiE80TeTt2d9bfV"
    "yTiXJA-UTHn6WwU)."
)

LEARN_PYTHON = (
    "That issue is no longer related with Telethon. You should learn more "
    "Python before trying again. " + GOOD_RESOURCES
)

# ============================== Constants ==============================
# ==============================  Welcome  ==============================
last_welcome = {}


@bot.on(events.ChatAction)
async def handler(event):
    if event.user_joined:
        if event.chat_id in last_welcome:
            try:
                await last_welcome[event.chat_id].delete()
            except errors.MessageDeleteForbiddenError:
                # We believe this happens when trying to delete old messages
                pass

        last_welcome[event.chat_id] = await event.reply(WELCOME[event.chat_id])


# ==============================  Welcome  ==============================
# ==============================  Commands ==============================


@bot.on(events.NewMessage(pattern='#ping', forwards=False))
async def handler(event):
    s = time.time()
    message = await event.reply('Pong!')
    d = time.time() - s
    await message.edit(f'Pong! __(reply took {d:.2f}s)__')
    await asyncio.sleep(5)
    await asyncio.wait([event.delete(), message.delete()])


@bot.on(events.NewMessage(pattern='#full', forwards=False))
async def handler(event):
    """#full: Advises to read "Accessing the full API" in the docs."""
    await asyncio.wait([
        event.delete(),
        event.respond(READ_FULL, reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='#search (.+)', forwards=False))
async def handler(event):
    """#search query: Searches for "query" in the method reference."""
    query = urllib.parse.quote(event.pattern_match.group(1))
    await asyncio.wait([
        event.delete(),
        event.respond(SEARCH.format(query), reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='(?i)#(?:docs|ref) (.+)', forwards=False))
async def handler(event):
    """#docs or #ref query: Like #search but shows the query."""
    q1 = event.pattern_match.group(1)
    q2 = urllib.parse.quote(q1)
    await asyncio.wait([
        event.delete(),
        event.respond(DOCS.format(q1, q2), reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='#rt(f)?d', forwards=False))
async def handler(event):
    """#rtd: Tells the user to please read the docs."""
    rtd = RTFD if event.pattern_match.group(1) else RTD
    await asyncio.wait([
        event.delete(),
        event.respond(rtd, reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='#(updates|events?)', forwards=False))
async def handler(event):
    """#updates: Advices the user to read "Working with Updates"."""
    await asyncio.wait([
        event.delete(),
        event.respond(UPDATES, reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='(?i)#(ask|question)', forwards=False))
async def handler(event):
    """#ask or #question: Advices the user to ask a better question."""
    await asyncio.wait([
        event.delete(),
        event.respond(
            ASK, reply_to=event.reply_to_msg_id, link_preview=False)
    ])


@bot.on(events.NewMessage(pattern='(?i)#spam(mer|ming)?', forwards=False))
async def handler(event):
    """#spam, #spammer, #spamming: Informs spammers that they are not welcome here."""
    await asyncio.wait([
        event.delete(),
        event.respond(SPAM, reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='(?i)#(ot|offtopic)', forwards=False))
async def handler(event):
    """#ot, #offtopic: Tells the user to move to @TelethonOffTopic."""
    await asyncio.wait([
        event.delete(),
        event.respond(OFFTOPIC.get(event.chat_id, UNKNOWN_OFFTOPIC), reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='(?i)#log(s|ging)?', forwards=False))
async def handler(event):
    """#log, #logs or #logging: Explains how to enable logging."""
    await asyncio.wait([
        event.delete(),
        event.respond(LOGGING, reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='(?i)#master', forwards=False))
async def handler(event):
    """#master: The bug has been fixed in the `master` branch."""
    await asyncio.wait([
        event.delete(),
        event.respond(ALREADY_FIXED, reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='(?i)#(learn|python)', forwards=False))
async def handler(event):
    """#learn or #python: Tells the user to learn some Python first."""
    await asyncio.wait([
        event.delete(),
        event.respond(
            LEARN_PYTHON, reply_to=event.reply_to_msg_id, link_preview=False)
    ])


@bot.on(events.NewMessage(pattern='(?i)#(list|help)', forwards=False))
async def handler(event):
    await event.delete()
    text = 'Available commands:\n'
    for callback, handler in bot.list_event_handlers():
        if isinstance(handler, events.NewMessage) and callback.__doc__:
            text += f'\n{callback.__doc__.strip()}'
    text += '\n\nYou can suggest new commands [here](https://docs.google.com/'\
            'spreadsheets/d/12yWwixUu_vB426_toLBAiajXxYKvR2J1DD6yZtQz9l4/edit).'

    message = await event.respond(text, link_preview=False)
    await asyncio.sleep(1 * text.count(' '))  # Sleep ~1 second per word
    await message.delete()


if aiohttp:
    @bot.on(events.NewMessage(pattern='(?i)#([hp]aste|dog|inu)(bin)?', forwards=False))
    async def handler(event):
        """
        #haste: Replaces the message you reply to with a dogbin link.
        """
        await event.delete()
        if not event.reply_to_msg_id:
            return

        msg = await event.get_reply_message()
        if len(msg.raw_text or '') < 200:
            return

        sent = await event.respond(
            'Uploading paste…', reply_to=msg.reply_to_msg_id)

        name = html.escape(
            utils.get_display_name(await msg.get_sender()) or 'A user')

        text = msg.raw_text
        code = ''
        for _, string in msg.get_entities_text((
                types.MessageEntityCode, types.MessageEntityPre)):
            code += f'{string}\n'
            text = text.replace(string, '')

        code = code.rstrip()
        if code:
            text = re.sub(r'\s+', ' ', text)
        else:
            code = msg.raw_text
            text = ''

        async with aiohttp.ClientSession() as session:
            async with session.post('https://del.dog/documents',
                                    data=code.encode('utf-8')) as resp:
                if resp.status >= 300:
                    await sent.edit("Dogbin seems to be down… ( ^^')")
                    return

                haste = (await resp.json())['key']

        await asyncio.wait([
            msg.delete(),
            sent.edit(f'<a href="tg://user?id={msg.sender_id}">{name}</a> '
                      f'said: {text} del.dog/{haste}.py'
                      .replace('  ', ' '), parse_mode='html')
        ])


# ==============================  Commands ==============================
# ==============================   Inline  ==============================


@bot.on(events.InlineQuery)
async def handler(event):
    builder = event.builder
    result = None
    query = event.text.lower()
    if query == 'ping':
        result = builder.article('Pong!', text='This bot works inline')
    elif query == 'group':
        result = builder.article(
            'Move to the right group!',
            text='Try moving to the [right group](t.me/TelethonChat)',
            buttons=custom.Button.url('Join the group!', 't.me/TelethonChat'),
            link_preview=False
        )
    elif query in ('python', 'learn'):
        result = builder.article(
            'Resources to Learn Python',
            text=GOOD_RESOURCES,
            link_preview=False
        )

    # NOTE: You should always answer, but we want plugins to be able to answer
    #       too (and we can only answer once), so we don't always answer here.
    if result:
        await event.answer([result])


# ==============================   Inline  ==============================

bot.start(bot_token=TOKEN)

# NOTE: This example has optional "plugins", which you can get by running:
#
#           git clone https://github.com/Lonami/TelethonianBotExt plugins
#
#       Into the same folder (so you would have `assistant.py` next to
#       the now downloaded `plugins/` folder). We try importing them so
#       that the example runs fine without them, but optionally load them.
try:
    # Standalone script assistant.py with folder plugins/
    import plugins
    plugins.init(bot)
except ImportError:
    try:
        # Running as a module with `python -m assistant` and structure:
        # assistant/
        #   __main__.py (this file)
        #   plugins/    (cloned)
        from . import plugins
        plugins.init(bot)
    except ImportError:
        plugins = None

bot.run_until_disconnected()
