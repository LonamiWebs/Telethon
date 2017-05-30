import shutil
from getpass import getpass

from . import TelegramClient
from .errors import RPCError
from .tl.types import UpdateShortChatMessage, UpdateShortMessage
from .utils import get_display_name

# Get the (current) number of lines in the terminal
cols, rows = shutil.get_terminal_size()


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
    def __init__(self, session_user_id, user_phone, api_id, api_hash, proxy=None):
        print_title('Initialization')

        print('Initializing interactive example...')
        super().__init__(session_user_id, api_id, api_hash, proxy)

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

            code_ok = False
            while not code_ok:
                code = input('Enter the code you just received: ')
                try:
                    code_ok = self.sign_in(user_phone, code)

                # Two-step verification may be enabled
                except RPCError as e:
                    if e.password_required:
                        pw = getpass(
                            'Two step verification is enabled. Please enter your password: ')
                        code_ok = self.sign_in(password=pw)
                    else:
                        raise

    def run(self):
        # Listen for updates
        self.add_update_handler(self.update_handler)

        # Enter a while loop to chat as long as the user wants
        while True:
            # Retrieve the top dialogs
            dialog_count = 10

            # Entities represent the user, chat or channel
            # corresponding to the dialog on the same index
            dialogs, entities = self.get_dialogs(dialog_count)

            i = None
            while i is None:
                print_title('Dialogs window')

                # Display them so the user can choose
                for i, entity in enumerate(entities):
                    i += 1  # 1-based index
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
                    # Ensure it is inside the bounds, otherwise set to None and retry
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
            print(
                '  !h: prints the latest messages (message History) of the chat.')
            print(
                '  !up <path>: Uploads and sends a Photo located at the given path.')
            print(
                '  !uf <path>: Uploads and sends a File document located at the given path.')
            print(
                '  !dm <msg-id>: Downloads the given message Media (if any).')
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
                    total_count, messages, senders = self.get_message_history(
                        entity, limit=10)
                    # Iterate over all (in reverse order so the latest appears the last in the console)
                    # and print them in "[hh:mm] Sender: Message" text format
                    for msg, sender in zip(
                            reversed(messages), reversed(senders)):
                        # Get the name of the sender if any
                        name = sender.first_name if sender else '???'

                        # Format the message content
                        if getattr(msg, 'media', None):
                            self.found_media.add(msg)
                            content = '<{}> {}'.format(  # The media may or may not have a caption
                                msg.media.__class__.__name__,
                                getattr(msg.media, 'caption', ''))
                        elif hasattr(msg, 'message'):
                            content = msg.message
                        elif hasattr(msg, 'action'):
                            content = str(msg.action)
                        else:
                            # Unknown message, simply print its class name
                            content = msg.__class__.__name__

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

                # Download media
                elif msg.startswith('!dm '):
                    # Slice the message to get message ID
                    self.download_media(msg[len('!dm '):])

                # Download profile photo
                elif msg == '!dp':
                    output = str('usermedia/propic_{}'.format(entity.id))
                    print('Downloading profile picture...')
                    success = self.download_profile_photo(entity.photo, output)
                    if success:
                        print('Profile picture downloaded to {}'.format(
                            output))
                    else:
                        print('No profile picture found for this user.')

                # Send chat message (if any)
                elif msg:
                    self.send_message(
                        entity, msg, markdown=True, no_web_page=True)

    def send_photo(self, path, entity):
        print('Uploading {}...'.format(path))
        input_file = self.upload_file(
            path, progress_callback=self.upload_progress_callback)

        # After we have the handle to the uploaded file, send it to our peer
        self.send_photo_file(input_file, entity)
        print('Photo sent!')

    def send_document(self, path, entity):
        print('Uploading {}...'.format(path))
        input_file = self.upload_file(
            path, progress_callback=self.upload_progress_callback)

        # After we have the handle to the uploaded file, send it to our peer
        self.send_document_file(input_file, entity)
        print('Document sent!')

    def download_media(self, media_id):
        try:
            # The user may have entered a non-integer string!
            msg_media_id = int(media_id)

            # Search the message ID
            for msg in self.found_media:
                if msg.id == msg_media_id:
                    # Let the output be the message ID
                    output = str('usermedia/{}'.format(msg_media_id))
                    print('Downloading media with name {}...'.format(output))
                    output = self.download_msg_media(
                        msg.media,
                        file_path=output,
                        progress_callback=self.download_progress_callback)
                    print('Media downloaded to {}!'.format(output))

        except ValueError:
            print('Invalid media ID given!')

    @staticmethod
    def download_progress_callback(downloaded_bytes, total_bytes):
        InteractiveTelegramClient.print_progress('Downloaded',
                                                 downloaded_bytes, total_bytes)

    @staticmethod
    def upload_progress_callback(uploaded_bytes, total_bytes):
        InteractiveTelegramClient.print_progress('Uploaded', uploaded_bytes,
                                                 total_bytes)

    @staticmethod
    def print_progress(progress_type, downloaded_bytes, total_bytes):
        print('{} {} out of {} ({:.2%})'.format(progress_type, bytes_to_string(
            downloaded_bytes), bytes_to_string(total_bytes), downloaded_bytes /
                                                total_bytes))

    @staticmethod
    def update_handler(update_object):
        if type(update_object) is UpdateShortMessage:
            if update_object.out:
                sprint('You sent {} to user #{}'.format(
                    update_object.message, update_object.user_id))
            else:
                sprint('[User #{} sent {}]'.format(
                    update_object.user_id, update_object.message))

        elif type(update_object) is UpdateShortChatMessage:
            if update_object.out:
                sprint('You sent {} to chat #{}'.format(
                    update_object.message, update_object.chat_id))
            else:
                sprint('[Chat #{}, user #{} sent {}]'.format(
                       update_object.chat_id, update_object.from_id,
                       update_object.message))
