import base64
import os

from quart import Quart, request

from telethon import TelegramClient, utils


def get_env(name, message):
    if name in os.environ:
        return os.environ[name]
    return input(message)


# Session name, API ID and hash to use; loaded from environmental variables
SESSION = os.environ.get('TG_SESSION', 'quart')
API_ID = int(get_env('TG_API_ID', 'Enter your API ID: '))
API_HASH = get_env('TG_API_HASH', 'Enter your API hash: ')


# Helper method to add the HTML head/body
def html(inner):
    return '''
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <title>Telethon + Quart</title>
    </head>
    <body>{}</body>
</html>
'''.format(inner)


# Helper method to format messages nicely
async def format_message(message):
    if message.photo:
        content = '<img src="data:image/png;base64,{}" alt="{}" />'.format(
            base64.b64encode(await message.download_media(bytes)).decode(),
            message.raw_text
        )
    else:
        # client.parse_mode = 'html', so bold etc. will work!
        content = (message.text or '(action message)').replace('\n', '<br>')

    return '<p><strong>{}</strong>: {}<sub>{}</sub></p>'.format(
        utils.get_display_name(message.sender),
        content,
        message.date
    )


# Define the global phone and Quart app variables
phone = None
app = Quart(__name__)


# Quart handlers
@app.route('/', methods=['GET', 'POST'])
async def root():
    # Connect if we aren't yet
    if not client.is_connected():
        await client.connect()

    # We want to update the global phone variable to remember it
    global phone

    # Check form parameters (phone/code)
    form = await request.form
    if 'phone' in form:
        phone = form['phone']
        await client.send_code_request(phone)

    if 'code' in form:
        await client.sign_in(code=form['code'])

    # If we're logged in, show them some messages from their first dialog
    if await client.is_user_authorized():
        # They are logged in, show them some messages from their first dialog
        dialog = (await client.get_dialogs())[0]
        result = '<h1>{}</h1>'.format(dialog.title)
        async for m in client.iter_messages(dialog, 10):
            result += await(format_message(m))

        return html(result)

    # Ask for the phone if we don't know it yet
    if phone is None:
        return html('''
<form action="/" method="post">
    Phone (international format): <input name="phone" type="text" placeholder="+34600000000">
    <input type="submit">
</form>''')

    # We have the phone, but we're not logged in, so ask for the code
    return html('''
<form action="/" method="post">
    Telegram code: <input name="code" type="text" placeholder="70707">
    <input type="submit">
</form>''')


# By default, `Quart.run` uses `asyncio.run()`, which creates a new asyncio
# event loop. If we create the `TelegramClient` before, `telethon` will
# use `asyncio.get_event_loop()`, which is the implicit loop in the main
# thread. These two loops are different, and it won't work.
#
# So, we have to manually pass the same `loop` to both applications to
# make 100% sure it works and to avoid headaches.
#
# Quart doesn't seem to offer a way to run inside `async def`
# (see https://gitlab.com/pgjones/quart/issues/146) so we must
# run and block on it last.
#
# This example creates a global client outside of Quart handlers.
# If you create the client inside the handlers (common case), you
# won't have to worry about any of this.
client = TelegramClient(SESSION, API_ID, API_HASH)
client.parse_mode = 'html'  # <- render things nicely
app.run(loop=client.loop)  # <- same event loop as telethon
