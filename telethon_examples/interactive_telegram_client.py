import os
from getpass import getpass

from telethon import TelegramClient, ConnectionMode
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import (
    UpdateShortChatMessage, UpdateShortMessage, PeerChat
)
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


class InteractiveTelegramClient(TelegramClient):
    """Full featured Telegram client, meant to be used on an interactive
       session to see what Telethon is capable off -

       This client allows the user to perform some basic interaction with
       Telegram through Telethon, such as listing dialogs (open chats),
       talking to people, downloading media, and receiving updates.
    """
    def __init__(self, session_user_id, user_phone, api_id, api_hash,
                 proxy=None):
        """
        Initializes the InteractiveTelegramClient.
        :param session_user_id: Name of the *.session file.
        :param user_phone: The phone of the user that will login.
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

            # You can optionally change the connection mode by using this enum.
            # This changes how much data will be sent over the network with
            # every request, and how it will be formatted. Default is
            # ConnectionMode.TCP_FULL, and smallest is TCP_TCP_ABRIDGED.
            connection_mode=ConnectionMode.TCP_ABRIDGED,

            # If you're using a proxy, set it here.
            proxy=proxy,

            # If you want to receive updates, you need to start one or more
            # "update workers" which are background threads that will allow
            # you to run things when your update handlers (callbacks) are
            # called with an Update object.
            update_workers=1
        )

        # Store {message.id: message} map here so that we can download
        # media known the message ID, for every message having media.
        self.found_media = {}

        # Calling .connect() may return False, so you need to assert it's
        # True before continuing. Otherwise you may want to retry as done here.
        print('Connecting to Telegram servers...')
        if not self.connect():
            print('Initial connection failed. Retrying...')
            if not self.connect():
                print('Could not connect to Telegram servers.')
                return

        # If the user hasn't called .sign_in() or .sign_up() yet, they won't
        # be authorized. The first thing you must do is authorize. Calling
        # .sign_in() should only be done once as the information is saved on
        # the *.session file so you don't need to enter the code every time.
        if not self.is_user_authorized():
            print('First run. Sending code request...')
            self.sign_in(user_phone)

            self_user = None
            while self_user is None:
                code = input('Enter the code you just received: ')
                try:
                    self_user = self.sign_in(code=code)

                # Two-step verification may be enabled, and .sign_in will
                # raise this error. If that's the case ask for the password.
                # Note that getpass() may not work on PyCharm due to a bug,
                # if that's the case simply change it for input().
                except SessionPasswordNeededError:
                    pw = getpass('Two step verification is enabled. '
                                 'Please enter your password: ')

                    self_user = self.sign_in(password=pw)

    def run(self):
        """Main loop of the TelegramClient, will wait for user action"""

        # Once everything is ready, we can add an update handler. Every
        # update object will be passed to the self.update_handler method,
        # where we can process it as we need.
        self.add_update_handler(self.update_handler)

        # Enter a while loop to chat as long as the user wants
        while True:
            # Retrieve the top dialogs. You can set the limit to None to
            # retrieve all of them if you wish, but beware that may take
            # a long time if you have hundreds of them.
            dialog_count = 15

            # Entities represent the user, chat or channel
            # corresponding to the dialog on the same index.
            dialogs = self.get_dialogs(limit=dialog_count)

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
                i = input('Enter dialog ID or a command: ')
                if i == '!q':
                    return
                if i == '!l':
                    # Logging out will cause the user to need to reenter the
                    # code next time they want to use the library, and will
                    # also delete the *.session file off the filesystem.
                    #
                    # This is not the same as simply calling .disconnect(),
                    # which simply shuts down everything gracefully.
                    self.log_out()
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
            print('  !q: Quits the current chat.')
            print('  !Q: Quits the current chat and exits.')
            print('  !h: prints the latest messages (message History).')
            print('  !up <path>: Uploads and sends the Photo from path.')
            print('  !uf <path>: Uploads and sends the File from path.')
            print('  !d <msg-id>: Deletes a message by its id')
            print('  !dm <msg-id>: Downloads the given message Media (if any).')
            print('  !dp: Downloads the current dialog Profile picture.')
            print()

            # And start a while loop to chat
            while True:
                msg = input('Enter a message: ')
                # Quit
                if msg == '!q':
                    break
                elif msg == '!Q':
                    return

                # History
                elif msg == '!h':
                    # First retrieve the messages and some information
                    messages = self.get_message_history(entity, limit=10)

                    # Iterate over all (in reverse order so the latest appear
                    # the last in the console) and print them with format:
                    # "[hh:mm] Sender: Message"
                    for msg in reversed(messages):
                        # Note that the .sender attribute is only there for
                        # convenience, the API returns it differently. But
                        # this shouldn't concern us. See the documentation
                        # for .get_message_history() for more information.
                        name = get_display_name(msg.sender)

                        # Format the message content
                        if getattr(msg, 'media', None):
                            self.found_media[msg.id] = msg
                            # The media may or may not have a caption
                            caption = getattr(msg.media, 'caption', '')
                            content = '<{}> {}'.format(
                                type(msg.media).__name__, caption)

                        elif hasattr(msg, 'message'):
                            content = msg.message
                        elif hasattr(msg, 'action'):
                            content = str(msg.action)
                        else:
                            # Unknown message, simply print its class name
                            content = type(msg).__name__

                        # And print it to the user
                        sprint('[{}:{}] (ID={}) {}: {}'.format(
                               msg.date.hour, msg.date.minute, msg.id, name,
                               content))

                # Send photo
                elif msg.startswith('!up '):
                    # Slice the message to get the path
                    self.send_photo(path=msg[len('!up '):], entity=entity)

                # Send file (document)
                elif msg.startswith('!uf '):
                    # Slice the message to get the path
                    self.send_document(path=msg[len('!uf '):], entity=entity)

                # Delete messages
                elif msg.startswith('!d '):
                    # Slice the message to get message ID
                    deleted_msg = self.delete_messages(entity, msg[len('!d '):])
                    print('Deleted {}'.format(deleted_msg))

                # Download media
                elif msg.startswith('!dm '):
                    # Slice the message to get message ID
                    self.download_media_by_id(msg[len('!dm '):])

                # Download profile photo
                elif msg == '!dp':
                    print('Downloading profile picture to usermedia/...')
                    os.makedirs('usermedia', exist_ok=True)
                    output = self.download_profile_photo(entity, 'usermedia')
                    if output:
                        print(
                            'Profile picture downloaded to {}'.format(output)
                        )
                    else:
                        print('No profile picture found for this user!')

                # Send chat message (if any)
                elif msg:
                    self.send_message(entity, msg, link_preview=False)

    def send_photo(self, path, entity):
        """Sends the file located at path to the desired entity as a photo"""
        self.send_file(
            entity, path,
            progress_callback=self.upload_progress_callback
        )
        print('Photo sent!')

    def send_document(self, path, entity):
        """Sends the file located at path to the desired entity as a document"""
        self.send_file(
            entity, path,
            force_document=True,
            progress_callback=self.upload_progress_callback
        )
        print('Document sent!')

    def download_media_by_id(self, media_id):
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
        output = self.download_media(
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

    def update_handler(self, update):
        """Callback method for received Updates"""

        # We have full control over what we want to do with the updates.
        # In our case we only want to react to chat messages, so we use
        # isinstance() to behave accordingly on these cases.
        if isinstance(update, UpdateShortMessage):
            who = self.get_entity(update.user_id)
            if update.out:
                sprint('>> "{}" to user {}'.format(
                    update.message, get_display_name(who)
                ))
            else:
                sprint('<< {} sent "{}"'.format(
                    get_display_name(who), update.message
                ))

        elif isinstance(update, UpdateShortChatMessage):
            which = self.get_entity(PeerChat(update.chat_id))
            if update.out:
                sprint('>> sent "{}" to chat {}'.format(
                    update.message, get_display_name(which)
                ))
            else:
                who = self.get_entity(update.from_id)
                sprint('<< {} @ {} sent "{}"'.format(
                       get_display_name(which), get_display_name(who),
                       update.message
                ))
