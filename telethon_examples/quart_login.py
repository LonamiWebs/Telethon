import base64
import os

from quart import Quart, render_template_string, request, session

from telethon import TelegramClient, utils

BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <title>Telethon + Quart</title>
    </head>
    <body>{{ content | safe }}</body>
</html>
"""

PHONE_FORM = """
<form action="/" method="post">
    Phone (international format): <input name="phone" type="text" placeholder="+34600000000">
    <input type="submit">
</form>
"""

CODE_FORM = """
<form action="/" method="post">
    Telegram code: <input name="code" type="text" placeholder="70707">
    <input type="submit">
</form>
"""

app = Quart(__name__)
app.secret_key = "CHANGE THIS TO SOMETHING SECRET"


def get_env(name, message):
    if name in os.environ:
        return os.environ[name]
    return input(message)


# Session name, API ID and hash to use; loaded from environmental variables
SESSION = os.environ.get('TG_SESSION', 'quart')
API_ID = int(get_env('TG_API_ID', 'Enter your API ID: '))
API_HASH = get_env('TG_API_HASH', 'Enter your API hash: ')


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


@app.route('/', methods=['GET', 'POST'])
async def root():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    if request.method == "POST":
        form = await request.form
        if 'phone' in form:
            session["phone"] = form["phone"]
            await client.send_code_request(form["phone"])

        if 'code' in form:
            session["code"] = form["code"]

    if "phone" not in session:
        return await render_template_string(BASE_TEMPLATE, content=PHONE_FORM)

    if "code" not in session:
        return await render_template_string(BASE_TEMPLATE, content=CODE_FORM)

    await client.sign_in(code=session["code"])
    # They are logged in, show them some messages from their first dialog
    dialog = (await client.get_dialogs())[0]
    result = '<h1>{}</h1>'.format(dialog.title)
    async for m in client.iter_messages(dialog, 10):
        result += await(format_message(m))

    await client.disconnect()
    return await render_template_string(BASE_TEMPLATE, content=result)


if __name__ == "__main__":
    app.run()
