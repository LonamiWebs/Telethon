import tl_generator
from tl.types import UpdateShortChatMessage
from tl.types import UpdateShortMessage

if not tl_generator.tlobjects_exist():
    import errors

    raise errors.TLGeneratorNotRan()
else:
    del tl_generator

from telegram_client import TelegramClient
from utils.helpers import load_settings
import shutil
import traceback

# Get the (current) number of lines in the terminal
cols, rows = shutil.get_terminal_size()


def print_title(title):
    # Clear previous window
    print('\n')
    available_cols = cols - 2  # -2 sincewe omit '┌' and '┐'
    print('┌{}┐'.format('─' * available_cols))
    print('│{}│'.format(title.center(available_cols)))
    print('└{}┘'.format('─' * available_cols))


class InteractiveTelegramClient(TelegramClient):
    def __init__(self, session_user_id, user_phone, layer, api_id, api_hash):
        print_title('Initialization')

        print('Initializing interactive example...')
        super().__init__(session_user_id, layer, api_id, api_hash)

        # Store all the found media in memory here,
        # so it can be downloaded if the user wants
        self.found_media = set()

        print('Connecting to Telegram servers...')
        self.connect()

        # Then, ensure we're authorized and have access
        if not self.is_user_authorized():
            print('First run. Sending code request...')
            self.send_code_request(user_phone)

            code_ok = False
            while not code_ok:
                code = input('Enter the code you just received: ')
                code_ok = self.sign_in(user_phone, code)

    def run(self):
        # Listen for updates
        self.add_update_handler(self.update_handler)

        # Enter a while loop to chat as long as the user wants
        while True:
            # Retrieve the top dialogs
            dialog_count = 10
            dialogs, displays, inputs = self.get_dialogs(dialog_count)

            i = None
            while i is None:
                try:
                    print_title('Dialogs window')

                    # Display them so the user can choose
                    for i, display in enumerate(displays):
                        i += 1  # 1-based index for normies
                        print('{}. {}'.format(i, display))

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

                    i = int(i if i else 0) - 1
                    # Ensure it is inside the bounds, otherwise set to None and retry
                    if not 0 <= i < dialog_count:
                        i = None

                except ValueError:
                    pass

            # Retrieve the selected user
            display = displays[i]
            input_peer = inputs[i]

            # Show some information
            print_title('Chat with "{}"'.format(display))
            print('Available commands:')
            print('  !q: Quits the current chat.')
            print('  !Q: Quits the current chat and exits.')
            print('  !h: prints the latest messages (message History) of the chat.')
            print('  !p <path>: sends a Photo located at the given path.')
            print('  !f <path>: sends a File document located at the given path.')
            print('  !d <msg-id>: Downloads the given message media (if any).')
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
                    total_count, messages, senders = self.get_message_history(input_peer, limit=10)
                    # Iterate over all (in reverse order so the latest appears the last in the console)
                    # and print them in "[hh:mm] Sender: Message" text format
                    for msg, sender in zip(reversed(messages), reversed(senders)):
                        # Get the name of the sender if any
                        name = sender.first_name if sender else '???'

                        # Format the message content
                        if msg.media:
                            self.found_media.add(msg)
                            content = '<{}> {}'.format(  # The media may or may not have a caption
                                msg.media.__class__.__name__, getattr(msg.media, 'caption', ''))
                        else:
                            content = msg.message

                        # And print it to the user
                        print('[{}:{}] (ID={}) {}: {}'.format(
                            msg.date.hour, msg.date.minute, msg.id, name, content))

                # Send photo
                elif msg.startswith('!p '):
                    # Slice the message to get the path
                    self.send_photo(path=msg[len('!p '):], peer=input_peer)

                # Send file (document)
                elif msg.startswith('!f '):
                    # Slice the message to get the path
                    self.send_document(path=msg[len('!f '):], peer=input_peer)

                # Download media
                elif msg.startswith('!d '):
                    # Slice the message to get message ID
                    self.download_media(msg[len('!d '):])

                # Send chat message (if any)
                elif msg:
                    self.send_message(input_peer, msg, markdown=True, no_web_page=True)

    def send_photo(self, path, peer):
        print('Uploading {}...'.format(path))
        input_file = self.upload_file(path)

        # After we have the handle to the uploaded file, send it to our peer
        self.send_photo_file(input_file, peer)
        print('Photo sent!')

    def send_document(self, path, peer):
        print('Uploading {}...'.format(path))
        input_file = self.upload_file(path)

        # After we have the handle to the uploaded file, send it to our peer
        self.send_document_file(input_file, peer)
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
                    output = self.download_msg_media(msg.media, file_path=output)
                    print('Media downloaded to {}!'.format(output))

        except ValueError:
            print('Invalid media ID given!')

    @staticmethod
    def update_handler(update_object):
        if type(update_object) is UpdateShortMessage:
            print('[User #{} sent {}]'.format(update_object.user_id, update_object.message))

        elif type(update_object) is UpdateShortChatMessage:
            print('[Chat #{} sent {}]'.format(update_object.chat_id, update_object.message))


if __name__ == '__main__':
    # Load the settings and initialize the client
    settings = load_settings()
    client = InteractiveTelegramClient(
        session_user_id=settings.get('session_name', 'anonymous'),
        user_phone=str(settings['user_phone']),
        layer=55,
        api_id=settings['api_id'],
        api_hash=settings['api_hash'])

    print('Initialization done!')

    try:
        client.run()

    except Exception as e:
        print('Unexpected error ({}): {} at\n{}'.format(type(e), e, traceback.format_exc()))

    finally:
        print_title('Exit')
        print('Thanks for trying the interactive example! Exiting...')
        client.disconnect()
