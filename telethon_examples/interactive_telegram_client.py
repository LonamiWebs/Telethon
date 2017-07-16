from getpass import getpass

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import UpdateShortChatMessage, UpdateShortMessage
from telethon.utils import get_display_name
from telethon.errors.rpc_errors_420 import FloodWaitError

from time import sleep
from collections import deque
import codecs
import tempfile
import os


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
        super().__init__(session_user_id, api_id, api_hash, proxy)

        # Store all the found media in memory here,
        # so it can be downloaded if the user wants
        self.found_media = set()
        self._user_phone = user_phone
        self.init_connect()

    def init_connect(self):

        print('Connecting to Telegram servers...')
        if not self.connect():
            print('Initial connection failed. Retrying...')
            if not self.connect():
                print('Could not connect to Telegram servers.')
                return

        # Then, ensure we're authorized and have access
        if not self.is_user_authorized():
            print('First run. Sending code request...')
            self.send_code_request(self._user_phone)

            self_user = None
            while self_user is None:
                code = input('Enter the code you just received: ')
                try:
                    self_user = self.sign_in(self._user_phone, code)

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
            dialog_count = 10

            # Entities represent the user, chat or channel
            # corresponding to the dialog on the same index
            dialogs, entities = self.get_dialogs(dialog_count)

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
            print('  !h: Prints the latest messages (message History).')
            print('  !hd <count> <path>: Dumps the latest message History into file.')
            print('  !up <path>: Uploads and sends the Photo from path.')
            print('  !uf <path>: Uploads and sends the File from path.')
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
                    total_count, messages, senders = self.get_message_history(
                        entity, limit=10)

                    # Iterate over all (in reverse order so the latest appear
                    # the last in the console) and print them with format:
                    # "[yyyy-mm-dd hh:mm] Sender: Message"
                    for msg, sender in zip(
                            reversed(messages), reversed(senders)):
                        name, caption, content = self.extract_message_data(msg, sender)

                        # And print it to the user
                        sprint('[{}-{}-{} {}:{}] ID={} {}: {}'.format(
                            msg.date.year, msg.date.month, msg.date.day,
                            msg.date.hour, msg.date.minute,
                            msg.id, name, content))

                # Dump history to file 
                elif msg.startswith('!hd'):
                    # Dump History into file
                    # Sample usages: !hd
                    #                !hd 1234
                    #                !hd 1234 /tmp/telegram_logs.log
                    #                !hd telegram_logs.log
                    self.dump_history_in_file(msg, entity)

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
                        entity, msg, link_preview=False)

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

    def extract_message_data(self, msg, sender):
        """ Extracts user name from 'sender', message caption and message content from msg."""
        # Get the name of the sender if any
        if sender:
            name = getattr(sender, 'first_name', None)
            if not name:
                name = getattr(sender, 'title', None)
                if not name:
                    name = '???'
        else:
            name = '???'

        caption = None
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

        return name, caption, content

    def retrieve_message_history(self, entity, msg_count, id_offset, buffer):
        """ Retrieves a number (100) of messages from Telegram's DC and adds them to 'buffer'.
            :returns
                msg_count - retrived_msg_count
                id_offset - the id of the last message retrieved
        """
        messages = []
        senders = []

        # First retrieve the messages and some information
        # make 5 attempts
        for i in range(0, 5):
            try:
                total_count, messages, senders = self.get_message_history(
                    entity, limit=100, offset_id=id_offset)
                if total_count > 0 and len(messages) > 0:
                    print('Processing messages {}-{} ...'.format(messages[0].id, messages[-1].id))
            except FloodWaitError as ex:
                sprint('FloodWaitError detected. Sleep for {} sec before reconnecting! \n'.format(ex.seconds))
                sleep(ex.seconds)
                self.init_connect()
                continue
            break

        # Iterate over all (in reverse order so the latest appear
        # the last in the console) and print them with format:
        # "[yyyy-mm-dd hh:mm] Sender: Message RE:"
        for msg, sender in zip(messages, senders):

            name, caption, content = self.extract_message_data(msg, sender)

            re_id_str = ''
            if hasattr(msg, 'reply_to_msg_id') and msg.reply_to_msg_id is not None:
                re_id_str = 'RID={} '.format(str(msg.reply_to_msg_id))

            # Format a message log record
            msg_dump_str = '[{}-{:02d}-{:02d} {:02d}:{:02d}] ID={} {}{}: {}'.format(
                msg.date.year, msg.date.month, msg.date.day,
                msg.date.hour, msg.date.minute, msg.id, re_id_str, name,
                content) 

            buffer.append(msg_dump_str)

            msg_count -= 1
            id_offset = msg.id

            if msg_count == 0:
                break

        return msg_count, id_offset

    def dump_history_in_file(self, msg, entity):
        """ Parses user's input from 'msg'.
        Gets values of:
            param_history_length: the number of messages to retrieve <Default:100>
            param_file_path: file name or file path to the file where those messages are going to be saved
            <Default:telegram_dump.txt>
        """
        # defaults 100 'telegram_dump.txt'
        param_history_length = 100
        param_file_path = 'telegram_dump.txt'

        # parse params
        command_char_count = len('!hd ')
        params_str = msg[command_char_count:].strip()
        next_whitespace_idx = params_str.find(' ')

        param1_str = None
        if next_whitespace_idx > 0:
            param1_str = params_str[:next_whitespace_idx].strip().strip("\"")
        elif len(params_str) > 0:
            param1_str = params_str

        if param1_str is not None and param1_str.isnumeric():
            param_history_length = int(param1_str)
            # consider the rest to be a file path
            next_whitespace_idx = params_str.find(' ')
            if next_whitespace_idx > 0:
                param_file_path = params_str[next_whitespace_idx:].strip().strip("\"")
        elif len(params_str) > 0:
            param_file_path = params_str.strip("\"")

        self.dump_messages_in_file(entity, param_history_length, param_file_path)

    def dump_messages_in_file(self, entity, history_length, file_path):
        """ Retrieves messages in small chunks (Default: 100) and saves them in in-memory 'buffer'.
            When buffer reaches '1000' messages they are saved into intermediate temp file.
            In the end messages from all the temp files are being moved into resulting file in
            ascending order along with the remaining ones in 'buffer'. After all, temp files are deleted.
        """
        print('Dumping {} messages into "{}" file ...'.format(history_length, file_path))

        msg_count_to_process = history_length
        id_offset = 0

        # buffer to save a bulk of messages before flushing them to a file
        buffer = deque()
        temp_files_list = []

        # process messages until either all message count requested by user are retrieved
        # or offset_id reaches msg_id=1 - the head of a channel message history
        while msg_count_to_process > 0:
            sleep(2)  # slip for a few seconds to avoid flood ban
            msg_count_to_process, id_offset = self.retrieve_message_history(entity, msg_count_to_process,
                                                                            id_offset, buffer)
            # when buffer is full, flush it into a temp file
            if len(buffer) >= 1000:
                with tempfile.TemporaryFile(mode='w+', encoding='utf-8', delete=False) as tf:
                    tf.write(codecs.BOM_UTF8.decode())
                    while len(buffer) > 0:
                        print(buffer.pop(), file=tf)
                    temp_files_list.append(tf)

            # break if the very beginning of channel history is reached
            if id_offset <= 1:
                break

        # Write all chunks into resulting file
        with codecs.open(file_path, 'w', 'utf-8') as resulting_file:
            resulting_file.write(codecs.BOM_UTF8.decode())

            # flush what's left in the mem buffer into resulting file
            while len(buffer) > 0:
                print(buffer.pop(), file=resulting_file)

            # merge all temp files into final one and delete them
            for tf in reversed(temp_files_list):
                with codecs.open(tf.name, 'r', 'utf-8') as ctf:
                    for line in ctf.readlines():
                        print(line, file=resulting_file, end='')
                # delete temp file
                tf.close()
                os.remove(tf.name)
