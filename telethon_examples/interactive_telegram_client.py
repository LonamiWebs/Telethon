import asyncio
import os
import sys
import time
from getpass import getpass

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.network import ConnectionTcpAbridged
from telethon.utils import get_display_name


def sprint(string, *args, **kwargs):
    """Safe Print (handle UnicodeEncodeErrors on some terminals)"""
    try:
        print(string, *args, **kwargs)
    except UnicodeEncodeError:
        string = string.encode('utf-8', errors='ignore')\
                       .decode('ascii', errors='ignore')
        print(string, *args, **kwargs)


def print_title(title):
    """Helper function to print titles to the console more nicely"""
    sprint('\n')
    sprint('=={}=='.format('=' * len(title)))
    sprint('= {} ='.format(title))
    sprint('=={}=='.format('=' * len(title)))


def bytes_to_string(byte_count):
    """Converts a byte count to a string (in KB, MB...)"""
    suffix_index = 0
    while byte_count >= 1024:
        byte_count /= 1024
        suffix_index += 1

    return '{:.2f}{}'.format(
        byte_count, [' bytes', 'KB', 'MB', 'GB', 'TB'][suffix_index]
    )


async def async_input(prompt):
    """
    Python's ``input()`` is blocking, which means the event loop we set
    above can't be running while we're blocking there. This method will
    let the loop run while we wait for input.
    """
    print(prompt, end='', flush=True)
    return (await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)).rstrip()


def get_env(name, message, cast=str):
    """Helper to get environment variables interactively"""
    if name in os.environ:
        return os.environ[name]
    while True:
        value = input(message)
        try:
            return cast(value)
        except ValueError as e:
            print(e, file=sys.stderr)
            time.sleep(1)


