import asyncio
import difflib
import logging
import os
import sys
import time
import urllib.parse

from telethon import TelegramClient, events, custom

logging.basicConfig(level=logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.ERROR)


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
    'read [the docs](https://telethon.readthedocs.io/). Make sure you are '
    'using the latest version with `pip3 install -U telethon`, since most '
    'problems have already been fixed in newer versions.',

-1001200633650:
    'Welcome to the off-topic group. Feel free to talk, ask or test anything '
    'here, politely. Check the description if you need to test more spammy '
    '"features" of your or other people\'s bots (sed commands too).'
}

READ_FULL = (
    'Please read [Accessing the Full API](https://telethon.readthedocs.io'
    '/en/latest/extra/advanced-usage/accessing-the-full-api.html)'
)

SEARCH = (
    'Remember [search is your friend]'
    '(https://lonamiwebs.github.io/Telethon/?q={})'
)

DOCS = 'TL Reference for [{}](https://lonamiwebs.github.io/Telethon/?q={})'
RTD = '[Read The Docs!](https://telethon.readthedocs.io)'
RTFD = '[Read The F* Docs!](https://telethon.readthedocs.io)'
DOCS_CLIENT = 'https://telethon.readthedocs.io/en/latest/telethon.client.html#'
DOCS_MESSAGE = (
    'https://telethon.readthedocs.io/en/latest/'
    'telethon.tl.custom.html#telethon.tl.custom.message.Message.'
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
    "You can upgrade now with `pip install --upgrade git+https://github.com"
    "/LonamiWebs/Telethon@master`."
)

LEARN_PYTHON = (
    "That issue is no longer related with Telethon. You should learn more "
    "Python before trying again. Some good resources:\n"
    "• [Official Docs](https://docs.python.org/3/tutorial/index.html).\n"
    "• [Dive Into Python 3](http://www.diveintopython3.net/).\n"
    "• [Learn Python](https://www.learnpython.org/).\n"
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

# ============================== Constants ==============================
# ==============================  Welcome  ==============================
last_welcome = {}


@bot.on(events.ChatAction)
async def handler(event):
    if event.user_joined:
        if event.chat_id in last_welcome:
            await last_welcome[event.chat_id].delete()

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


@bot.on(events.NewMessage(pattern='(?i)#(client|msg) (.+)', forwards=False))
async def handler(event):
    """#client or #msg query: Looks for the given attribute in RTD."""
    await event.delete()
    query = event.pattern_match.group(2).lower()
    cls = ({'client': TelegramClient, 'msg': custom.Message}
           [event.pattern_match.group(1)])

    attr = search_attr(cls, query)
    if not attr:
        await event.respond(f'No such method "{query}" :/')
        return

    name = attr
    if event.pattern_match.group(1) == 'client':
        attr = attr_fullname(cls, attr)
        url = DOCS_CLIENT
    elif event.pattern_match.group(1) == 'msg':
        name = f'Message.{name}'
        url = DOCS_MESSAGE
    else:
        return

    await event.respond(
        f'Documentation for [{name}]({url}{attr})',
        reply_to=event.reply_to_msg_id
    )


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
        event.respond(OFFTOPIC[event.chat_id], reply_to=event.reply_to_msg_id)
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
            text += f'\n{callback.__doc__}'
    text += '\n\nYou can suggest new commands [here](https://docs.google.com/'\
            'spreadsheets/d/12yWwixUu_vB426_toLBAiajXxYKvR2J1DD6yZtQz9l4/edit).'

    message = await event.respond(text, link_preview=False)
    await asyncio.sleep(1 * text.count(' '))  # Sleep ~1 second per word
    await message.delete()


# ==============================  Commands ==============================
# ============================== AutoReply ==============================


@bot.on(events.NewMessage(pattern='(?i)how (.+?)[\W]*$', forwards=False))
@bot.on(events.NewMessage(pattern='(.+?)[\W]*?\?+', forwards=False))
async def handler(event):
    words = event.pattern_match.group(1).split()
    rates = [
        search_attr(TelegramClient, ' '.join(words[-i:]), threshold=None)
        for i in range(1, 4)
    ]
    what = max(rates, key=lambda t: t[1])
    if what[1] < 0.7:
        return

    name = what[0]
    if len(name) < 4:
        return  # Short words trigger very commonly (such as "on")

    attr = attr_fullname(TelegramClient, name)
    await event.reply(
        f'Documentation for [{name}]({DOCS_CLIENT}{attr})',
        reply_to=event.reply_to_msg_id
    )

    # We have two @client.on, both could fire, stop that
    raise events.StopPropagation


# ============================== AutoReply ==============================
# ==============================  Helpers  ==============================


def search_attr(cls, query, threshold=0.6):
    seq = difflib.SequenceMatcher(b=query, autojunk=False)
    scores = []
    for n in dir(cls):
        if not n.startswith('_'):
            seq.set_seq1(n)
            scores.append((n, seq.ratio()))

    scores.sort(key=lambda t: t[1], reverse=True)
    if threshold is None:
        return scores[0]
    else:
        return scores[0][0] if scores[0][1] >= threshold else None


def attr_fullname(cls, n):
    m = getattr(cls, n)
    cls = sys.modules.get(m.__module__)
    for name in m.__qualname__.split('.')[:-1]:
        cls = getattr(cls, name)
    return cls.__module__ + '.' + cls.__name__ + '.' + m.__name__


# ==============================  Helpers  ==============================


bot.start(bot_token=TOKEN)
bot.run_until_disconnected()
