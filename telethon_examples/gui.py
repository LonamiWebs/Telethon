import asyncio
import functools
import inspect
import os
import sys
import tkinter
import tkinter.constants
import tkinter.scrolledtext
import tkinter.ttk

from telethon import TelegramClient, events, utils

# Some configuration for the app
TITLE = 'Telethon GUI'
SIZE = '640x280'

# Session name, API ID and hash to use; loaded from environmental variables
SESSION = os.environ.get('TG_SESSION', 'gui')

API_ID = os.environ.get('TG_API_ID')
if not API_ID:
    API_ID = input('Enter API ID (or add TG_API_ID to env vars): ')

API_HASH = os.environ.get('TG_API_HASH')
if not API_HASH:
    API_HASH = input('Enter API hash (or add TG_API_HASH to env vars): ')


def callback(func):
    """
    This decorator turns `func` into a callback for Tkinter
    to be able to use, even if `func` is an awaitable coroutine.
    """
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        result = func(*args, **kwargs)
        if inspect.iscoroutine(result):
            asyncio.create_task(result)

    return wrapped


def allow_copy(widget):
    """
    This helper makes `widget` readonly but allows copying with ``Ctrl+C``.
    """
    widget.bind('<Control-c>', lambda e: None)
    widget.bind('<Key>', lambda e: "break")


