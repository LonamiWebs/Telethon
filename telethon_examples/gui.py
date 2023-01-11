import asyncio
import collections
import functools
import inspect
import os
import re
import sys
import time
import tkinter
import tkinter.constants
import tkinter.scrolledtext
import tkinter.ttk

from telethon import TelegramClient, events, utils

# Some configuration for the app
TITLE = 'Telethon GUI'
SIZE = '640x280'
REPLY = re.compile(r'\.r\s*(\d+)\s*(.+)', re.IGNORECASE)
DELETE = re.compile(r'\.d\s*(\d+)', re.IGNORECASE)
EDIT = re.compile(r'\.s(.+?[^\\])/(.*)', re.IGNORECASE)


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


# Session name, API ID and hash to use; loaded from environmental variables
SESSION = os.environ.get('TG_SESSION', 'gui')
API_ID = get_env('TG_API_ID', 'Enter your API ID: ', int)
API_HASH = get_env('TG_API_HASH', 'Enter your API hash: ')


def sanitize_str(string):
    return ''.join(x if ord(x) <= 0xffff else
                   '{{{:x}ū}}'.format(ord(x)) for x in string)


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
        self.me = None

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

        # Save shown message IDs to support replying with ".rN reply"
        # For instance to reply to the last message ".r1 this is a reply"
        # Deletion also works with ".dN".
        self.message_ids = []

        # Save the sent texts to allow editing with ".s text/replacement"
        # For instance to edit the last "hello" with "bye" ".s hello/bye"
        self.sent_text = collections.deque(maxlen=10)

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

        # Save the message ID so we know which to reply to
        self.message_ids.append(event.id)

        # Decide a prefix (">> " for our messages, "<user>" otherwise)
        if event.out:
            text = '>> '
        else:
            sender = await event.get_sender()
            text = '<{}> '.format(sanitize_str(
                utils.get_display_name(sender)))

        # If the message has media show "(MediaType) "
        if event.media:
            text += '({}) '.format(event.media.__class__.__name__)

        text += sanitize_str(event.text)
        text += '\n'

        # Append the text to the end with a newline, and scroll to the end
        self.log.insert(tkinter.END, text)
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
        self.me = me
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
        text = self.message.get().strip()
        self.message.delete(0, tkinter.END)
        self.message.focus()
        if not text:
            return

        # NOTE: This part is optional but supports editing messages
        #       You can remove it if you find it too complicated.
        #
        # Check if the edit matches any text
        m = EDIT.match(text)
        if m:
            find = re.compile(m.group(1).lstrip())
            # Cannot reversed(enumerate(...)), use index
            for i in reversed(range(len(self.sent_text))):
                msg_id, msg_text = self.sent_text[i]
                if find.search(msg_text):
                    # Found text to replace, so replace it and edit
                    new = find.sub(m.group(2), msg_text)
                    self.sent_text[i] = (msg_id, new)
                    await self.cl.edit_message(self.chat_id, msg_id, new)

                    # Notify that a replacement was made
                    self.log.insert(tkinter.END, '(message edited: {} -> {})\n'
                                    .format(msg_text, new))
                    self.log.yview(tkinter.END)
                    return

        # Check if we want to delete the message
        m = DELETE.match(text)
        if m:
            try:
                delete = self.message_ids.pop(-int(m.group(1)))
            except IndexError:
                pass
            else:
                await self.cl.delete_messages(self.chat_id, delete)
                # Notify that a message was deleted
                self.log.insert(tkinter.END, '(message deleted)\n')
                self.log.yview(tkinter.END)
                return

        # Check if we want to reply to some message
        reply_to = None
        m = REPLY.match(text)
        if m:
            text = m.group(2)
            try:
                reply_to = self.message_ids[-int(m.group(1))]
            except IndexError:
                pass

        # NOTE: This part is no longer optional. It sends the message.
        # Send the message text and get back the sent message object
        message = await self.cl.send_message(self.chat_id, text,
                                             reply_to=reply_to)

        # Save the sent message ID and text to allow edits
        self.sent_text.append((message.id, text))

        # Process the sent message as if it were an event
        await self.on_message(message)

    # noinspection PyUnusedLocal
    @callback
    async def check_chat(self, event=None):
        """
        Checks the input chat where to send and listen messages from.
        """
        if self.me is None:
            return  # Not logged in yet

        chat = self.chat.get().strip()
        try:
            chat = int(chat)
        except ValueError:
            pass

        try:
            old = self.chat_id
            # Valid chat ID, set it and configure the colour back to white
            self.chat_id = await self.cl.get_peer_id(chat)
            self.chat.configure(bg='white')

            # If the chat ID changed, clear the
            # messages that we could edit or reply
            if self.chat_id != old:
                self.message_ids.clear()
                self.sent_text.clear()
                self.log.delete('1.0', tkinter.END)
                if not self.me.bot:
                    for msg in reversed(
                            await self.cl.get_messages(self.chat_id, 100)):
                        await self.on_message(msg)
        except ValueError:
            # Invalid chat ID, let the user know with a yellow background
            self.chat_id = None
            self.chat.configure(bg='yellow')


async def main(interval=0.05):
    client = TelegramClient(SESSION, API_ID, API_HASH)
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
    asyncio.run(main())