class InteractiveTelegramClient(TelegramClient):
    """Full featured Telegram client, meant to be used on an interactive
       session to see what Telethon is capable off -

       This client allows the user to perform some basic interaction with
       Telegram through Telethon, such as listing dialogs (open chats),
       talking to people, downloading media, and receiving updates.
    """

    def __init__(self, session_user_id, api_id, api_hash,
                 proxy=None):
        """
        Initializes the InteractiveTelegramClient.
        :param session_user_id: Name of the *.session file.
        :param api_id: Telegram's api_id acquired through my.telegram.org.
        :param api_hash: Telegram's api_hash.
        :param proxy: Optional proxy tuple/dictionary.
        """
        print_title('Initialization')

        print('Initializing interactive example...')

        # The first step is to initialize the TelegramClient, as we are
        # subclassing it, we need to call super().__init__(). On a more
        # normal case you would want 'client = TelegramClient(...)'
        super().__init__(
            # These parameters should be passed always, session name and API
            session_user_id, api_id, api_hash,

            # You can optionally change the connection mode by passing a
            # type or an instance of it. This changes how the sent packets
            # look (low-level concept you normally shouldn't worry about).
            # Default is ConnectionTcpFull, smallest is ConnectionTcpAbridged.
            connection=ConnectionTcpAbridged,

            # If you're using a proxy, set it here.
            proxy=proxy
        )

        # Store {message.id: message} map here so that we can download
        # media known the message ID, for every message having media.
        self.found_media = {}

    async def init(self):
        # Calling .connect() may raise a connection error False, so you need
        # to except those before continuing. Otherwise you may want to retry
        # as done here.
        print('Connecting to Telegram servers...')
        try:
            await self.connect()
        except IOError:
            # We handle IOError and not ConnectionError because
            # PySocks' errors do not subclass ConnectionError
            # (so this will work with and without proxies).
            print('Initial connection failed. Retrying...')
            await self.connect()

        # If the user hasn't called .sign_in() yet, they won't
        # be authorized. The first thing you must do is authorize. Calling
        # .sign_in() should only be done once as the information is saved on
        # the *.session file so you don't need to enter the code every time.
        if not await self.is_user_authorized():
            print('First run. Sending code request...')
            user_phone = input('Enter your phone: ')
            await self.sign_in(user_phone)

            self_user = None
            while self_user is None:
                code = input('Enter the code you just received: ')
                try:
                    self_user = await self.sign_in(code=code)

                # Two-step verification may be enabled, and .sign_in will
                # raise this error. If that's the case ask for the password.
                # Note that getpass() may not work on PyCharm due to a bug,
                # if that's the case simply change it for input().
                except SessionPasswordNeededError:
                    pw = getpass('Two step verification is enabled. '
                                 'Please enter your password: ')

                    self_user = await self.sign_in(password=pw)

    async def run(self):
        """Main loop of the TelegramClient, will wait for user action"""

        # Once everything is ready, we can add an event handler.
        #
        # Events are an abstraction over Telegram's "Updates" and
        # are much easier to use.
        self.add_event_handler(self.message_handler, events.NewMessage)

        # Enter a while loop to chat as long as the user wants
        while True:
            # Retrieve the top dialogs. You can set the limit to None to
            # retrieve all of them if you wish, but beware that may take
            # a long time if you have hundreds of them.
            dialog_count = 15

            # Entities represent the user, chat or channel
            # corresponding to the dialog on the same index.
            dialogs = await self.get_dialogs(limit=dialog_count)

            i = None
            while i is None:
                print_title('Dialogs window')

                # Display them so the user can choose
                for i, dialog in enumerate(dialogs, start=1):
                    sprint('{}. {}'.format(i, get_display_name(dialog.entity)))

                # Let the user decide who they want to talk to
                print()
                print('> Who do you want to send messages to?')
                print('> Available commands:')
                print('  !q: Quits the dialogs window and exits.')
                print('  !l: Logs out, terminating this session.')
                print()
                i = await async_input('Enter dialog ID or a command: ')
                if i == '!q':
                    return
                if i == '!l':
                    # Logging out will cause the user to need to reenter the
                    # code next time they want to use the library, and will
                    # also delete the *.session file off the filesystem.
                    #
                    # This is not the same as simply calling .disconnect(),
                    # which simply shuts down everything gracefully.
                    await self.log_out()
                    return

                try:
                    i = int(i if i else 0) - 1
                    # Ensure it is inside the bounds, otherwise retry
                    if not 0 <= i < dialog_count:
                        i = None
                except ValueError:
                    i = None

            # Retrieve the selected user (or chat, or channel)
            entity = dialogs[i].entity

            # Show some information
            print_title('Chat with "{}"'.format(get_display_name(entity)))
            print('Available commands:')
            print('  !q:  Quits the current chat.')
            print('  !Q:  Quits the current chat and exits.')
            print('  !h:  prints the latest messages (message History).')
            print('  !up  <path>: Uploads and sends the Photo from path.')
            print('  !uf  <path>: Uploads and sends the File from path.')
            print('  !d   <msg-id>: Deletes a message by its id')
            print('  !dm  <msg-id>: Downloads the given message Media (if any).')
            print('  !dp: Downloads the current dialog Profile picture.')
            print('  !i:  Prints information about this chat..')
            print()

            # And start a while loop to chat
            while True:
                msg = await async_input('Enter a message: ')
                # Quit
                if msg == '!q':
                    break
                elif msg == '!Q':
                    return

                # History
                elif msg == '!h':
                    # First retrieve the messages and some information
                    messages = await self.get_messages(entity, limit=10)

                    # Iterate over all (in reverse order so the latest appear
                    # the last in the console) and print them with format:
                    # "[hh:mm] Sender: Message"
                    for msg in reversed(messages):
                        # Note how we access .sender here. Since we made an
                        # API call using the self client, it will always have
                        # information about the sender. This is different to
                        # events, where Telegram may not always send the user.
                        name = get_display_name(msg.sender)

                        # Format the message content
                        if getattr(msg, 'media', None):
                            self.found_media[msg.id] = msg
                            content = '<{}> {}'.format(
                                type(msg.media).__name__, msg.message)

                        elif hasattr(msg, 'message'):
                            content = msg.message
                        elif hasattr(msg, 'action'):
                            content = str(msg.action)
                        else:
                            # Unknown message, simply print its class name
                            content = type(msg).__name__

                        # And print it to the user
                        sprint('[{}:{}] (ID={}) {}: {}'.format(
                            msg.date.hour, msg.date.minute, msg.id, name, content))

                # Send photo
                elif msg.startswith('!up '):
                    # Slice the message to get the path
                    path = msg[len('!up '):]
                    await self.send_photo(path=path, entity=entity)

                # Send file (document)
                elif msg.startswith('!uf '):
                    # Slice the message to get the path
                    path = msg[len('!uf '):]
                    await self.send_document(path=path, entity=entity)

                # Delete messages
                elif msg.startswith('!d '):
                    # Slice the message to get message ID
                    msg = msg[len('!d '):]
                    deleted_msg = await self.delete_messages(entity, msg)
                    print('Deleted {}'.format(deleted_msg))

                # Download media
                elif msg.startswith('!dm '):
                    # Slice the message to get message ID
                    await self.download_media_by_id(msg[len('!dm '):])

                # Download profile photo
                elif msg == '!dp':
                    print('Downloading profile picture to usermedia/...')
                    os.makedirs('usermedia', exist_ok=True)
                    output = await self.download_profile_photo(entity,
                                                               'usermedia')
                    if output:
                        print('Profile picture downloaded to', output)
                    else:
                        print('No profile picture found for this user!')

                elif msg == '!i':
                    attributes = list(entity.to_dict().items())
                    pad = max(len(x) for x, _ in attributes)
                    for name, val in attributes:
                        print("{:<{width}} : {}".format(name, val, width=pad))

                # Send chat message (if any)
                elif msg:
                    await self.send_message(entity, msg, link_preview=False)

    async def send_photo(self, path, entity):
        """Sends the file located at path to the desired entity as a photo"""
        await self.send_file(
            entity, path,
            progress_callback=self.upload_progress_callback
        )
        print('Photo sent!')

    async def send_document(self, path, entity):
        """Sends the file located at path to the desired entity as a document"""
        await self.send_file(
            entity, path,
            force_document=True,
            progress_callback=self.upload_progress_callback
        )
        print('Document sent!')

    async def download_media_by_id(self, media_id):
        """Given a message ID, finds the media this message contained and
           downloads it.
        """
        try:
            msg = self.found_media[int(media_id)]
        except (ValueError, KeyError):
            # ValueError when parsing, KeyError when accessing dictionary
            print('Invalid media ID given or message not found!')
            return

        print('Downloading media to usermedia/...')
        os.makedirs('usermedia', exist_ok=True)
        output = await self.download_media(
            msg.media,
            file='usermedia/',
            progress_callback=self.download_progress_callback
        )
        print('Media downloaded to {}!'.format(output))

    @staticmethod
    def download_progress_callback(downloaded_bytes, total_bytes):
        InteractiveTelegramClient.print_progress(
            'Downloaded', downloaded_bytes, total_bytes
        )

    @staticmethod
    def upload_progress_callback(uploaded_bytes, total_bytes):
        InteractiveTelegramClient.print_progress(
            'Uploaded', uploaded_bytes, total_bytes
        )

    @staticmethod
    def print_progress(progress_type, downloaded_bytes, total_bytes):
        print('{} {} out of {} ({:.2%})'.format(
            progress_type, bytes_to_string(downloaded_bytes),
            bytes_to_string(total_bytes), downloaded_bytes / total_bytes)
        )

    async def message_handler(self, event):
        """Callback method for received events.NewMessage"""

        # Note that message_handler is called when a Telegram update occurs
        # and an event is created. Telegram may not always send information
        # about the ``.sender`` or the ``.chat``, so if you *really* want it
        # you should use ``get_chat()`` and ``get_sender()`` while working
        # with events. Since they are methods, you know they may make an API
        # call, which can be expensive.
        chat = await event.get_chat()
        if event.is_group:
            if event.out:
                sprint('>> sent "{}" to chat {}'.format(
                    event.text, get_display_name(chat)
                ))
            else:
                sprint('<< {} @ {} sent "{}"'.format(
                    get_display_name(await event.get_sender()),
                    get_display_name(chat),
                    event.text
                ))
        else:
            if event.out:
                sprint('>> "{}" to user {}'.format(
                    event.text, get_display_name(chat)
                ))
            else:
                sprint('<< {} sent "{}"'.format(
                    get_display_name(chat), event.text
                ))


async def main():
    SESSION = os.environ.get('TG_SESSION', 'interactive')
    API_ID = get_env('TG_API_ID', 'Enter your API ID: ', int)
    API_HASH = get_env('TG_API_HASH', 'Enter your API hash: ')
    client = InteractiveTelegramClient(SESSION, API_ID, API_HASH)
    await client.init()
    await client.run()


if __name__ == '__main__':
    asyncio.run()
