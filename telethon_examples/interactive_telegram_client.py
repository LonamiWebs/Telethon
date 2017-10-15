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
    # Clear previous window
    print('\n')
    print('=={}=='.format('=' * len(title)))
    sprint('= {} ='.format(title))
    print('=={}=='.format('=' * len(title)))


def bytes_to_string(byte_count):
    """Converts a byte count to a string (in KB, MB...)"""
    suffix_index = 0
    while byte_count >= 1024:
        byte_count /= 1024
        suffix_index += 1

    return '{:.2f}{}'.format(byte_count,
                             [' bytes', 'KB', 'MB', 'GB', 'TB'][suffix_index])


class InteractiveTelegramClient(TelegramClient):
    """Full featured Telegram client, meant to be used on an interactive
       session to see what Telethon is capable off -

       This client allows the user to perform some basic interaction with
       Telegram through Telethon, such as listing dialogs (open chats),
       talking to people, downloading media, and receiving updates.
    """
    def __init__(self, session_user_id, user_phone, api_id, api_hash,
                 proxy=None):
        print_title('Initialization')

        print('Initializing interactive example...')
        super().__init__(
            session_user_id, api_id, api_hash,
            connection_mode=ConnectionMode.TCP_ABRIDGED,
            proxy=proxy,
            update_workers=1
        )

        # Store all the found media in memory here,
        # so it can be downloaded if the user wants
        self.found_media = set()

        print('Connecting to Telegram servers...')
        if not self.connect():
            print('Initial connection failed. Retrying...')
            if not self.connect():
                print('Could not connect to Telegram servers.')
                return

        # Then, ensure we're authorized and have access
        if not self.is_user_authorized():
            print('First run. Sending code request...')
            self.send_code_request(user_phone)

            self_user = None
            while self_user is None:
                code = input('Enter the code you just received: ')
                try:
                    self_user = self.sign_in(user_phone, code)

                # Two-step verification may be enabled
                except SessionPasswordNeededError:
                    pw = getpass('Two step verification is enabled. '
                                 'Please enter your password: ')

                    self_user = self.sign_in(password=pw)

    def run(self):
        # Listen for updates
        self.add_update_handler(self.update_handler)

        # Enter a while loop to chat as long as the user wants
        while True:
            # Retrieve the top dialogs
            dialog_count = 15

            # Entities represent the user, chat or channel
            # corresponding to the dialog on the same index
            dialogs, entities = self.get_dialogs(limit=dialog_count)

            i = None
            while i is None:
                print_title('Dialogs window')

                # Display them so the user can choose
                for i, entity in enumerate(entities, start=1):
                    sprint('{}. {}'.format(i, get_display_name(entity)))

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
            entity = entities[i]

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
                    try:
                        total_count, messages, senders = self.get_message_history(
                        entity, limit=10)
                    except:
                        continue

                    # Iterate over all (in reverse order so the latest appear
                    # the last in the console) and print them with format:
                    # "[hh:mm] Sender: Message"
                    for msg, sender in zip(
                            reversed(messages), reversed(senders)):
                        # Get the name of the sender if any
                        if sender:
                            name = getattr(sender, 'first_name', None)
                            if not name:
                                name = getattr(sender, 'title')
                                if not name:
                                    name = '???'
                        else:
                            name = '???'

                        # Format the message content
                        if getattr(msg, 'media', None):
                            self.found_media.add(msg)
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
                    print('Deleted. {}'.format(deleted_msg))


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
                        print('No profile picture found for this user.')

                # Send chat message (if any)
                elif msg:
                    self.send_message(
                        entity, msg, link_preview=False)

    def send_photo(self, path, entity):
        self.send_file(
            entity, path,
            progress_callback=self.upload_progress_callback
        )
        print('Photo sent!')

    def send_document(self, path, entity):
        self.send_file(
            entity, path,
            force_document=True,
            progress_callback=self.upload_progress_callback
        )
        print('Document sent!')

    def download_media_by_id(self, media_id):
        try:
            # The user may have entered a non-integer string!
            msg_media_id = int(media_id)

            # Search the message ID
            for msg in self.found_media:
                if msg.id == msg_media_id:
                    print('Downloading media to usermedia/...')
                    os.makedirs('usermedia', exist_ok=True)
                    output = self.download_media(
                        msg.media,
                        file='usermedia/',
                        progress_callback=self.download_progress_callback
                    )
                    print('Media downloaded to {}!'.format(output))

        except ValueError:
            print('Invalid media ID given!')

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
        if isinstance(update, UpdateShortMessage):
            who = self.get_entity(update.user_id)
            if update.out:
                sprint('>> "{}" to user {}'.format(
                    update.message, get_display_name(who)
                ))
            else:
                sprint('<< {} sent "{}"]'.format(
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
