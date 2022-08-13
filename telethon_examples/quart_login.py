import base64
import os

import hypercorn.asyncio
from quart import Quart, render_template_string, request

from telethon import TelegramClient, utils
from telethon.types import Message
from telethon.errors import SessionPasswordNeededError


def get_env(name, message):
    if name in os.environ:
        return os.environ[name]
    return input(message)


BASE_TEMPLATE = '''
<!DOCTYPE html>
<html>
    <head>
        <meta charset='UTF-8'>
        <title>Telethon + Quart</title>
    </head>
    <body>{{ content | safe }}</body>
</html>
'''

PHONE_FORM = '''
<form action='/' method='post'>
    Phone (international format): <input name='phone' type='text' placeholder='+34600000000'>
    <input type='submit'>
</form>
'''

CODE_FORM = '''
<form action='/' method='post'>
    Telegram code: <input name='code' type='text' placeholder='70707'>
    <input type='submit'>
</form>
'''

PASSWORD_FORM = '''
<form action='/' method='post'>
    Telegram password: <input name='password' type='text' placeholder='your password'>
    <input type='submit'>
</form>
'''

# Session name, API ID and hash to use; loaded from environmental variables
SESSION = os.environ.get('TG_SESSION', 'quart')
API_ID = int(get_env('TG_API_ID', 'Enter your API ID: '))
API_HASH = get_env('TG_API_HASH', 'Enter your API hash: ')

# Render things nicely (global setting)
Message.set_default_parse_mode('html')

# Telethon client
client = TelegramClient(SESSION, API_ID, API_HASH)
phone = None

# Quart app
app = Quart(__name__)
app.secret_key = 'CHANGE THIS TO SOMETHING SECRET'


# Helper method to format messages nicely
async def format_message(message):
    if message.photo:
        content = '<img src="data:image/png;base64,{}" alt="{}" />'.format(
            base64.b64encode(await message.download_media(bytes)).decode(),
            message.raw_text
        )
    else:
        # The Message parse_mode is 'html', so bold etc. will work!
        content = (message.text or '(action message)').replace('\n', '<br>')

    return '<p><strong>{}</strong>: {}<sub>{}</sub></p>'.format(
        utils.get_display_name(message.sender),
        content,
        message.date
    )


# Connect the client before we start serving with Quart
@app.before_serving
async def startup():
    await client.connect()


# After we're done serving (near shutdown), clean up the client
@app.after_serving
async def cleanup():
    await client.disconnect()


@app.route('/', methods=['GET', 'POST'])
async def root():
    # We want to update the global phone variable to remember it
    global phone

    # Check form parameters (phone/code)
    form = await request.form
    if 'phone' in form:
        phone = form['phone']
        await client.send_code_request(phone)

    if 'code' in form:
        try:
            await client.sign_in(code=form['code'])
        except SessionPasswordNeededError:
            return await render_template_string(BASE_TEMPLATE, content=PASSWORD_FORM)

    if 'password' in form:
        await client.sign_in(password=form['password'])

    # If we're logged in, show them some messages from their first dialog
    if await client.is_user_authorized():
        # They are logged in, show them some messages from their first dialog
        dialog = (await client.get_dialogs())[0]
        result = '<h1>{}</h1>'.format(dialog.title)
        async for m in client.get_messages(dialog, 10):
            result += await(format_message(m))

        return await render_template_string(BASE_TEMPLATE, content=result)

    # Ask for the phone if we don't know it yet
    if phone is None:
        return await render_template_string(BASE_TEMPLATE, content=PHONE_FORM)

    # We have the phone, but we're not logged in, so ask for the code
    return await render_template_string(BASE_TEMPLATE, content=CODE_FORM)


async def main():
    await hypercorn.asyncio.serve(app, hypercorn.Config())


# By default, `Quart.run` uses `asyncio.run()`, which creates a new asyncio
# event loop. Instead, we use `asyncio.run()` manually in order to make this
# explicit, as the client cannot be "transferred" between loops while
# connected due to the need to schedule work within an event loop.
#
# In essence one needs to be careful to avoid mixing event loops, but this is
# simple, as `asyncio.run` is generally only used in the entry-point of the
# program.
#
# To run Quart inside `async def`, we must use `hypercorn.asyncio.serve()`
# directly.
#
# This example creates a global client outside of Quart handlers.
# If you create the client inside the handlers (common case), you
# won't have to worry about any of this, but it's still good to be
# explicit about the event loop.
if __name__ == '__main__':
    asyncio.run(main())