class App(tkinter.Tk):
    """
    Our main GUI application; we subclass `tkinter.Tk`
    so the `self` instance can be the root widget.

    One must be careful when assigning members or
    defining methods since those may interfer with
    the root widget.

    You may prefer to have ``App.root = tkinter.Tk()``
    and create widgets with ``self.root`` as parent.
    """
    def __init__(self, client, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cl = client
        self.title(TITLE)
        self.geometry(SIZE)

        # Signing in row; the entry supports phone and bot token
        self.sign_in_label = tkinter.Label(self, text='Loading...')
        self.sign_in_label.grid(row=0, column=0)
        self.sign_in_entry = tkinter.Entry(self)
        self.sign_in_entry.grid(row=0, column=1, sticky=tkinter.EW)
        self.sign_in_entry.bind('<Return>', self.sign_in)
        self.sign_in_button = tkinter.Button(self, text='...',
                                             command=self.sign_in)
        self.sign_in_button.grid(row=0, column=2)
        self.code = None

        # The chat where to send and show messages from
        tkinter.Label(self, text='Target chat:').grid(row=1, column=0)
        self.chat = tkinter.Entry(self)
        self.chat.grid(row=1, column=1, columnspan=2, sticky=tkinter.EW)
        self.columnconfigure(1, weight=1)
        self.chat.bind('<Return>', self.check_chat)
        self.chat.bind('<FocusOut>', self.check_chat)
        self.chat.focus()
        self.chat_id = None

        # Message log (incoming and outgoing); we configure it as readonly
        self.log = tkinter.scrolledtext.ScrolledText(self)
        allow_copy(self.log)
        self.log.grid(row=2, column=0, columnspan=3, sticky=tkinter.NSEW)
        self.rowconfigure(2, weight=1)
        self.cl.add_event_handler(self.on_message, events.NewMessage)

        # Sending messages
        tkinter.Label(self, text='Message:').grid(row=3, column=0)
        self.message = tkinter.Entry(self)
        self.message.grid(row=3, column=1, sticky=tkinter.EW)
        self.message.bind('<Return>', self.send_message)
        tkinter.Button(self, text='Send',
                       command=self.send_message).grid(row=3, column=2)

        # Post-init (async, connect client)
        self.cl.loop.create_task(self.post_init())

    async def post_init(self):
        """
        Completes the initialization of our application.
        Since `__init__` cannot be `async` we use this.
        """
        if await self.cl.is_user_authorized():
            self.set_signed_in(await self.cl.get_me())
        else:
            # User is not logged in, configure the button to ask them to login
            self.sign_in_button.configure(text='Sign in')
            self.sign_in_label.configure(
                text='Sign in (phone/token):')

    async def on_message(self, event):
        """
        Event handler that will add new messages to the message log.
        """
        # We want to show only messages sent to this chat
        if event.chat_id != self.chat_id:
            return

        # Decide a prefix (">> " for our messages, "<user>" otherwise)
        if event.out:
            text = '>> '
        else:
            sender = await event.get_sender()
            text = '<{}> '.format(utils.get_display_name(sender))

        # If the message has media show "(MediaType) "
        if event.media:
            text += '({}) '.format(event.media.__class__.__name__)

        text += event.text
        text += '\n'

        # Append the text to the end with a newline, and scroll to the end
        self.log.insert(tkinter.INSERT, text)
        self.log.yview(tkinter.END)

    # noinspection PyUnusedLocal
    @callback
    async def sign_in(self, event=None):
        """
        Note the `event` argument. This is required since this callback
        may be called from a ``widget.bind`` (such as ``'<Return>'``),
        which sends information about the event we don't care about.

        This callback logs out if authorized, signs in if a code was
        sent or a bot token is input, or sends the code otherwise.
        """
        self.sign_in_label.configure(text='Working...')
        self.sign_in_entry.configure(state=tkinter.DISABLED)
        if await self.cl.is_user_authorized():
            await self.cl.log_out()
            self.destroy()
            return

        value = self.sign_in_entry.get().strip()
        if self.code:
            self.set_signed_in(await self.cl.sign_in(code=value))
        elif ':' in value:
            self.set_signed_in(await self.cl.sign_in(bot_token=value))
        else:
            self.code = await self.cl.send_code_request(value)
            self.sign_in_label.configure(text='Code:')
            self.sign_in_entry.configure(state=tkinter.NORMAL)
            self.sign_in_entry.delete(0, tkinter.END)
            self.sign_in_entry.focus()
            return

    def set_signed_in(self, me):
        """
        Configures the application as "signed in" (displays user's
        name and disables the entry to input phone/bot token/code).
        """
        self.sign_in_label.configure(text='Signed in')
        self.sign_in_entry.configure(state=tkinter.NORMAL)
        self.sign_in_entry.delete(0, tkinter.END)
        self.sign_in_entry.insert(tkinter.INSERT, utils.get_display_name(me))
        self.sign_in_entry.configure(state=tkinter.DISABLED)
        self.sign_in_button.configure(text='Log out')
        self.chat.focus()

    # noinspection PyUnusedLocal
    @callback
    async def send_message(self, event=None):
        """
        Sends a message. Does nothing if the client is not connected.
        """
        if not self.cl.is_connected():
            return

        # The user needs to configure a chat where the message should be sent.
        #
        # If the chat ID does not exist, it was not valid and the user must
        # configure one; hint them by changing the background to red.
        if not self.chat_id:
            self.chat.configure(bg='red')
            self.chat.focus()
            return

        # Get the message, clear the text field and focus it again
        text = self.message.get()
        self.message.delete(0, tkinter.END)
        self.message.focus()

        # Send the message text and get back the sent message object
        message = await self.cl.send_message(self.chat_id, text)

        # Process the sent message as if it were an event
        await self.on_message(message)

    # noinspection PyUnusedLocal
    @callback
    async def check_chat(self, event=None):
        """
        Checks the input chat where to send and listen messages from.
        """
        chat = self.chat.get().strip()
        if chat.isdigit():
            chat = int(chat)

        try:
            # Valid chat ID, set it and configure the colour back to white
            self.chat_id = await self.cl.get_peer_id(chat)
            self.chat.configure(bg='white')
        except ValueError:
            # Invalid chat ID, let the user know with a yellow background
            self.chat_id = None
            self.chat.configure(bg='yellow')


async def main(loop, interval=0.05):
    client = TelegramClient(SESSION, API_ID, API_HASH, loop=loop)
    try:
        await client.connect()
    except Exception as e:
        print('Failed to connect', e, file=sys.stderr)
        return

    app = App(client)
    try:
        while True:
            # We want to update the application but get back
            # to asyncio's event loop. For this we sleep a
            # short time so the event loop can run.
            #
            # https://www.reddit.com/r/Python/comments/33ecpl
            app.update()
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        pass
    except tkinter.TclError as e:
        if 'application has been destroyed' not in e.args[0]:
            raise
    finally:
        await app.cl.disconnect()


if __name__ == "__main__":
    # Some boilerplate code to set up the main method
    aio_loop = asyncio.get_event_loop()
    try:
        aio_loop.run_until_complete(main(aio_loop))
    finally:
        if not aio_loop.is_closed():
            aio_loop.close()
